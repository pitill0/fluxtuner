"""Read-only resolution of profile playlists for portable export."""

from __future__ import annotations

import sqlite3

from fluxtuner.core.m3u_import import M3UEntry


def resolve_playlist_entries(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    profile_id: int,
    playlist_name: str,
) -> tuple[M3UEntry, ...]:
    """Resolve an owned playlist in stored order without changing the database.

    A missing playlist, unknown profile or foreign profile produces the
    same error. The caller must supply an authenticated user identity.
    """
    if type(user_id) is not int or user_id <= 0 or type(profile_id) is not int or profile_id <= 0:
        raise ValueError("An existing user and profile are required.")

    if not isinstance(playlist_name, str):
        raise ValueError("Playlist name is required.")

    name = playlist_name.strip()
    if not name:
        raise ValueError("Playlist name is required.")

    rows = conn.execute(
        """
        SELECT
            pl.id AS playlist_id,
            s.station_key,
            s.name,
            f.custom_name
        FROM playlists AS pl
        JOIN profiles AS p ON p.id = pl.profile_id
        LEFT JOIN playlist_stations AS ps
          ON ps.playlist_id = pl.id
        LEFT JOIN stations AS s ON s.id = ps.station_id
        LEFT JOIN favorites AS f
          ON f.station_id = s.id
         AND f.profile_id = pl.profile_id
        WHERE p.user_id = ?
          AND p.id = ?
          AND lower(pl.name) = lower(?)
        ORDER BY ps.position ASC, ps.id ASC
        """,
        (user_id, profile_id, name),
    ).fetchall()

    if not rows:
        raise ValueError("Playlist is unavailable.")

    return tuple(
        M3UEntry(
            name=str(row["custom_name"] or row["name"]),
            url=str(row["station_key"]),
        )
        for row in rows
        if row["station_key"] is not None
    )
