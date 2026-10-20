# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Security regression tests for recovery-code regeneration."""

import sqlite3

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import create_app
from fluxtuner.web.security import CSRF_HEADER_NAME

VALID_PASSWORD = "correct horse battery staple"
INVALID_PASSWORD = "incorrect horse battery staple"
REGENERATE_URL = "/api/auth/recovery-codes/regenerate"


def make_authenticated_client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "regeneration-hardening.db")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")

    db.init_db()

    with db.connect() as conn:
        db.get_or_create_user(
            conn,
            "alice",
            password_hash=auth.hash_password(VALID_PASSWORD),
            is_active=True,
        )
        conn.commit()

    client = TestClient(create_app())
    response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )

    assert response.status_code == 200

    return client, response.json()["csrf_token"]


def regenerate(client, csrf_token, password):
    return client.post(
        REGENERATE_URL,
        headers={CSRF_HEADER_NAME: csrf_token},
        json={"current_password": password},
    )


def test_regeneration_rate_limit_rejects_before_argon2(
    tmp_path,
    monkeypatch,
) -> None:
    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    for _ in range(5):
        response = regenerate(client, csrf_token, INVALID_PASSWORD)
        assert response.status_code == 401

    original_verify = auth.verify_password
    verification_calls = 0

    def counted_verify(password, password_hash):
        nonlocal verification_calls
        verification_calls += 1
        return original_verify(password, password_hash)

    monkeypatch.setattr(auth, "verify_password", counted_verify)

    blocked = regenerate(client, csrf_token, VALID_PASSWORD)

    assert blocked.status_code == 429
    assert "recovery_codes" not in blocked.json()
    assert verification_calls == 0


def test_regeneration_argon2_does_not_hold_sqlite_writer_reservation(
    tmp_path,
    monkeypatch,
) -> None:
    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    original_verify = auth.verify_password
    observed = False

    def verify_with_competing_writer(password, password_hash):
        nonlocal observed

        # A different connection must be able to reserve the writer
        # while the request performs its expensive password verification.
        with sqlite3.connect(db.DB_FILE, timeout=0) as other:
            other.execute("BEGIN IMMEDIATE")
            other.rollback()
            observed = True

        return original_verify(password, password_hash)

    monkeypatch.setattr(
        auth,
        "verify_password",
        verify_with_competing_writer,
    )

    response = regenerate(client, csrf_token, VALID_PASSWORD)

    assert response.status_code == 200
    assert observed
    assert len(response.json()["recovery_codes"]) == 8


def test_regeneration_rejects_password_change_during_verification(
    tmp_path,
    monkeypatch,
) -> None:
    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    with db.connect() as conn:
        original_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    replacement_hash = auth.hash_password(
        "replacement credential for concurrent change"
    )
    original_verify = auth.verify_password
    updated = False

    def verify_while_password_changes(password, password_hash):
        nonlocal updated
        result = original_verify(password, password_hash)

        with db.connect() as other:
            other.execute(
                "UPDATE users SET password_hash = ? WHERE username = ?",
                (replacement_hash, "alice"),
            )
            other.commit()
            updated = True

        return result

    monkeypatch.setattr(
        auth,
        "verify_password",
        verify_while_password_changes,
    )

    response = regenerate(client, csrf_token, VALID_PASSWORD)

    assert updated
    assert response.status_code == 401
    assert "recovery_codes" not in response.json()

    with db.connect() as conn:
        current_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    assert current_codes == original_codes


def test_regeneration_rejects_session_revocation_during_verification(
    tmp_path,
    monkeypatch,
) -> None:
    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    with db.connect() as conn:
        original_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    original_verify = auth.verify_password
    revoked = False

    def verify_while_session_is_revoked(password, password_hash):
        nonlocal revoked
        result = original_verify(password, password_hash)

        with db.connect() as other:
            other.execute(
                """
                UPDATE web_sessions
                SET revoked_at = ?
                WHERE user_id = (
                    SELECT id FROM users WHERE username = ?
                )
                  AND revoked_at IS NULL
                """,
                (db.utc_now(), "alice"),
            )
            other.commit()
            revoked = True

        return result

    monkeypatch.setattr(
        auth,
        "verify_password",
        verify_while_session_is_revoked,
    )

    response = regenerate(client, csrf_token, VALID_PASSWORD)

    assert revoked
    assert response.status_code == 401
    assert "recovery_codes" not in response.json()

    with db.connect() as conn:
        current_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    assert current_codes == original_codes


def test_regeneration_failures_do_not_limit_normal_login(
    tmp_path,
    monkeypatch,
) -> None:
    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    for _ in range(5):
        response = regenerate(client, csrf_token, INVALID_PASSWORD)
        assert response.status_code == 401

    limited = regenerate(client, csrf_token, VALID_PASSWORD)
    assert limited.status_code == 429

    login_response = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": VALID_PASSWORD},
    )
    assert login_response.status_code == 200


def test_rate_limited_regeneration_preserves_existing_codes(
    tmp_path,
    monkeypatch,
) -> None:
    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    with db.connect() as conn:
        original_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    for _ in range(5):
        response = regenerate(client, csrf_token, INVALID_PASSWORD)
        assert response.status_code == 401

    blocked = regenerate(client, csrf_token, VALID_PASSWORD)
    assert blocked.status_code == 429
    assert "recovery_codes" not in blocked.json()

    with db.connect() as conn:
        current_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    assert current_codes == original_codes


def test_expired_successful_verification_cannot_rotate_codes(
    tmp_path,
    monkeypatch,
) -> None:
    from datetime import UTC, datetime, timedelta

    from fluxtuner.web import reauth_attempts

    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    with db.connect() as conn:
        original_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    original_finish = reauth_attempts.finish_attempt

    def finish_after_lease(conn, attempt_id, *, success, now=None):
        if success:
            row = conn.execute(
                """
                SELECT expires_at
                FROM web_reauth_attempts
                WHERE id = ?
                """,
                (attempt_id,),
            ).fetchone()
            assert row is not None
            expiry = datetime.fromisoformat(row["expires_at"])
            assert expiry.tzinfo is not None
            now = expiry.astimezone(UTC) + timedelta(seconds=1)

        return original_finish(
            conn,
            attempt_id,
            success=success,
            now=now,
        )

    monkeypatch.setattr(
        reauth_attempts,
        "finish_attempt",
        finish_after_lease,
    )

    response = regenerate(client, csrf_token, VALID_PASSWORD)

    assert response.status_code == 401
    assert "recovery_codes" not in response.json()

    with db.connect() as conn:
        current_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    assert current_codes == original_codes


def test_rotation_exception_releases_reservation_without_changing_codes(
    tmp_path,
    monkeypatch,
) -> None:
    import pytest

    from fluxtuner.core import recovery_codes

    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    with db.connect() as conn:
        original_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    def failed_rotation(conn, user_id):
        # Simulate an exception after modifying the transaction.
        conn.execute(
            "DELETE FROM web_recovery_codes WHERE user_id = ?",
            (user_id,),
        )
        raise RuntimeError("Simulated rotation failure")

    monkeypatch.setattr(
        recovery_codes,
        "rotate_recovery_codes",
        failed_rotation,
    )

    with pytest.raises(RuntimeError, match="Simulated rotation failure"):
        regenerate(client, csrf_token, VALID_PASSWORD)

    with db.connect() as conn:
        current_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }
        attempts = conn.execute(
            """
            SELECT status
            FROM web_reauth_attempts
            ORDER BY id
            """
        ).fetchall()

    assert current_codes == original_codes
    assert len(attempts) == 1
    assert attempts[0]["status"] == "failed"


def test_concurrent_http_regenerations_limit_pending_argon2(
    tmp_path,
    monkeypatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event, Lock

    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    original_verify = auth.verify_password
    two_verifications_started = Event()
    release_verifications = Event()
    counter_lock = Lock()
    verification_count = 0

    def controlled_verify(password, password_hash):
        nonlocal verification_count

        with counter_lock:
            verification_count += 1
            if verification_count == 2:
                two_verifications_started.set()

        if not release_verifications.wait(timeout=15):
            raise AssertionError("Timed out waiting to release Argon2")

        return original_verify(password, password_hash)

    monkeypatch.setattr(auth, "verify_password", controlled_verify)

    # Each HTTP client has its own transport but shares the
    # authenticated session cookie.
    first_client = TestClient(create_app())
    second_client = TestClient(create_app())
    third_client = TestClient(create_app())

    for concurrent_client in (
        first_client,
        second_client,
        third_client,
    ):
        concurrent_client.cookies.update(client.cookies)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first_future = executor.submit(
            regenerate,
            first_client,
            csrf_token,
            VALID_PASSWORD,
        )
        second_future = executor.submit(
            regenerate,
            second_client,
            csrf_token,
            VALID_PASSWORD,
        )

        try:
            assert two_verifications_started.wait(timeout=15), (
                "Two admitted requests did not reach password verification"
            )

            rejected = regenerate(
                third_client,
                csrf_token,
                VALID_PASSWORD,
            )

            assert rejected.status_code == 429
            assert "recovery_codes" not in rejected.json()

            with counter_lock:
                assert verification_count == 2

        finally:
            release_verifications.set()

        first = first_future.result(timeout=15)
        second = second_future.result(timeout=15)

    assert first.status_code == 200
    assert second.status_code == 200

    for response in (first, second):
        assert len(response.json()["recovery_codes"]) == 8

    with counter_lock:
        assert verification_count == 2



def test_hash_read_exception_finalizes_reserved_attempt(
    tmp_path, monkeypatch
) -> None:
    import sqlite3

    import pytest

    from fluxtuner.web import reauth_attempts

    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    with db.connect() as conn:
        original_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }

    original_connect = db.connect
    original_reserve = reauth_attempts.reserve_attempt
    inject_failure = False
    failure_injected = False

    def reserve_then_arm_failure(conn, user_id, client_key, **kwargs):
        nonlocal inject_failure

        attempt_id = original_reserve(
            conn, user_id, client_key, **kwargs
        )
        assert attempt_id is not None
        inject_failure = True
        return attempt_id

    def fail_next_connection(*args, **kwargs):
        nonlocal inject_failure, failure_injected

        if inject_failure:
            inject_failure = False
            failure_injected = True
            raise sqlite3.OperationalError(
                "Simulated password-hash read failure"
            )

        return original_connect(*args, **kwargs)

    monkeypatch.setattr(
        reauth_attempts,
        "reserve_attempt",
        reserve_then_arm_failure,
    )
    monkeypatch.setattr(db, "connect", fail_next_connection)

    with pytest.raises(
        sqlite3.OperationalError,
        match="Simulated password-hash read failure",
    ):
        regenerate(client, csrf_token, VALID_PASSWORD)

    assert failure_injected

    with original_connect() as conn:
        current_codes = {
            row["code_hash"]
            for row in conn.execute(
                "SELECT code_hash FROM web_recovery_codes"
            )
        }
        recorded = conn.execute(
            """
            SELECT status
            FROM web_reauth_attempts
            ORDER BY id
            """
        ).fetchall()

    assert current_codes == original_codes
    assert len(recorded) == 1
    assert recorded[0]["status"] == "failed"



def test_hash_read_error_survives_failure_accounting_error(
    tmp_path, monkeypatch
) -> None:
    import sqlite3

    import pytest

    from fluxtuner.web import reauth_attempts

    client, csrf_token = make_authenticated_client(tmp_path, monkeypatch)

    original_connect = db.connect
    original_reserve = reauth_attempts.reserve_attempt

    fail_hash_connection = False
    hash_failure_seen = False
    accounting_failure_seen = False

    def reserve_then_arm_failure(conn, user_id, client_key, **kwargs):
        nonlocal fail_hash_connection
        attempt_id = original_reserve(
            conn, user_id, client_key, **kwargs
        )
        assert attempt_id is not None
        fail_hash_connection = True
        return attempt_id

    def fail_hash_read_connection(*args, **kwargs):
        nonlocal fail_hash_connection, hash_failure_seen

        if fail_hash_connection:
            fail_hash_connection = False
            hash_failure_seen = True
            raise sqlite3.OperationalError(
                "Simulated password-hash read failure"
            )

        return original_connect(*args, **kwargs)

    def fail_accounting(conn, attempt_id, *, success, now=None):
        nonlocal accounting_failure_seen
        accounting_failure_seen = True
        raise sqlite3.OperationalError(
            "Simulated failure-accounting error"
        )

    monkeypatch.setattr(
        reauth_attempts, "reserve_attempt", reserve_then_arm_failure
    )
    monkeypatch.setattr(db, "connect", fail_hash_read_connection)
    monkeypatch.setattr(
        reauth_attempts, "finish_attempt", fail_accounting
    )

    with pytest.raises(
        sqlite3.OperationalError,
        match="Simulated password-hash read failure",
    ) as captured:
        regenerate(client, csrf_token, VALID_PASSWORD)

    assert hash_failure_seen
    assert accounting_failure_seen

    cause = captured.value.__cause__
    assert isinstance(cause, sqlite3.OperationalError)
    assert "Simulated failure-accounting error" in str(cause)

    with original_connect() as conn:
        attempts = conn.execute(
            "SELECT status FROM web_reauth_attempts ORDER BY id"
        ).fetchall()

    assert len(attempts) == 1
    assert attempts[0]["status"] == "pending"
