from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from fluxtuner.paths import data_file

DB_FILE = data_file("fluxtuner.db")
DEFAULT_PROFILE_NAME = "default"
SCHEMA_MIGRATION_NAME = "schema_v1"


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
    """Create the FluxTuner SQLite schema and default profile if needed."""
    with connect(db_path) as conn:
        create_schema(conn)
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

        CREATE TABLE IF NOT EXISTS profiles (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            display_name TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK (length(trim(name)) > 0)
        );

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


def ensure_default_profile(conn: sqlite3.Connection | None = None) -> int:
    """Return the default profile id, creating it when needed."""
    if conn is None:
        with connect() as managed_conn:
            create_schema(managed_conn)
            profile_id = ensure_default_profile(managed_conn)
            managed_conn.commit()
            return profile_id

    row = conn.execute(
        "SELECT id FROM profiles WHERE name = ?",
        (DEFAULT_PROFILE_NAME,),
    ).fetchone()

    if row is not None:
        return int(row["id"])

    now = utc_now()
    cursor = conn.execute(
        """
        INSERT INTO profiles (name, display_name, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (DEFAULT_PROFILE_NAME, "Default", now, now),
    )

    created_profile_id = cursor.lastrowid
    if created_profile_id is None:
        raise RuntimeError("Could not create default profile.")

    return created_profile_id


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
