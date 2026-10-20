# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Persistent, cross-connection reauthentication admission tests."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from fluxtuner.core import db
from fluxtuner.web import reauth_attempts as attempts

NOW = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)


def setup_storage(tmp_path):
    path = tmp_path / "reauth-admission.db"
    db.init_db(path)
    with db.connect(path) as conn:
        user_id = db.get_or_create_user(
            conn, "alice", password_hash="test-hash", is_active=True
        )
        conn.commit()
    return path, user_id


def reserve(path, user_id, *, now=NOW):
    with db.connect(path) as conn:
        return attempts.reserve_attempt(conn, user_id, "client-A", now=now)


def test_two_pending_reservations_limit_admission(tmp_path) -> None:
    path, user_id = setup_storage(tmp_path)

    first = reserve(path, user_id)
    second = reserve(path, user_id)
    third = reserve(path, user_id)

    assert isinstance(first, int)
    assert isinstance(second, int)
    assert first != second
    assert third is None


def test_failures_persist_between_connections_and_expire(tmp_path) -> None:
    path, user_id = setup_storage(tmp_path)

    for _ in range(attempts.MAX_FAILED_ATTEMPTS):
        attempt_id = reserve(path, user_id)
        assert attempt_id is not None

        with db.connect(path) as conn:
            assert attempts.finish_attempt(
                conn, attempt_id, success=False, now=NOW
            )
            conn.commit()

    assert reserve(path, user_id) is None
    assert reserve(
        path,
        user_id,
        now=NOW + timedelta(seconds=attempts.FAILED_WINDOW_SECONDS + 1),
    ) is not None


def test_expired_reservation_cannot_finalize_successfully(tmp_path) -> None:
    path, user_id = setup_storage(tmp_path)
    attempt_id = reserve(path, user_id)
    assert attempt_id is not None

    expired = NOW + timedelta(seconds=attempts.PENDING_LEASE_SECONDS + 1)

    with db.connect(path) as conn:
        assert not attempts.finish_attempt(
            conn, attempt_id, success=True, now=expired
        )
        conn.commit()

    assert reserve(path, user_id, now=expired) is not None


def test_reservation_releases_writer_before_password_verification(
    tmp_path,
) -> None:
    path, user_id = setup_storage(tmp_path)
    assert reserve(path, user_id) is not None

    with db.connect(path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.rollback()


def test_concurrent_reservations_do_not_exceed_pending_limit(
    tmp_path,
) -> None:
    path, user_id = setup_storage(tmp_path)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: reserve(path, user_id),
                range(8),
            )
        )

    accepted = [result for result in results if result is not None]
    assert len(accepted) == attempts.MAX_PENDING_ATTEMPTS
    assert len(set(accepted)) == len(accepted)


def test_expired_reservation_still_records_failed_password(tmp_path) -> None:
    path, user_id = setup_storage(tmp_path)
    attempt_id = reserve(path, user_id)
    assert attempt_id is not None

    expired = NOW + timedelta(seconds=attempts.PENDING_LEASE_SECONDS + 1)

    with db.connect(path) as conn:
        assert attempts.finish_attempt(
            conn, attempt_id, success=False, now=expired
        )
        conn.commit()

    with db.connect(path) as conn:
        row = conn.execute(
            "SELECT status FROM web_reauth_attempts WHERE id = ?",
            (attempt_id,),
        ).fetchone()
        assert row is not None
        assert row["status"] == "failed"

        count = conn.execute(
            """
            SELECT COUNT(*) AS count
            FROM web_reauth_attempts
            WHERE user_id = ? AND status = 'failed'
            """,
            (user_id,),
        ).fetchone()
        assert count["count"] == 1



def test_failures_from_different_clients_share_account_limit(tmp_path) -> None:
    path, user_id = setup_storage(tmp_path)

    for number in range(attempts.MAX_FAILED_ATTEMPTS):
        with db.connect(path) as conn:
            attempt_id = attempts.reserve_attempt(
                conn, user_id, f"source-{number}", now=NOW
            )
            assert attempt_id is not None

        with db.connect(path) as conn:
            assert attempts.finish_attempt(
                conn, attempt_id, success=False, now=NOW
            )
            conn.commit()

    with db.connect(path) as conn:
        assert attempts.reserve_attempt(
            conn, user_id, "previously-unseen-source", now=NOW
        ) is None


def test_pending_from_different_clients_share_account_limit(tmp_path) -> None:
    path, user_id = setup_storage(tmp_path)

    with db.connect(path) as conn:
        first = attempts.reserve_attempt(
            conn, user_id, "source-1", now=NOW
        )
        second = attempts.reserve_attempt(
            conn, user_id, "source-2", now=NOW
        )
        blocked = attempts.reserve_attempt(
            conn, user_id, "source-3", now=NOW
        )

    assert first is not None
    assert second is not None
    assert blocked is None



def test_failed_plus_pending_reservations_share_five_attempt_budget(
    tmp_path,
) -> None:
    path, user_id = setup_storage(tmp_path)

    for number in range(attempts.MAX_FAILED_ATTEMPTS - 1):
        with db.connect(path) as conn:
            attempt_id = attempts.reserve_attempt(
                conn, user_id, f"failed-source-{number}", now=NOW
            )
            assert attempt_id is not None

        with db.connect(path) as conn:
            assert attempts.finish_attempt(
                conn, attempt_id, success=False, now=NOW
            )
            conn.commit()

    with db.connect(path) as conn:
        pending = attempts.reserve_attempt(
            conn, user_id, "pending-source", now=NOW
        )
        blocked = attempts.reserve_attempt(
            conn, user_id, "another-source", now=NOW
        )

    assert pending is not None
    assert blocked is None
