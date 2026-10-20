# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Retention tests for persistent reauthentication attempts."""

from datetime import UTC, datetime, timedelta

import pytest

from fluxtuner.core import db
from fluxtuner.web import maintenance, reauth_attempts

NOW = datetime(2026, 10, 20, 10, 0, tzinfo=UTC)


def _ts(value: datetime) -> str:
    return value.isoformat()


def _setup(tmp_path, monkeypatch):
    path = tmp_path / "reauth-maintenance.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    db.init_db(path)

    with db.connect(path) as conn:
        user_id = db.get_or_create_user(
            conn,
            "reauth-maintenance-user",
            password_hash="test-hash",
            is_active=True,
        )
        conn.commit()

    return path, user_id


def _insert(conn, user_id, status, attempted_at, expires_at):
    conn.execute(
        """
        INSERT INTO web_reauth_attempts (
            user_id, client_key, status, attempted_at, expires_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            user_id,
            "test-client",
            status,
            _ts(attempted_at),
            _ts(expires_at),
        ),
    )


def test_maintenance_removes_only_stale_reauth_rows(tmp_path, monkeypatch) -> None:
    path, user_id = _setup(tmp_path, monkeypatch)

    old = NOW - timedelta(hours=25)
    recent = NOW - timedelta(minutes=2)

    with db.connect(path) as conn:
        _insert(
            conn,
            user_id,
            "pending",
            NOW - timedelta(minutes=10),
            NOW - timedelta(minutes=8),
        )
        _insert(
            conn,
            user_id,
            "pending",
            recent,
            NOW - timedelta(seconds=1),
        )
        _insert(
            conn,
            user_id,
            "pending",
            recent,
            NOW + timedelta(seconds=60),
        )
        _insert(
            conn,
            user_id,
            "failed",
            old,
            old + timedelta(minutes=5),
        )
        _insert(
            conn,
            user_id,
            "failed",
            recent,
            NOW + timedelta(minutes=3),
        )
        _insert(
            conn,
            user_id,
            "succeeded",
            old,
            old + timedelta(minutes=5),
        )
        _insert(
            conn,
            user_id,
            "succeeded",
            recent,
            NOW + timedelta(minutes=3),
        )
        conn.commit()

    result = maintenance.run_auth_maintenance(now=NOW)
    assert result.old_reauth_attempts == 3

    with db.connect(path) as conn:
        remaining = conn.execute(
            """
            SELECT status, expires_at
            FROM web_reauth_attempts
            ORDER BY id
            """
        ).fetchall()

    assert [row["status"] for row in remaining] == [
        "pending",
        "pending",
        "failed",
        "succeeded",
    ]
    assert remaining[0]["expires_at"] == _ts(NOW - timedelta(seconds=1))
    assert remaining[1]["expires_at"] == _ts(NOW + timedelta(seconds=60))


def test_reauth_retention_rejects_unsafe_short_window(tmp_path, monkeypatch) -> None:
    path, _ = _setup(tmp_path, monkeypatch)

    with db.connect(path) as conn, pytest.raises(ValueError, match="retention"):
        reauth_attempts.purge_old_reauth_attempts(
            conn,
            now=NOW,
            window_seconds=reauth_attempts.FAILED_WINDOW_SECONDS - 1,
        )


def test_reauth_maintenance_commits_deletions(tmp_path, monkeypatch) -> None:
    path, user_id = _setup(tmp_path, monkeypatch)

    with db.connect(path) as conn:
        _insert(
            conn,
            user_id,
            "pending",
            NOW - timedelta(minutes=10),
            NOW - timedelta(minutes=8),
        )
        conn.commit()

    result = maintenance.run_auth_maintenance(now=NOW)
    assert result.old_reauth_attempts == 1

    with db.connect(path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM web_reauth_attempts").fetchone()[0]

    assert count == 0


def test_cleanup_does_not_discard_inflight_failure_accounting(tmp_path, monkeypatch) -> None:
    path, user_id = _setup(tmp_path, monkeypatch)

    # The reservation expires while password verification is still running.
    started = NOW - timedelta(seconds=reauth_attempts.PENDING_LEASE_SECONDS + 1)

    with db.connect(path) as conn:
        attempt_id = reauth_attempts.reserve_attempt(
            conn,
            user_id,
            "slow-verification",
            now=started,
        )

    assert attempt_id is not None

    # Background maintenance runs before Argon2 has returned.
    maintenance.run_auth_maintenance(now=NOW)

    # A password failure must remain accountable after maintenance.
    with db.connect(path) as conn:
        finalized = reauth_attempts.finish_attempt(
            conn,
            attempt_id,
            success=False,
            now=NOW,
        )
        conn.commit()

    assert finalized

    with db.connect(path) as conn:
        row = conn.execute(
            """
            SELECT status
            FROM web_reauth_attempts
            WHERE id = ?
            """,
            (attempt_id,),
        ).fetchone()

    assert row is not None
    assert row["status"] == "failed"
