# SPDX-License-Identifier: MIT
#
# FluxTuner core storage remains MIT for local application use.
# Web/server-specific public activity stats behavior in this file is
# additionally governed by LICENSE-WEB when used to operate, host, sell or
# monetize FluxTuner Web/server features.

from __future__ import annotations

import sqlite3
from typing import Any


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def public_activity_stats(
    conn: sqlite3.Connection,
    *,
    top_limit: int = 3,
) -> dict[str, Any]:
    """Return anonymous global activity stats safe for public display."""
    safe_limit = max(0, int(top_limit))

    top_rows = conn.execute(
        """
        SELECT
            COALESCE(NULLIF(trim(stations.name), ''), 'Unknown station') AS name,
            SUM(history_entries.play_count) AS play_count,
            MAX(history_entries.last_played_at) AS last_played_at
        FROM history_entries
        JOIN stations ON stations.id = history_entries.station_id
        GROUP BY history_entries.station_id
        ORDER BY
            SUM(history_entries.play_count) DESC,
            MAX(history_entries.last_played_at) DESC,
            name COLLATE NOCASE ASC
        LIMIT ?
        """,
        (safe_limit,),
    ).fetchall()

    totals_row = conn.execute(
        """
        SELECT
            COALESCE(SUM(history_entries.play_count), 0) AS plays_count,
            (SELECT COUNT(*) FROM favorites) AS favorites_count,
            (SELECT COUNT(*) FROM playlists) AS playlists_count,
            (
                SELECT COUNT(*)
                FROM users
                WHERE is_active = 1
                  AND approval_status = 'approved'
                  AND password_hash IS NOT NULL
                  AND trim(password_hash) != ''
            ) AS users_count
        FROM history_entries
        """
    ).fetchone()

    return {
        "top_stations": [
            {
                "name": str(row["name"] or "Unknown station"),
                "play_count": _safe_int(row["play_count"]),
            }
            for row in top_rows
        ],
        "totals": {
            "plays": _safe_int(totals_row["plays_count"]),
            "favorites": _safe_int(totals_row["favorites_count"]),
            "playlists": _safe_int(totals_row["playlists_count"]),
            "users": _safe_int(totals_row["users_count"]),
        },
    }
