# SPDX-License-Identifier: MIT
#
# FluxTuner core storage remains MIT for local application use.
# Web/server-specific user, profile-ownership, login-attempt and session
# storage behavior in this file is additionally governed by LICENSE-WEB
# when used to operate, host, sell or monetize FluxTuner Web/server features.

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fluxtuner.core.stations import station_key, station_name
from fluxtuner.paths import data_file

DB_FILE = data_file("fluxtuner.db")
DEFAULT_USER_NAME = "default"
DEFAULT_PROFILE_NAME = "default"
SCHEMA_MIGRATION_NAME = "schema_v5"
APPROVAL_APPROVED = "approved"
APPROVAL_PENDING = "pending"
APPROVAL_REJECTED = "rejected"
APPROVAL_DISABLED = "disabled"
APPROVAL_STATUSES = {
    APPROVAL_APPROVED,
    APPROVAL_PENDING,
    APPROVAL_REJECTED,
    APPROVAL_DISABLED,
}
ACCOUNT_CHANGE_PENDING = "pending"
ACCOUNT_CHANGE_APPROVED = "approved"
ACCOUNT_CHANGE_REJECTED = "rejected"
ACCOUNT_CHANGE_EXPIRED = "expired"
ACCOUNT_CHANGE_STATUSES = {
    ACCOUNT_CHANGE_PENDING,
    ACCOUNT_CHANGE_APPROVED,
    ACCOUNT_CHANGE_REJECTED,
    ACCOUNT_CHANGE_EXPIRED,
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a SQLite connection for FluxTuner library storage."""
    path = db_path or DB_FILE
    path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | None = None) -> None:
    """Create the FluxTuner SQLite schema and default user/profile if needed."""
    with connect(db_path) as conn:
        create_schema(conn)
        ensure_user_approval_schema(conn)
        ensure_profile_user_schema(conn)
        ensure_default_user(conn)
        ensure_default_profile(conn)
        conn.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (name, applied_at)
            VALUES (?, ?)
            """,
            (SCHEMA_MIGRATION_NAME, utc_now()),
        )
        conn.commit()


def create_schema(conn: sqlite3.Connection) -> None:
    """Create all storage-foundation tables."""
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            display_name TEXT,
            password_hash TEXT,
            is_admin INTEGER NOT NULL DEFAULT 0,
            is_active INTEGER NOT NULL DEFAULT 1,
            approval_status TEXT NOT NULL DEFAULT 'approved',
            signup_note TEXT,
            reviewed_at TEXT,
            reviewed_by_user_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK (length(trim(username)) > 0),
            CHECK (is_admin IN (0, 1)),
            CHECK (is_active IN (0, 1)),
            CHECK (approval_status IN ('approved', 'pending', 'rejected', 'disabled'))
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_nocase
        ON users(lower(username));

        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            display_name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            CHECK (length(trim(name)) > 0)
        );
        CREATE TABLE IF NOT EXISTS web_sessions (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            revoked_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            CHECK (length(trim(token_hash)) > 0)
        );

        CREATE INDEX IF NOT EXISTS idx_web_sessions_user_id
        ON web_sessions(user_id);

        CREATE INDEX IF NOT EXISTS idx_web_sessions_expires_at
        ON web_sessions(expires_at);

        CREATE TABLE IF NOT EXISTS web_login_attempts (
            id INTEGER PRIMARY KEY,
            normalized_username TEXT NOT NULL,
            client_key TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0,
            attempted_at TEXT NOT NULL,
            CHECK (length(trim(normalized_username)) > 0),
            CHECK (length(trim(client_key)) > 0),
            CHECK (success IN (0, 1))
        );

        CREATE INDEX IF NOT EXISTS idx_web_login_attempts_lookup
        ON web_login_attempts(normalized_username, client_key, attempted_at);

        CREATE TABLE IF NOT EXISTS web_password_change_requests (
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            password_hash TEXT NOT NULL,
            note TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            resolved_at TEXT,
            resolved_by_user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (resolved_by_user_id) REFERENCES users(id) ON DELETE SET NULL,
            CHECK (length(trim(password_hash)) > 0),
            CHECK (status IN ('pending', 'approved', 'rejected', 'expired'))
        );

        CREATE INDEX IF NOT EXISTS idx_web_password_change_requests_user_status
        ON web_password_change_requests(user_id, status);

        CREATE INDEX IF NOT EXISTS idx_web_password_change_requests_status_created
        ON web_password_change_requests(status, created_at DESC);

        CREATE TABLE IF NOT EXISTS stations (
            id INTEGER PRIMARY KEY,
            station_key TEXT NOT NULL UNIQUE,
            stationuuid TEXT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            url_resolved TEXT,
            homepage TEXT,
            favicon TEXT,
            country TEXT,
            countrycode TEXT,
            language TEXT,
            tags TEXT,
            codec TEXT,
            bitrate INTEGER,
            metadata_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK (length(trim(station_key)) > 0),
            CHECK (length(trim(url)) > 0)
        );

        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY,
            profile_id INTEGER NOT NULL,
            station_id INTEGER NOT NULL,
            custom_name TEXT,
            favorite_tags_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE (profile_id, station_id),
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS history_entries (
            id INTEGER PRIMARY KEY,
            profile_id INTEGER NOT NULL,
            station_id INTEGER NOT NULL,
            last_played_at TEXT NOT NULL,
            play_count INTEGER NOT NULL DEFAULT 1,
            station_snapshot_json TEXT NOT NULL,
            UNIQUE (profile_id, station_id),
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY,
            profile_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (profile_id) REFERENCES profiles(id) ON DELETE CASCADE,
            CHECK (length(trim(name)) > 0)
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_playlists_profile_name_nocase
        ON playlists(profile_id, lower(name));

        CREATE TABLE IF NOT EXISTS playlist_stations (
            id INTEGER PRIMARY KEY,
            playlist_id INTEGER NOT NULL,
            station_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE (playlist_id, station_id),
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (station_id) REFERENCES stations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_favorites_profile_id
        ON favorites(profile_id);

        CREATE INDEX IF NOT EXISTS idx_history_profile_last_played
        ON history_entries(profile_id, last_played_at DESC);

        CREATE INDEX IF NOT EXISTS idx_playlist_stations_playlist_position
        ON playlist_stations(playlist_id, position);
        """
    )


def _column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    columns = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {str(column["name"]) for column in columns}


def _validate_approval_status(status: str) -> str:
    clean_status = str(status or "").strip().lower()
    if clean_status not in APPROVAL_STATUSES:
        raise ValueError(f"Invalid approval status: {status}")
    return clean_status


def active_for_approval_status(status: str) -> bool:
    """Return whether a user with the approval status may authenticate."""
    return _validate_approval_status(status) == APPROVAL_APPROVED


def ensure_user_approval_schema(conn: sqlite3.Connection) -> None:
    """Ensure web users have explicit approval-state metadata."""
    columns = _column_names(conn, "users")

    if "approval_status" not in columns:
        conn.execute(
            "ALTER TABLE users ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'approved'"
        )
        columns.add("approval_status")

    if "signup_note" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN signup_note TEXT")
        columns.add("signup_note")

    if "reviewed_at" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN reviewed_at TEXT")
        columns.add("reviewed_at")

    if "reviewed_by_user_id" not in columns:
        conn.execute("ALTER TABLE users ADD COLUMN reviewed_by_user_id INTEGER")
        columns.add("reviewed_by_user_id")

    conn.execute(
        """
        UPDATE users
        SET approval_status = CASE
            WHEN is_active = 1 THEN ?
            ELSE ?
        END
        WHERE approval_status IS NULL OR trim(approval_status) = ''
        """,
        (APPROVAL_APPROVED, APPROVAL_DISABLED),
    )

    conn.execute(
        """
        UPDATE users
        SET is_active = CASE
            WHEN approval_status = ? THEN 1
            ELSE 0
        END
        WHERE approval_status IN (?, ?, ?, ?)
        """,
        (
            APPROVAL_APPROVED,
            APPROVAL_APPROVED,
            APPROVAL_PENDING,
            APPROVAL_REJECTED,
            APPROVAL_DISABLED,
        ),
    )


def normalize_username(username: str) -> str:
    """Normalize a username for storage and lookup."""
    return username.strip()


def user_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a public user dictionary from a SQLite row."""
    return {
        "id": int(row["id"]),
        "username": str(row["username"]),
        "display_name": str(row["display_name"] or row["username"]),
        "password_hash": (str(row["password_hash"]) if row["password_hash"] is not None else None),
        "is_admin": bool(row["is_admin"]),
        "is_active": bool(row["is_active"]),
        "approval_status": str(row["approval_status"]),
        "signup_note": (str(row["signup_note"]) if row["signup_note"] is not None else None),
        "reviewed_at": (str(row["reviewed_at"]) if row["reviewed_at"] is not None else None),
        "reviewed_by_user_id": (
            int(row["reviewed_by_user_id"]) if row["reviewed_by_user_id"] is not None else None
        ),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def get_user_by_username(
    conn: sqlite3.Connection,
    username: str,
) -> dict[str, Any] | None:
    """Return a user by username using case-insensitive lookup."""
    clean_username = normalize_username(username)
    if not clean_username:
        return None

    row = conn.execute(
        """
        SELECT
            id,
            username,
            display_name,
            password_hash,
            is_admin,
            is_active,
            approval_status,
            signup_note,
            reviewed_at,
            reviewed_by_user_id,
            created_at,
            updated_at
        FROM users
        WHERE lower(username) = lower(?)
        """,
        (clean_username,),
    ).fetchone()

    if row is None:
        return None

    return user_from_row(row)


def get_or_create_user(
    conn: sqlite3.Connection,
    username: str,
    *,
    display_name: str | None = None,
    password_hash: str | None = None,
    is_admin: bool = False,
    is_active: bool = True,
    approval_status: str | None = None,
    signup_note: str | None = None,
) -> int:
    """Return a user id, creating the user if needed."""
    clean_username = normalize_username(username)
    if not clean_username:
        raise ValueError("Username is required.")

    existing = get_user_by_username(conn, clean_username)
    if existing is not None:
        return int(existing["id"])

    now = utc_now()
    clean_display_name = _clean_text(display_name) or clean_username
    clean_approval_status = _validate_approval_status(
        approval_status or (APPROVAL_APPROVED if is_active else APPROVAL_DISABLED)
    )
    resolved_is_active = active_for_approval_status(clean_approval_status)

    cursor = conn.execute(
        """
        INSERT INTO users (
            username,
            display_name,
            password_hash,
            is_admin,
            is_active,
            approval_status,
            signup_note,
            reviewed_at,
            reviewed_by_user_id,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            clean_username,
            clean_display_name,
            password_hash,
            1 if is_admin else 0,
            1 if resolved_is_active else 0,
            clean_approval_status,
            _clean_text(signup_note),
            None,
            None,
            now,
            now,
        ),
    )

    user_id = cursor.lastrowid
    if user_id is None:
        raise RuntimeError("Could not create user.")

    return int(user_id)


def ensure_default_user(conn: sqlite3.Connection | None = None) -> int:
    """Return the default web user id, creating it when needed."""
    if conn is None:
        with connect() as managed_conn:
            create_schema(managed_conn)
            ensure_user_approval_schema(managed_conn)
            ensure_profile_user_schema(managed_conn)
            user_id = ensure_default_user(managed_conn)
            managed_conn.commit()
            return user_id

    user_id = get_or_create_user(
        conn,
        DEFAULT_USER_NAME,
        display_name="Default",
        is_admin=False,
        is_active=True,
    )

    conn.execute(
        """
        UPDATE users
        SET
            is_admin = 0,
            approval_status = ?,
            is_active = 1,
            updated_at = ?
        WHERE username = ?
          AND is_admin != 0
          AND (password_hash IS NULL OR password_hash = '')
        """,
        (APPROVAL_APPROVED, utc_now(), DEFAULT_USER_NAME),
    )

    return user_id


def create_pending_user(
    conn: sqlite3.Connection,
    username: str,
    *,
    password_hash: str,
    display_name: str | None = None,
    signup_note: str | None = None,
) -> int:
    """Create an inactive user pending administrator approval."""
    return get_or_create_user(
        conn,
        username,
        display_name=display_name,
        password_hash=password_hash,
        is_admin=False,
        is_active=False,
        approval_status=APPROVAL_PENDING,
        signup_note=signup_note,
    )


def set_user_approval_status(
    conn: sqlite3.Connection,
    user_id: int,
    status: str,
    *,
    reviewed_by_user_id: int | None = None,
) -> None:
    """Update a user's approval status and effective active flag."""
    clean_status = _validate_approval_status(status)
    conn.execute(
        """
        UPDATE users
        SET
            approval_status = ?,
            is_active = ?,
            reviewed_at = ?,
            reviewed_by_user_id = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            clean_status,
            1 if active_for_approval_status(clean_status) else 0,
            utc_now(),
            reviewed_by_user_id,
            utc_now(),
            user_id,
        ),
    )


def _validate_password_change_status(status: str) -> str:
    clean_status = str(status or "").strip().lower()
    if clean_status not in ACCOUNT_CHANGE_STATUSES:
        raise ValueError(f"Invalid password change request status: {status}")
    return clean_status


def password_change_request_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a password change request dictionary from a SQLite row."""
    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "username": str(row["username"]),
        "display_name": str(row["display_name"] or row["username"]),
        "password_hash": str(row["password_hash"]),
        "note": (str(row["note"]) if row["note"] is not None else None),
        "status": str(row["status"]),
        "created_at": str(row["created_at"]),
        "expires_at": str(row["expires_at"]),
        "resolved_at": (str(row["resolved_at"]) if row["resolved_at"] is not None else None),
        "resolved_by_user_id": (
            int(row["resolved_by_user_id"]) if row["resolved_by_user_id"] is not None else None
        ),
    }


def upsert_pending_password_change_request(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    password_hash: str,
    note: str | None = None,
    created_at: str | None = None,
    expires_at: str,
) -> int:
    """Create or replace the active pending password change request for a user."""
    now = created_at or utc_now()
    clean_note = _clean_text(note)

    row = conn.execute(
        """
        SELECT id
        FROM web_password_change_requests
        WHERE user_id = ? AND status = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (user_id, ACCOUNT_CHANGE_PENDING),
    ).fetchone()

    if row is not None:
        request_id = int(row["id"])
        conn.execute(
            """
            UPDATE web_password_change_requests
            SET
                password_hash = ?,
                note = ?,
                created_at = ?,
                expires_at = ?,
                resolved_at = NULL,
                resolved_by_user_id = NULL
            WHERE id = ?
            """,
            (password_hash, clean_note, now, expires_at, request_id),
        )
        return request_id

    cursor = conn.execute(
        """
        INSERT INTO web_password_change_requests (
            user_id,
            password_hash,
            note,
            status,
            created_at,
            expires_at,
            resolved_at,
            resolved_by_user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
        """,
        (user_id, password_hash, clean_note, ACCOUNT_CHANGE_PENDING, now, expires_at),
    )

    request_id = cursor.lastrowid
    if request_id is None:
        raise RuntimeError("Could not create password change request.")
    return int(request_id)


def list_password_change_requests(
    conn: sqlite3.Connection,
    *,
    status: str | None = ACCOUNT_CHANGE_PENDING,
) -> list[dict[str, Any]]:
    """Return password change requests joined with their target users."""
    base_query = """
        SELECT
            r.id,
            r.user_id,
            u.username,
            u.display_name,
            r.password_hash,
            r.note,
            r.status,
            r.created_at,
            r.expires_at,
            r.resolved_at,
            r.resolved_by_user_id
        FROM web_password_change_requests r
        JOIN users u ON u.id = r.user_id
    """
    if status is None:
        query = (
            base_query
            + """
        ORDER BY r.created_at DESC, r.id DESC
        """
        )
        params: tuple[Any, ...] = ()
    else:
        query = (
            base_query
            + """
        WHERE r.status = ?
        ORDER BY r.created_at DESC, r.id DESC
        """
        )
        params = (_validate_password_change_status(status),)

    rows = conn.execute(query, params).fetchall()

    return [password_change_request_from_row(row) for row in rows]


def user_has_pending_password_change_request(
    conn: sqlite3.Connection,
    user_id: int,
    *,
    now: str | None = None,
) -> bool:
    """Return whether an active pending password change request locks login."""
    row = conn.execute(
        """
        SELECT 1
        FROM web_password_change_requests
        WHERE user_id = ?
          AND status = ?
          AND expires_at > ?
        LIMIT 1
        """,
        (user_id, ACCOUNT_CHANGE_PENDING, now or utc_now()),
    ).fetchone()
    return row is not None


def get_password_change_request(
    conn: sqlite3.Connection,
    request_id: int,
) -> dict[str, Any] | None:
    """Return one password change request joined with its target user."""
    row = conn.execute(
        """
        SELECT
            r.id,
            r.user_id,
            u.username,
            u.display_name,
            r.password_hash,
            r.note,
            r.status,
            r.created_at,
            r.expires_at,
            r.resolved_at,
            r.resolved_by_user_id
        FROM web_password_change_requests r
        JOIN users u ON u.id = r.user_id
        WHERE r.id = ?
        """,
        (request_id,),
    ).fetchone()

    if row is None:
        return None
    return password_change_request_from_row(row)


def set_password_change_request_status(
    conn: sqlite3.Connection,
    request_id: int,
    status: str,
    *,
    resolved_by_user_id: int | None = None,
) -> None:
    """Resolve a password change request with a final status."""
    clean_status = _validate_password_change_status(status)
    conn.execute(
        """
        UPDATE web_password_change_requests
        SET
            status = ?,
            resolved_at = ?,
            resolved_by_user_id = ?
        WHERE id = ?
        """,
        (clean_status, utc_now(), resolved_by_user_id, request_id),
    )


def list_users(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all known users."""
    rows = conn.execute(
        """
        SELECT
            id,
            username,
            display_name,
            password_hash,
            is_admin,
            is_active,
            approval_status,
            signup_note,
            reviewed_at,
            reviewed_by_user_id,
            created_at,
            updated_at
        FROM users
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()

    return [user_from_row(row) for row in rows]


def _profile_table_has_user_id(conn: sqlite3.Connection) -> bool:
    columns = conn.execute("PRAGMA table_info(profiles)").fetchall()
    return any(str(column["name"]) == "user_id" for column in columns)


def _ensure_no_duplicate_profile_names_for_user(
    conn: sqlite3.Connection,
    user_id: int,
) -> None:
    duplicates = conn.execute(
        """
        SELECT lower(name) AS normalized_name, COUNT(*) AS count
        FROM profiles
        WHERE user_id = ?
        GROUP BY lower(name)
        HAVING COUNT(*) > 1
        """,
        (user_id,),
    ).fetchall()

    if duplicates:
        duplicate_names = ", ".join(str(row["normalized_name"]) for row in duplicates)
        raise RuntimeError(
            "Cannot create profile ownership index because duplicate profile "
            f"names exist for the same user: {duplicate_names}"
        )


def ensure_profile_user_schema(conn: sqlite3.Connection) -> None:
    """Ensure profiles have user ownership and a per-user name constraint."""
    ensure_user_approval_schema(conn)
    default_user_id = ensure_default_user(conn)

    if not _profile_table_has_user_id(conn):
        conn.commit()
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute(
                """
                CREATE TABLE profiles_new (
                    id INTEGER PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    display_name TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    CHECK (length(trim(name)) > 0)
                )
                """
            )
            conn.execute(
                """
                INSERT INTO profiles_new (
                    id,
                    user_id,
                    name,
                    display_name,
                    created_at,
                    updated_at
                )
                SELECT
                    id,
                    ?,
                    name,
                    display_name,
                    created_at,
                    updated_at
                FROM profiles
                """,
                (default_user_id,),
            )
            conn.execute("DROP TABLE profiles")
            conn.execute("ALTER TABLE profiles_new RENAME TO profiles")
            conn.commit()
        finally:
            conn.execute("PRAGMA foreign_keys = ON")

    _ensure_no_duplicate_profile_names_for_user(conn, default_user_id)

    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_user_name_nocase
        ON profiles(user_id, lower(name))
        """
    )

    foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
    if foreign_key_errors:
        raise RuntimeError("Profile user migration left invalid foreign keys.")


def ensure_default_profile(
    conn: sqlite3.Connection | None = None,
    *,
    user_id: int | None = None,
) -> int:
    """Return the default profile id for a user, creating it when needed."""
    if conn is None:
        with connect() as managed_conn:
            create_schema(managed_conn)
            ensure_user_approval_schema(managed_conn)
            ensure_profile_user_schema(managed_conn)
            profile_id = ensure_default_profile(managed_conn, user_id=user_id)
            managed_conn.commit()
            return profile_id

    resolved_user_id = user_id if user_id is not None else ensure_default_user(conn)

    row = conn.execute(
        """
        SELECT id FROM profiles
        WHERE user_id = ? AND lower(name) = lower(?)
        """,
        (resolved_user_id, DEFAULT_PROFILE_NAME),
    ).fetchone()

    if row is not None:
        return int(row["id"])

    now = utc_now()
    cursor = conn.execute(
        """
        INSERT INTO profiles (
            user_id,
            name,
            display_name,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (resolved_user_id, DEFAULT_PROFILE_NAME, "Default", now, now),
    )

    created_profile_id = cursor.lastrowid
    if created_profile_id is None:
        raise RuntimeError("Could not create default profile.")

    return int(created_profile_id)


def get_default_profile_id() -> int:
    """Return the internal default profile id."""
    return ensure_default_profile()


def table_names(conn: sqlite3.Connection) -> set[str]:
    """Return user-defined SQLite table names."""
    rows = conn.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()
    return {str(row["name"]) for row in rows}


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    clean_value = str(value).strip()
    return clean_value or None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def station_metadata(station: dict[str, Any]) -> str:
    """Serialize a station dict for lossless-ish metadata preservation."""
    return json.dumps(
        station,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def upsert_station(conn: sqlite3.Connection, station: dict[str, Any]) -> int:
    """Insert or update a station and return its database id.

    FluxTuner 0.6.0 identifies saved stations by the playable URL returned by
    station_key(). SQLite keeps that same key so existing favorites, history and
    playlists can migrate without changing user-visible behavior.
    """
    key = station_key(station)
    if not key:
        raise ValueError("Station URL is required.")

    now = utc_now()
    url = _clean_text(station.get("url")) or key
    url_resolved = _clean_text(station.get("url_resolved")) or url

    conn.execute(
        """
        INSERT INTO stations (
            station_key,
            stationuuid,
            name,
            url,
            url_resolved,
            homepage,
            favicon,
            country,
            countrycode,
            language,
            tags,
            codec,
            bitrate,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(station_key) DO UPDATE SET
            stationuuid = excluded.stationuuid,
            name = excluded.name,
            url = excluded.url,
            url_resolved = excluded.url_resolved,
            homepage = excluded.homepage,
            favicon = excluded.favicon,
            country = excluded.country,
            countrycode = excluded.countrycode,
            language = excluded.language,
            tags = excluded.tags,
            codec = excluded.codec,
            bitrate = excluded.bitrate,
            metadata_json = excluded.metadata_json,
            updated_at = excluded.updated_at
        """,
        (
            key,
            _clean_text(station.get("stationuuid")),
            station_name(station),
            url,
            url_resolved,
            _clean_text(station.get("homepage")),
            _clean_text(station.get("favicon")),
            _clean_text(station.get("country")),
            _clean_text(station.get("countrycode")),
            _clean_text(station.get("language")),
            _clean_text(station.get("tags")),
            _clean_text(station.get("codec")),
            _safe_int(station.get("bitrate")),
            station_metadata(station),
            now,
            now,
        ),
    )

    row = conn.execute(
        "SELECT id FROM stations WHERE station_key = ?",
        (key,),
    ).fetchone()

    if row is None:
        raise RuntimeError("Could not persist station.")

    return int(row["id"])


def station_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a FluxTuner station dict from a stations row."""
    try:
        metadata = json.loads(str(row["metadata_json"] or "{}"))
    except json.JSONDecodeError:
        metadata = {}

    if not isinstance(metadata, dict):
        metadata = {}

    station = dict(metadata)

    station["stationuuid"] = row["stationuuid"] or station.get("stationuuid") or ""
    station["name"] = row["name"] or station.get("name") or "Unknown station"
    station["url"] = row["url"] or station.get("url") or ""
    station["url_resolved"] = row["url_resolved"] or station.get("url_resolved") or station["url"]
    station["homepage"] = row["homepage"] or station.get("homepage") or ""
    station["favicon"] = row["favicon"] or station.get("favicon") or ""
    station["country"] = row["country"] or station.get("country") or ""
    station["countrycode"] = row["countrycode"] or station.get("countrycode") or ""
    station["language"] = row["language"] or station.get("language") or ""
    station["tags"] = row["tags"] or station.get("tags") or ""
    station["codec"] = row["codec"] or station.get("codec") or ""
    station["bitrate"] = _safe_int(row["bitrate"])

    return station


def get_station_by_key(conn: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    """Load a station by FluxTuner station key."""
    row = conn.execute(
        "SELECT * FROM stations WHERE station_key = ?",
        (key,),
    ).fetchone()

    if row is None:
        return None

    return station_from_row(row)


def normalize_favorite_tags(value: Any) -> list[str]:
    """Return normalized user-defined favorite tags."""
    if not isinstance(value, list):
        return []
    return sorted({str(tag).strip() for tag in value if str(tag).strip()})


def favorite_tags_to_json(value: Any) -> str:
    """Serialize favorite tags using the current FluxTuner normalization rules."""
    return json.dumps(
        normalize_favorite_tags(value),
        ensure_ascii=False,
        sort_keys=True,
    )


def favorite_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a favorite station dict from a joined favorite/station row."""
    favorite = station_from_row(row)

    custom_name = _clean_text(row["custom_name"])
    favorite["custom_name"] = custom_name

    try:
        raw_tags = json.loads(str(row["favorite_tags_json"] or "[]"))
    except json.JSONDecodeError:
        raw_tags = []

    favorite["favorite_tags"] = normalize_favorite_tags(raw_tags)

    if not favorite.get("url_resolved"):
        favorite["url_resolved"] = favorite.get("url")

    return favorite


def list_favorites(
    conn: sqlite3.Connection,
    profile_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return favorites for a profile as FluxTuner station dictionaries."""
    active_profile_id = profile_id or ensure_default_profile(conn)

    rows = conn.execute(
        """
        SELECT
            stations.*,
            favorites.custom_name,
            favorites.favorite_tags_json
        FROM favorites
        JOIN stations ON stations.id = favorites.station_id
        WHERE favorites.profile_id = ?
        ORDER BY favorites.created_at ASC, favorites.id ASC
        """,
        (active_profile_id,),
    ).fetchall()

    return [favorite_from_row(row) for row in rows]


def add_favorite_record(
    conn: sqlite3.Connection,
    station: dict[str, Any],
    profile_id: int | None = None,
) -> bool:
    """Add a favorite for a profile.

    Returns False when the station is already a favorite.
    """
    active_profile_id = profile_id or ensure_default_profile(conn)
    station_id = upsert_station(conn, station)
    now = utc_now()

    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO favorites (
            profile_id,
            station_id,
            custom_name,
            favorite_tags_json,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            active_profile_id,
            station_id,
            _clean_text(station.get("custom_name")),
            favorite_tags_to_json(station.get("favorite_tags")),
            now,
            now,
        ),
    )

    return cursor.rowcount > 0


def remove_favorite_record(
    conn: sqlite3.Connection,
    key: str,
    profile_id: int | None = None,
) -> bool:
    """Remove a favorite by station key or raw URL."""
    clean_key = key.strip()
    if not clean_key:
        return False

    active_profile_id = profile_id or ensure_default_profile(conn)

    cursor = conn.execute(
        """
        DELETE FROM favorites
        WHERE profile_id = ?
          AND station_id IN (
              SELECT id
              FROM stations
              WHERE station_key = ?
                 OR url = ?
                 OR url_resolved = ?
          )
        """,
        (active_profile_id, clean_key, clean_key, clean_key),
    )

    return cursor.rowcount > 0


def update_favorite_record(
    conn: sqlite3.Connection,
    key: str,
    *,
    custom_name: Any = ...,
    favorite_tags: Any = ...,
    profile_id: int | None = None,
) -> bool:
    """Update editable favorite metadata for a saved station."""
    clean_key = key.strip()
    if not clean_key:
        return False

    if custom_name is ... and favorite_tags is ...:
        return False

    active_profile_id = profile_id or ensure_default_profile(conn)
    now = utc_now()

    if custom_name is not ... and favorite_tags is not ...:
        cursor = conn.execute(
            """
            UPDATE favorites
            SET custom_name = ?,
                favorite_tags_json = ?,
                updated_at = ?
            WHERE profile_id = ?
              AND station_id IN (
                  SELECT id
                  FROM stations
                  WHERE station_key = ?
                     OR url = ?
                     OR url_resolved = ?
              )
            """,
            (
                _clean_text(custom_name),
                favorite_tags_to_json(favorite_tags or []),
                now,
                active_profile_id,
                clean_key,
                clean_key,
                clean_key,
            ),
        )
        return cursor.rowcount > 0

    if custom_name is not ...:
        cursor = conn.execute(
            """
            UPDATE favorites
            SET custom_name = ?,
                updated_at = ?
            WHERE profile_id = ?
              AND station_id IN (
                  SELECT id
                  FROM stations
                  WHERE station_key = ?
                     OR url = ?
                     OR url_resolved = ?
              )
            """,
            (
                _clean_text(custom_name),
                now,
                active_profile_id,
                clean_key,
                clean_key,
                clean_key,
            ),
        )
        return cursor.rowcount > 0

    cursor = conn.execute(
        """
        UPDATE favorites
        SET favorite_tags_json = ?,
            updated_at = ?
        WHERE profile_id = ?
          AND station_id IN (
              SELECT id
              FROM stations
              WHERE station_key = ?
                 OR url = ?
                 OR url_resolved = ?
          )
        """,
        (
            favorite_tags_to_json(favorite_tags or []),
            now,
            active_profile_id,
            clean_key,
            clean_key,
            clean_key,
        ),
    )
    return cursor.rowcount > 0


def replace_favorites(
    conn: sqlite3.Connection,
    favorites: list[dict[str, Any]],
    profile_id: int | None = None,
) -> None:
    """Replace all favorites for a profile with the provided station dictionaries."""
    active_profile_id = profile_id or ensure_default_profile(conn)

    conn.execute(
        "DELETE FROM favorites WHERE profile_id = ?",
        (active_profile_id,),
    )

    for favorite in favorites:
        if station_key(favorite):
            add_favorite_record(conn, favorite, active_profile_id)


def history_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a history station dict from a joined history/station row.

    History entries are snapshots. FluxTuner 0.6.0 returned the saved JSON item
    mostly as-is, so migrated history should not grow station defaults such as
    codec, bitrate or url_resolved unless they were already present.
    """
    try:
        snapshot = json.loads(str(row["station_snapshot_json"] or "{}"))
    except json.JSONDecodeError:
        snapshot = {}

    if isinstance(snapshot, dict) and snapshot:
        return dict(snapshot)

    station = station_from_row(row)
    station["last_played_at"] = str(row["last_played_at"] or "")
    station["play_count"] = _safe_int(row["play_count"])

    return station


def list_history(
    conn: sqlite3.Connection,
    *,
    limit: int = 100,
    profile_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return profile history, newest first."""
    active_profile_id = profile_id or ensure_default_profile(conn)
    safe_limit = max(0, int(limit))

    rows = conn.execute(
        """
        SELECT
            stations.*,
            history_entries.last_played_at,
            history_entries.play_count,
            history_entries.station_snapshot_json
        FROM history_entries
        JOIN stations ON stations.id = history_entries.station_id
        WHERE history_entries.profile_id = ?
        ORDER BY history_entries.last_played_at DESC, history_entries.id DESC
        LIMIT ?
        """,
        (active_profile_id, safe_limit),
    ).fetchall()

    return [history_from_row(row) for row in rows]


def add_history_record(
    conn: sqlite3.Connection,
    station: dict[str, Any],
    *,
    played_at: str | None = None,
    profile_id: int | None = None,
) -> None:
    """Insert or update one history entry for a station.

    FluxTuner history keeps one row per station and increments play_count on
    repeated plays. It is not a raw play-event log.
    """
    key = station_key(station)
    if not key:
        return

    active_profile_id = profile_id or ensure_default_profile(conn)
    station_id = upsert_station(conn, station)
    timestamp = played_at or utc_now()

    previous = conn.execute(
        """
        SELECT play_count
        FROM history_entries
        WHERE profile_id = ?
          AND station_id = ?
        """,
        (active_profile_id, station_id),
    ).fetchone()
    play_count = _safe_int(previous["play_count"]) + 1 if previous is not None else 1

    snapshot_data = dict(station)
    snapshot_data["last_played_at"] = timestamp
    snapshot_data["play_count"] = play_count
    snapshot = station_metadata(snapshot_data)

    conn.execute(
        """
        INSERT INTO history_entries (
            profile_id,
            station_id,
            last_played_at,
            play_count,
            station_snapshot_json
        )
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(profile_id, station_id) DO UPDATE SET
            last_played_at = excluded.last_played_at,
            play_count = excluded.play_count,
            station_snapshot_json = excluded.station_snapshot_json
        """,
        (
            active_profile_id,
            station_id,
            timestamp,
            play_count,
            snapshot,
        ),
    )


def replace_history(
    conn: sqlite3.Connection,
    history: list[dict[str, Any]],
    *,
    limit: int = 100,
    profile_id: int | None = None,
) -> None:
    """Replace profile history with the provided station dictionaries."""
    active_profile_id = profile_id or ensure_default_profile(conn)

    conn.execute(
        "DELETE FROM history_entries WHERE profile_id = ?",
        (active_profile_id,),
    )

    for item in history[:limit]:
        if not station_key(item):
            continue

        station_id = upsert_station(conn, item)
        last_played_at = str(item.get("last_played_at") or utc_now())

        conn.execute(
            """
            INSERT OR REPLACE INTO history_entries (
                profile_id,
                station_id,
                last_played_at,
                play_count,
                station_snapshot_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                active_profile_id,
                station_id,
                last_played_at,
                max(1, _safe_int(item.get("play_count"))),
                station_metadata(item),
            ),
        )


def clear_history_records(
    conn: sqlite3.Connection,
    profile_id: int | None = None,
) -> None:
    """Clear profile history."""
    active_profile_id = profile_id or ensure_default_profile(conn)
    conn.execute(
        "DELETE FROM history_entries WHERE profile_id = ?",
        (active_profile_id,),
    )


def _clean_playlist_name(name: str) -> str:
    return name.strip()


def _playlist_id(
    conn: sqlite3.Connection,
    name: str,
    profile_id: int,
) -> int | None:
    clean_name = _clean_playlist_name(name)
    if not clean_name:
        return None

    row = conn.execute(
        """
        SELECT id
        FROM playlists
        WHERE profile_id = ?
          AND lower(name) = lower(?)
        """,
        (profile_id, clean_name),
    ).fetchone()

    if row is None:
        return None

    return int(row["id"])


def _playlist_station_keys(
    conn: sqlite3.Connection,
    playlist_id: int,
) -> list[str]:
    rows = conn.execute(
        """
        SELECT stations.station_key
        FROM playlist_stations
        JOIN stations ON stations.id = playlist_stations.station_id
        WHERE playlist_stations.playlist_id = ?
        ORDER BY playlist_stations.position ASC, playlist_stations.id ASC
        """,
        (playlist_id,),
    ).fetchall()

    return [str(row["station_key"]) for row in rows]


def list_playlists(
    conn: sqlite3.Connection,
    profile_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return playlists using the public FluxTuner station_keys shape."""
    active_profile_id = profile_id or ensure_default_profile(conn)

    rows = conn.execute(
        """
        SELECT id, name
        FROM playlists
        WHERE profile_id = ?
        ORDER BY created_at ASC, id ASC
        """,
        (active_profile_id,),
    ).fetchall()

    return [
        {
            "name": str(row["name"]),
            "station_keys": _playlist_station_keys(conn, int(row["id"])),
        }
        for row in rows
    ]


def get_playlist_record(
    conn: sqlite3.Connection,
    name: str,
    profile_id: int | None = None,
) -> dict[str, Any] | None:
    """Return one playlist using the public FluxTuner station_keys shape."""
    active_profile_id = profile_id or ensure_default_profile(conn)
    playlist_id = _playlist_id(conn, name, active_profile_id)

    if playlist_id is None:
        return None

    row = conn.execute(
        "SELECT name FROM playlists WHERE id = ?",
        (playlist_id,),
    ).fetchone()

    if row is None:
        return None

    return {
        "name": str(row["name"]),
        "station_keys": _playlist_station_keys(conn, playlist_id),
    }


def create_playlist_record(
    conn: sqlite3.Connection,
    name: str,
    profile_id: int | None = None,
) -> bool:
    """Create a playlist, returning False if it already exists."""
    clean_name = _clean_playlist_name(name)
    if not clean_name:
        return False

    active_profile_id = profile_id or ensure_default_profile(conn)
    now = utc_now()

    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO playlists (
            profile_id,
            name,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (active_profile_id, clean_name, now, now),
    )

    return cursor.rowcount > 0


def delete_playlist_record(
    conn: sqlite3.Connection,
    name: str,
    profile_id: int | None = None,
) -> bool:
    """Delete a playlist by name."""
    clean_name = _clean_playlist_name(name)
    if not clean_name:
        return False

    active_profile_id = profile_id or ensure_default_profile(conn)

    cursor = conn.execute(
        """
        DELETE FROM playlists
        WHERE profile_id = ?
          AND lower(name) = lower(?)
        """,
        (active_profile_id, clean_name),
    )

    return cursor.rowcount > 0


def add_station_to_playlist_record(
    conn: sqlite3.Connection,
    name: str,
    station: dict[str, Any],
    profile_id: int | None = None,
) -> bool:
    """Add a station key to a playlist, creating the playlist if needed."""
    clean_name = _clean_playlist_name(name)
    key = station_key(station)

    if not clean_name or not key:
        return False

    active_profile_id = profile_id or ensure_default_profile(conn)
    playlist_id = _playlist_id(conn, clean_name, active_profile_id)

    if playlist_id is None:
        create_playlist_record(conn, clean_name, active_profile_id)
        playlist_id = _playlist_id(conn, clean_name, active_profile_id)

    if playlist_id is None:
        raise RuntimeError("Could not create playlist.")

    station_id = upsert_station(conn, station)

    next_position_row = conn.execute(
        """
        SELECT COALESCE(MAX(position), -1) + 1 AS next_position
        FROM playlist_stations
        WHERE playlist_id = ?
        """,
        (playlist_id,),
    ).fetchone()
    next_position = int(next_position_row["next_position"] if next_position_row else 0)

    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO playlist_stations (
            playlist_id,
            station_id,
            position,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (playlist_id, station_id, next_position, utc_now()),
    )

    return cursor.rowcount > 0


def remove_station_from_playlist_record(
    conn: sqlite3.Connection,
    name: str,
    station: dict[str, Any],
    profile_id: int | None = None,
) -> bool:
    """Remove a station key from a playlist."""
    clean_name = _clean_playlist_name(name)
    key = station_key(station)

    if not clean_name or not key:
        return False

    active_profile_id = profile_id or ensure_default_profile(conn)
    playlist_id = _playlist_id(conn, clean_name, active_profile_id)

    if playlist_id is None:
        return False

    cursor = conn.execute(
        """
        DELETE FROM playlist_stations
        WHERE playlist_id = ?
          AND station_id IN (
              SELECT id
              FROM stations
              WHERE station_key = ?
                 OR url = ?
                 OR url_resolved = ?
          )
        """,
        (playlist_id, key, key, key),
    )

    return cursor.rowcount > 0


def replace_playlists(
    conn: sqlite3.Connection,
    playlists: list[dict[str, Any]],
    profile_id: int | None = None,
) -> None:
    """Replace all playlists for a profile using the public station_keys shape."""
    active_profile_id = profile_id or ensure_default_profile(conn)

    conn.execute(
        "DELETE FROM playlists WHERE profile_id = ?",
        (active_profile_id,),
    )

    for playlist in playlists:
        name = _clean_playlist_name(str(playlist.get("name") or ""))
        if not name:
            continue

        create_playlist_record(conn, name, active_profile_id)

        station_keys = playlist.get("station_keys", [])
        if not isinstance(station_keys, list):
            continue

        for key in station_keys:
            clean_key = str(key).strip()
            if not clean_key:
                continue

            add_station_to_playlist_record(
                conn,
                name,
                {"name": clean_key, "url": clean_key},
                active_profile_id,
            )


def normalize_profile_name(name: str) -> str:
    """Normalize a profile name for storage and lookup."""
    return name.strip()


def get_profile_by_name(
    conn: sqlite3.Connection,
    name: str,
    *,
    user_id: int | None = None,
) -> dict[str, Any] | None:
    """Return a profile by name for a user."""
    clean_name = normalize_profile_name(name)
    if not clean_name:
        return None

    resolved_user_id = user_id if user_id is not None else ensure_default_user(conn)

    row = conn.execute(
        """
        SELECT id, user_id, name, display_name, created_at, updated_at
        FROM profiles
        WHERE user_id = ? AND lower(name) = lower(?)
        """,
        (resolved_user_id, clean_name),
    ).fetchone()

    if row is None:
        return None

    return {
        "id": int(row["id"]),
        "user_id": int(row["user_id"]),
        "name": str(row["name"]),
        "display_name": str(row["display_name"] or row["name"]),
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
    }


def get_or_create_profile(
    conn: sqlite3.Connection,
    name: str,
    *,
    display_name: str | None = None,
    user_id: int | None = None,
) -> int:
    """Return a profile id for a user, creating the profile if needed."""
    clean_name = normalize_profile_name(name)
    if not clean_name:
        raise ValueError("Profile name is required.")

    resolved_user_id = user_id if user_id is not None else ensure_default_user(conn)

    existing = get_profile_by_name(conn, clean_name, user_id=resolved_user_id)
    if existing is not None:
        return int(existing["id"])

    now = utc_now()
    clean_display_name = _clean_text(display_name) or clean_name

    cursor = conn.execute(
        """
        INSERT INTO profiles (
            user_id,
            name,
            display_name,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            resolved_user_id,
            clean_name,
            clean_display_name,
            now,
            now,
        ),
    )

    profile_id = cursor.lastrowid
    if profile_id is None:
        raise RuntimeError("Could not create profile.")

    return int(profile_id)


def list_profiles(
    conn: sqlite3.Connection,
    *,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    """Return known profiles, optionally scoped to a user."""
    if user_id is None:
        rows = conn.execute(
            """
            SELECT id, user_id, name, display_name, created_at, updated_at
            FROM profiles
            ORDER BY created_at ASC, id ASC
            """
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT id, user_id, name, display_name, created_at, updated_at
            FROM profiles
            WHERE user_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (user_id,),
        ).fetchall()

    return [
        {
            "id": int(row["id"]),
            "user_id": int(row["user_id"]),
            "name": str(row["name"]),
            "display_name": str(row["display_name"] or row["name"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }
        for row in rows
    ]
