from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fluxtuner.core import db, recovery_codes
from fluxtuner.web import auth, maintenance


def test_auth_maintenance_purges_only_expired_or_stale_rows(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "maintenance.db"
    monkeypatch.setattr(db, "DB_FILE", db_path)
    db.init_db()

    now = datetime(2026, 1, 2, tzinfo=UTC)

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "alice")

        auth.create_session(
            conn,
            user_id,
            max_age_seconds=10,
            now=now - timedelta(seconds=11),
        )
        auth.create_session(
            conn,
            user_id,
            max_age_seconds=100,
            now=now,
        )

        auth.record_login_attempt(
            conn,
            "alice",
            "127.0.0.1",
            success=False,
            now=now - timedelta(hours=25),
        )
        auth.record_login_attempt(
            conn,
            "alice",
            "127.0.0.1",
            success=False,
            now=now - timedelta(hours=23),
        )

        recovery_codes.record_recovery_attempt(
            conn,
            "alice",
            "127.0.0.1",
            success=False,
            now=now - timedelta(hours=25),
        )
        recovery_codes.record_recovery_attempt(
            conn,
            "alice",
            "127.0.0.1",
            success=False,
            now=now - timedelta(hours=23),
        )
        conn.commit()

    result = maintenance.run_auth_maintenance(now=now)

    with db.connect() as conn:
        session_count = conn.execute("SELECT COUNT(*) FROM web_sessions").fetchone()[0]
        login_count = conn.execute("SELECT COUNT(*) FROM web_login_attempts").fetchone()[0]
        recovery_count = conn.execute("SELECT COUNT(*) FROM web_recovery_attempts").fetchone()[0]

    assert result.expired_sessions == 1
    assert result.old_login_attempts == 1
    assert result.old_recovery_attempts == 1
    assert session_count == 1
    assert login_count == 1
    assert recovery_count == 1


def test_auth_maintenance_commits_independently(
    tmp_path,
    monkeypatch,
) -> None:
    db_path = tmp_path / "maintenance.db"
    monkeypatch.setattr(db, "DB_FILE", db_path)
    db.init_db()

    now = datetime(2026, 1, 2, tzinfo=UTC)

    with db.connect() as conn:
        auth.record_login_attempt(
            conn,
            "alice",
            "127.0.0.1",
            success=False,
            now=now - timedelta(hours=25),
        )
        conn.commit()

    maintenance.run_auth_maintenance(now=now)

    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO web_login_attempts (
                normalized_username,
                client_key,
                success,
                attempted_at
            )
            VALUES ('rollback-test', '127.0.0.1', 0, ?)
            """,
            (now.isoformat(),),
        )
        conn.rollback()

    with db.connect() as conn:
        old_count = conn.execute(
            """
            SELECT COUNT(*)
            FROM web_login_attempts
            WHERE normalized_username = 'alice'
            """
        ).fetchone()[0]

    assert old_count == 0


def test_auth_maintenance_if_due_is_throttled(
    monkeypatch,
) -> None:
    runs = 0

    def fake_maintenance(*, now=None):
        nonlocal runs
        runs += 1
        return maintenance.AuthMaintenanceResult(0, 0, 0)

    monkeypatch.setattr(
        maintenance,
        "run_auth_maintenance",
        fake_maintenance,
    )
    monkeypatch.setattr(
        maintenance,
        "_last_auth_maintenance_monotonic",
        None,
    )

    assert maintenance.run_auth_maintenance_if_due(
        monotonic_now=1000.0,
    )
    assert not maintenance.run_auth_maintenance_if_due(
        monotonic_now=1000.0 + maintenance.AUTH_MAINTENANCE_INTERVAL_SECONDS - 1,
    )
    assert maintenance.run_auth_maintenance_if_due(
        monotonic_now=1000.0 + maintenance.AUTH_MAINTENANCE_INTERVAL_SECONDS,
    )

    assert runs == 2


def test_failed_auth_maintenance_does_not_consume_throttle_window(
    monkeypatch,
) -> None:
    attempts = 0

    def flaky_maintenance(*, now=None):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("maintenance failed")
        return maintenance.AuthMaintenanceResult(0, 0, 0)

    monkeypatch.setattr(
        maintenance,
        "run_auth_maintenance",
        flaky_maintenance,
    )
    monkeypatch.setattr(
        maintenance,
        "_last_auth_maintenance_monotonic",
        None,
    )

    import pytest

    with pytest.raises(RuntimeError, match="maintenance failed"):
        maintenance.run_auth_maintenance_if_due(
            monotonic_now=1000.0,
        )

    assert maintenance.run_auth_maintenance_if_due(
        monotonic_now=1000.0,
    )
    assert attempts == 2


def test_concurrent_auth_maintenance_if_due_runs_cleanup_once(
    monkeypatch,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock
    from time import sleep

    start = Barrier(2)
    runs = 0
    runs_lock = Lock()

    def fake_maintenance(*, now=None):
        nonlocal runs
        with runs_lock:
            runs += 1
        sleep(0.05)
        return maintenance.AuthMaintenanceResult(0, 0, 0)

    monkeypatch.setattr(
        maintenance,
        "run_auth_maintenance",
        fake_maintenance,
    )
    monkeypatch.setattr(
        maintenance,
        "_last_auth_maintenance_monotonic",
        None,
    )

    def attempt() -> bool:
        start.wait(timeout=5)
        return maintenance.run_auth_maintenance_if_due(
            monotonic_now=1000.0,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: attempt(), range(2)))

    assert sorted(results) == [False, True]
    assert runs == 1
