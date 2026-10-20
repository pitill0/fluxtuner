# SPDX-License-Identifier: MIT

from pathlib import Path

import pytest

from fluxtuner.core import db


def patch_db_file(tmp_path: Path, monkeypatch) -> Path:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    return db_file


def test_init_db_creates_database_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    db_file = patch_db_file(tmp_path, monkeypatch)

    db.init_db()

    assert db_file.exists()


def test_init_db_creates_expected_tables(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    db.init_db()

    with db.connect() as conn:
        assert db.table_names(conn) == {
            "web_reauth_attempts",
            "favorites",
            "history_entries",
            "playlist_stations",
            "playlists",
            "profiles",
            "recordings",
            "schema_migrations",
            "stations",
            "users",
            "web_login_attempts",
            "web_password_change_requests",
            "web_recovery_attempts",
            "web_recovery_codes",
            "web_sessions",
        }


def test_init_db_creates_default_user_and_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    db.init_db()

    with db.connect() as conn:
        user = conn.execute(
            "SELECT id, username, display_name, is_admin FROM users WHERE username = ?",
            (db.DEFAULT_USER_NAME,),
        ).fetchone()
        profile = conn.execute(
            """
            SELECT profiles.name, profiles.display_name, profiles.user_id
            FROM profiles
            JOIN users ON users.id = profiles.user_id
            WHERE profiles.name = ? AND users.username = ?
            """,
            (db.DEFAULT_PROFILE_NAME, db.DEFAULT_USER_NAME),
        ).fetchone()

    assert user is not None
    assert user["username"] == "default"
    assert user["display_name"] == "Default"
    assert user["is_admin"] == 0

    assert profile is not None
    assert profile["name"] == "default"
    assert profile["display_name"] == "Default"
    assert profile["user_id"] == user["id"]


def test_get_default_profile_id_is_stable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    first_id = db.get_default_profile_id()
    second_id = db.get_default_profile_id()

    assert first_id == second_id

    with db.connect() as conn:
        profile_count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    assert profile_count == 1


def test_init_db_is_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    db.init_db()
    db.init_db()

    with db.connect() as conn:
        profile_count = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        migration_count = conn.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0]

    assert profile_count == 1
    assert migration_count == 1


def test_connect_enables_foreign_keys(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)

    with db.connect() as conn:
        foreign_keys_enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]

    assert foreign_keys_enabled == 1


def test_init_db_accepts_explicit_database_path(tmp_path: Path) -> None:
    db_file = tmp_path / "custom.db"

    db.init_db(db_file)

    assert db_file.exists()


def test_existing_profiles_are_migrated_to_default_user(
    tmp_path: Path,
) -> None:
    db_file = tmp_path / "legacy.db"

    with db.connect(db_file) as conn:
        conn.executescript(
            """
            CREATE TABLE schema_migrations (
                name TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            );

            CREATE TABLE profiles (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                display_name TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                CHECK (length(trim(name)) > 0)
            );
            """
        )
        conn.execute(
            """
            INSERT INTO profiles (id, name, display_name, created_at, updated_at)
            VALUES (10, 'work', 'Work', '2026-01-01T00:00:00+00:00', '2026-01-01T00:00:00+00:00')
            """
        )
        conn.commit()

    db.init_db(db_file)

    with db.connect(db_file) as conn:
        user = db.get_user_by_username(conn, db.DEFAULT_USER_NAME)
        profile = db.get_profile_by_name(
            conn,
            "work",
            user_id=user["id"] if user else None,
        )

    assert user is not None
    assert profile is not None
    assert profile["id"] == 10
    assert profile["user_id"] == user["id"]


def test_default_web_user_is_not_admin_without_password(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FLUXTUNER_DATA_DIR", str(tmp_path))

    from fluxtuner.core import db

    with db.connect() as conn:
        db.create_schema(conn)
        db.ensure_profile_user_schema(conn)
        user_id = db.ensure_default_user(conn)
        conn.commit()

        user = conn.execute(
            """
            SELECT username, is_admin, is_active, password_hash
            FROM users
            WHERE id = ?
            """,
            (user_id,),
        ).fetchone()

    assert user is not None
    assert user["username"] == db.DEFAULT_USER_NAME
    assert user["is_admin"] == 0
    assert user["is_active"] == 1
    assert user["password_hash"] is None


def test_init_db_records_current_schema_version(tmp_path) -> None:
    db_file = tmp_path / "fluxtuner.sqlite3"

    db.init_db(db_file)

    with db.connect(db_file) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]

    assert version == db.CURRENT_SCHEMA_VERSION


def test_current_schema_version_does_not_rerun_compatibility_migrations(
    tmp_path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "fluxtuner.sqlite3"

    db.init_db(db_file)

    approval_calls = 0
    profile_calls = 0

    original_approval = db.ensure_user_approval_schema
    original_profile = db.ensure_profile_user_schema

    def counted_approval(conn):
        nonlocal approval_calls
        approval_calls += 1
        return original_approval(conn)

    def counted_profile(conn):
        nonlocal profile_calls
        profile_calls += 1
        return original_profile(conn)

    monkeypatch.setattr(db, "ensure_user_approval_schema", counted_approval)
    monkeypatch.setattr(db, "ensure_profile_user_schema", counted_profile)

    db.init_db(db_file)

    assert approval_calls == 0
    assert profile_calls == 0


def test_init_db_rejects_newer_schema_version(tmp_path) -> None:
    db_file = tmp_path / "fluxtuner.sqlite3"

    with db.connect(db_file) as conn:
        conn.execute(f"PRAGMA user_version = {db.CURRENT_SCHEMA_VERSION + 1}")

    with pytest.raises(RuntimeError, match="newer than supported"):
        db.init_db(db_file)


def test_schema_upgrade_clears_retired_password_change_requests_once(
    tmp_path,
    monkeypatch,
) -> None:
    db_file = tmp_path / "fluxtuner.sqlite3"

    # Build a representative pre-versioned database using the current
    # compatibility schema, then mark it as legacy user_version=0.
    db.init_db(db_file)

    with db.connect(db_file) as conn:
        user_id = db.get_or_create_user(
            conn,
            "alice",
            password_hash="legacy-user-password-hash",
            is_active=True,
        )
        now = db.utc_now()
        conn.execute(
            """
            INSERT INTO web_password_change_requests (
                user_id,
                password_hash,
                note,
                status,
                created_at,
                expires_at
            )
            VALUES (?, ?, ?, 'pending', ?, ?)
            """,
            (
                user_id,
                "retired-password-change-hash",
                "legacy request",
                now,
                now,
            ),
        )
        conn.execute("PRAGMA user_version = 0")
        conn.commit()

    db.init_db(db_file)

    with db.connect(db_file) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        legacy_rows = conn.execute("SELECT COUNT(*) FROM web_password_change_requests").fetchone()[
            0
        ]
        user = db.get_user_by_username(conn, "alice")

    assert version == db.CURRENT_SCHEMA_VERSION
    assert legacy_rows == 0
    assert user is not None
    assert user["password_hash"] == "legacy-user-password-hash"

    # Once current, initialization must not execute the legacy cleanup again.
    execute_calls = 0
    original_connect = db.connect

    class CountingConnection:
        def __init__(self, connection):
            self._connection = connection

        def __enter__(self):
            self._connection.__enter__()
            return self

        def __exit__(self, *args):
            return self._connection.__exit__(*args)

        def __getattr__(self, name):
            return getattr(self._connection, name)

        def execute(self, sql, parameters=()):
            nonlocal execute_calls
            if "DELETE FROM web_password_change_requests" in sql:
                execute_calls += 1
            return self._connection.execute(sql, parameters)

    def counted_connect(path=None):
        return CountingConnection(original_connect(path))

    monkeypatch.setattr(db, "connect", counted_connect)

    db.init_db(db_file)

    assert execute_calls == 0


def test_current_schema_version_skips_migration_runner(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "fluxtuner.sqlite3"
    db.init_db(db_path)

    migration_calls = 0
    original_migrate_schema = db.migrate_schema

    def counted_migrate_schema(conn):
        nonlocal migration_calls
        migration_calls += 1
        return original_migrate_schema(conn)

    monkeypatch.setattr(db, "migrate_schema", counted_migrate_schema)

    db.init_db(db_path)

    assert migration_calls == 0


def test_get_default_profile_id_does_not_run_schema_helpers_directly(
    tmp_path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    def forbidden_schema_helper(*_args, **_kwargs):
        raise AssertionError("managed default ran schema compatibility helper directly")

    monkeypatch.setattr(db, "create_schema", forbidden_schema_helper)
    monkeypatch.setattr(db, "ensure_user_approval_schema", forbidden_schema_helper)
    monkeypatch.setattr(db, "ensure_profile_user_schema", forbidden_schema_helper)

    profile_id = db.get_default_profile_id()

    assert profile_id > 0


def test_migrate_schema_holds_write_lock_until_version_is_recorded(
    tmp_path,
) -> None:
    db_path = tmp_path / "fluxtuner.db"
    statements: list[str] = []

    with db.connect(db_path) as conn:
        conn.set_trace_callback(statements.append)
        db.migrate_schema(conn)

    normalized = [" ".join(statement.upper().split()) for statement in statements]

    begin_index = next(
        index for index, statement in enumerate(normalized) if statement == "BEGIN IMMEDIATE"
    )
    version_read_index = next(
        index for index, statement in enumerate(normalized) if statement == "PRAGMA USER_VERSION"
    )
    version_write_index = next(
        index
        for index, statement in enumerate(normalized)
        if statement.startswith("PRAGMA USER_VERSION =")
    )
    commit_index = next(
        index for index, statement in enumerate(normalized) if statement == "COMMIT"
    )

    assert begin_index < version_read_index
    assert version_read_index < version_write_index
    assert version_write_index < commit_index


def test_concurrent_init_db_migrates_fresh_database_once(
    tmp_path,
) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    db_path = tmp_path / "fluxtuner.db"
    barrier = Barrier(2)

    def initialize() -> None:
        barrier.wait(timeout=5)
        db.init_db(db_path)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(initialize),
            executor.submit(initialize),
        ]
        for future in futures:
            future.result(timeout=10)

    with db.connect(db_path) as conn:
        stored_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        migration_count = int(
            conn.execute(
                """
                SELECT COUNT(*)
                FROM schema_migrations
                WHERE name = ?
                """,
                (db.SCHEMA_MIGRATION_NAME,),
            ).fetchone()[0]
        )
        default_user_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM users WHERE username = ?",
                (db.DEFAULT_USER_NAME,),
            ).fetchone()[0]
        )
        default_profile_count = int(
            conn.execute(
                "SELECT COUNT(*) FROM profiles WHERE name = ?",
                (db.DEFAULT_PROFILE_NAME,),
            ).fetchone()[0]
        )

    assert stored_version == db.CURRENT_SCHEMA_VERSION
    assert migration_count == 1
    assert default_user_count == 1
    assert default_profile_count == 1


def test_schema_v1_upgrades_to_v2_with_auth_retention_indexes(tmp_path) -> None:
    db_path = tmp_path / "fluxtuner.db"

    with db.connect(db_path) as conn:
        db.create_schema(conn)
        db.ensure_user_approval_schema(conn)
        db.ensure_profile_user_schema(conn)

        # create_schema() represents the current schema, so remove the v2-only
        # indexes to construct a representative schema-v1 database.
        conn.execute("DROP INDEX IF EXISTS idx_web_login_attempts_attempted_at")
        conn.execute("DROP INDEX IF EXISTS idx_web_recovery_attempts_attempted_at")
        conn.execute("PRAGMA user_version = 1")
        conn.commit()

    db.init_db(db_path)

    with db.connect(db_path) as conn:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        indexes = {
            str(row["name"])
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            ).fetchall()
        }

    assert version == db.CURRENT_SCHEMA_VERSION
    assert "idx_web_login_attempts_attempted_at" in indexes
    assert "idx_web_recovery_attempts_attempted_at" in indexes


def test_fresh_database_contains_auth_retention_indexes(tmp_path) -> None:
    db_path = tmp_path / "fluxtuner.db"

    db.init_db(db_path)

    with db.connect(db_path) as conn:
        indexes = {
            str(row["name"])
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            ).fetchall()
        }

    assert "idx_web_login_attempts_attempted_at" in indexes
    assert "idx_web_recovery_attempts_attempted_at" in indexes


def test_schema_v0_upgrades_through_v3(tmp_path) -> None:
    db_path = tmp_path / "fluxtuner.db"

    with db.connect(db_path) as conn:
        db.create_schema(conn)
        db.ensure_user_approval_schema(conn)
        db.ensure_profile_user_schema(conn)
        conn.execute("PRAGMA user_version = 0")
        conn.commit()

    db.init_db(db_path)

    with db.connect(db_path) as conn:
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        indexes = {
            str(row["name"])
            for row in conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'index'
                """
            ).fetchall()
        }

    assert version == db.CURRENT_SCHEMA_VERSION
    assert version == 3
    assert "idx_web_login_attempts_attempted_at" in indexes
    assert "idx_web_recovery_attempts_attempted_at" in indexes
