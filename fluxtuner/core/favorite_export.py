"""Read-only, owner-scoped favorites for portable station exports."""

from __future__ import annotations

import sqlite3

from fluxtuner.core.m3u_import import M3UEntry


def resolve_favorite_entries(
    conn: sqlite3.Connection,
    *,
    user_id: int,
    profile_id: int,
    station_id: int | None = None,
) -> tuple[M3UEntry, ...]:
    """Return an owned profile's favorites in order, optionally one station."""
    if type(user_id) is not int or user_id <= 0 or type(profile_id) is not int or profile_id <= 0:
        raise ValueError("An existing user and profile are required.")
    if station_id is not None and (type(station_id) is not int or station_id <= 0):
        raise ValueError("Station is unavailable.")

    rows = conn.execute(
        """
        SELECT s.station_key, s.name, f.custom_name
        FROM favorites AS f
        JOIN profiles AS p ON p.id = f.profile_id
        JOIN stations AS s ON s.id = f.station_id
        WHERE p.user_id = ? AND p.id = ?
          AND (? IS NULL OR f.station_id = ?)
        ORDER BY f.created_at ASC, f.id ASC
        """,
        (user_id, profile_id, station_id, station_id),
    ).fetchall()
    if not rows:
        raise ValueError("Favorites are unavailable.")
    return tuple(
        M3UEntry(name=str(row["custom_name"] or row["name"]), url=str(row["station_key"]))
        for row in rows
    )
