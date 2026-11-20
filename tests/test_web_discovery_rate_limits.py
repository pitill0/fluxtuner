"""Persistent discovery admission is bounded, atomic and migratable."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from fluxtuner.core import db
from fluxtuner.web.discovery_rate_limits import (
    MAX_ATTEMPTS,
    admit_redemption,
    purge_stale_limits,
)


def _default_user(conn):
    return int(
        conn.execute("SELECT id FROM users WHERE username = ?", (db.DEFAULT_USER_NAME,)).fetchone()[
            0
        ]
    )


def test_discovery_rate_limit_is_bounded_and_resets(tmp_path):
    path = tmp_path / "discovery.db"
    db.init_db(path)
    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    with db.connect(path) as conn:
        user_id = _default_user(conn)
        for _ in range(MAX_ATTEMPTS):
            assert admit_redemption(conn, user_id=user_id, now=now)
        for _ in range(100):
            assert not admit_redemption(conn, user_id=user_id, now=now)
        assert conn.execute("SELECT COUNT(*) FROM web_discovery_rate_limits").fetchone()[0] == 1
        assert admit_redemption(conn, user_id=user_id, now=now + timedelta(seconds=60))
        assert (
            conn.execute(
                "SELECT attempts FROM web_discovery_rate_limits WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            == 1
        )
        assert purge_stale_limits(conn, now=now + timedelta(seconds=121)) == 1
        assert conn.execute("SELECT COUNT(*) FROM web_discovery_rate_limits").fetchone()[0] == 0


def test_backward_clock_does_not_reset_redemption_window(tmp_path):
    path = tmp_path / "backward.db"
    db.init_db(path)
    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    with db.connect(path) as conn:
        user_id = _default_user(conn)
        for _ in range(MAX_ATTEMPTS):
            assert admit_redemption(conn, user_id=user_id, now=now)
        # A thread whose clock was read before it acquired the SQLite lock
        # must not replenish the exhausted per-user quota.
        assert not admit_redemption(conn, user_id=user_id, now=now - timedelta(seconds=1))
        assert not admit_redemption(conn, user_id=user_id, now=now)
        assert (
            conn.execute(
                "SELECT attempts FROM web_discovery_rate_limits WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            == MAX_ATTEMPTS
        )


def test_discovery_rate_limit_serializes_concurrent_attempts(tmp_path):
    path = tmp_path / "concurrent.db"
    db.init_db(path)
    with db.connect(path) as conn:
        user_id = _default_user(conn)

    def attempt(_index):
        with db.connect(path) as conn:
            return admit_redemption(conn, user_id=user_id)

    with ThreadPoolExecutor(max_workers=12) as pool:
        results = list(pool.map(attempt, range(40)))
    assert sum(results) == MAX_ATTEMPTS
    with db.connect(path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM web_discovery_rate_limits").fetchone()[0] == 1


def test_v8_upgrade_preserves_data_and_adds_limit_table(tmp_path):
    path = tmp_path / "upgrade.db"
    db.init_db(path)
    with db.connect(path) as conn:
        user_id = _default_user(conn)
        conn.execute("DROP TABLE web_discovery_rate_limits")
        conn.execute("PRAGMA user_version = 8")
        conn.commit()
    db.init_db(path)
    with db.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 9
        assert _default_user(conn) == user_id
        assert admit_redemption(conn, user_id=user_id)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_discovery_admission_rejects_invalid_input(tmp_path):
    path = tmp_path / "invalid.db"
    db.init_db(path)
    with db.connect(path) as conn:
        with pytest.raises(ValueError):
            admit_redemption(conn, user_id=0)
        with pytest.raises(ValueError):
            admit_redemption(conn, user_id=True)
        conn.execute("BEGIN")
        with pytest.raises(RuntimeError):
            admit_redemption(conn, user_id=_default_user(conn))
        conn.rollback()
