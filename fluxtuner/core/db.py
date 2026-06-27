from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fluxtuner.core.stations import station_key, station_name
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
) -> dict[str, Any] | None:
    """Return a profile by name."""
    clean_name = normalize_profile_name(name)
    if not clean_name:
        return None

    row = conn.execute(
        """
        SELECT id, name, display_name, created_at, updated_at
        FROM profiles
        WHERE lower(name) = lower(?)
        """,
        (clean_name,),
    ).fetchone()

    if row is None:
        return None

    return {
        "id": int(row["id"]),
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
) -> int:
    """Return a profile id, creating the profile if needed."""
    clean_name = normalize_profile_name(name)
    if not clean_name:
        raise ValueError("Profile name is required.")

    existing = get_profile_by_name(conn, clean_name)
    if existing is not None:
        return int(existing["id"])

    now = utc_now()
    clean_display_name = _clean_text(display_name) or clean_name

    cursor = conn.execute(
        """
        INSERT INTO profiles (
            name,
            display_name,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
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


def list_profiles(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Return all known profiles."""
    rows = conn.execute(
        """
        SELECT id, name, display_name, created_at, updated_at
        FROM profiles
        ORDER BY created_at ASC, id ASC
        """
    ).fetchall()

    return [
        {
            "id": int(row["id"]),
            "name": str(row["name"]),
            "display_name": str(row["display_name"] or row["name"]),
            "created_at": str(row["created_at"]),
            "updated_at": str(row["updated_at"]),
        }
        for row in rows
    ]
