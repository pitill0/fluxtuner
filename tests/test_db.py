# SPDX-License-Identifier: MIT

from pathlib import Path

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
            "favorites",
            "history_entries",
            "playlist_stations",
            "playlists",
            "profiles",
            "schema_migrations",
            "stations",
            "users",
            "web_login_attempts",
            "web_password_change_requests",
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


def test_get_or_create_user_is_case_insensitive(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        first_id = db.get_or_create_user(conn, "Laura", display_name="Laura")
        second_id = db.get_or_create_user(conn, "laura", display_name="Other")

    assert first_id == second_id


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
