from __future__ import annotations

import secrets
import sqlite3
from typing import Any

from fluxtuner.core.favorites import load_favorites
from fluxtuner.core.stations import station_key, upsert_station


def get_tag_counts(*, profile_name: str | None = None) -> list[tuple[str, int]]:
    """Return favorite tag counts sorted by tag name."""
    counts: dict[str, int] = {}
    for favorite in load_favorites(profile_name=profile_name):
        for tag in favorite.get("favorite_tags", []):
            clean_tag = str(tag).strip()
            if clean_tag:
                counts[clean_tag] = counts.get(clean_tag, 0) + 1
    return sorted(counts.items(), key=lambda item: item[0].lower())


def get_all_tags(*, profile_name: str | None = None) -> list[str]:
    """Return all favorite tags sorted by name."""
    return [tag for tag, _count in get_tag_counts(profile_name=profile_name)]


def get_by_tag(tag: str, *, profile_name: str | None = None) -> list[dict[str, Any]]:
    """Return favorites that include the given user tag."""
    clean_tag = tag.strip().lower()
    if not clean_tag:
        return []
    return [
        favorite
        for favorite in load_favorites(profile_name=profile_name)
        if clean_tag in {str(item).lower() for item in favorite.get("favorite_tags", [])}
    ]


def random_by_tag(tag: str, *, profile_name: str | None = None) -> dict[str, Any] | None:
    """Return a random favorite from a tag-based dynamic playlist."""
    stations = get_by_tag(tag, profile_name=profile_name)
    if not stations:
        return None
    return secrets.choice(stations)


def _default_profile_id(conn: sqlite3.Connection, profile_id: int | None) -> int:
    if profile_id:
        return profile_id

    from fluxtuner.core import db

    return db.ensure_default_profile(conn)


def _utc_now() -> str:
    from fluxtuner.core import db

    return db.utc_now()


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
    active_profile_id = _default_profile_id(conn, profile_id)

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
    active_profile_id = _default_profile_id(conn, profile_id)
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

    active_profile_id = _default_profile_id(conn, profile_id)
    now = _utc_now()

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

    active_profile_id = _default_profile_id(conn, profile_id)

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

    active_profile_id = _default_profile_id(conn, profile_id)
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
        (playlist_id, station_id, next_position, _utc_now()),
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

    active_profile_id = _default_profile_id(conn, profile_id)
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
    active_profile_id = _default_profile_id(conn, profile_id)

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
