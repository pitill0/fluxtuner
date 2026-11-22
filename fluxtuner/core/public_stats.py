# SPDX-License-Identifier: MIT
#
# FluxTuner core storage remains MIT for local application use.
# Web/server-specific public activity stats behavior in this file is
# additionally governed by LICENSE-WEB when used to operate, host, sell or
# monetize FluxTuner Web/server features.

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from fluxtuner.core.public_station_visibility import (
    public_station_urls_safe,
)

MIN_PUBLIC_LISTENERS = 3
PUBLIC_PLAYS_RETENTION_DAYS = 35


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def public_top_station_rows(conn: sqlite3.Connection, *, top_limit: int = 3) -> list[sqlite3.Row]:
    """Rank only publishable stations, with live consent and URL validation."""
    safe_limit = max(0, int(top_limit))
    if not safe_limit:
        return []
    cutoff = (
        datetime.now(UTC).date() - timedelta(days=PUBLIC_PLAYS_RETENTION_DAYS - 1)
    ).isoformat()
    rows = conn.execute(
        """
        SELECT
            s.id AS station_id,
            s.favicon AS favicon,
            s.url AS url,
            s.url_resolved AS url_resolved,
            COALESCE(NULLIF(trim(s.name), ''), 'Unknown station') AS name,
            SUM(plays.play_count) AS play_count,
            MAX(plays.last_counted_at) AS last_played_at
        FROM web_public_play_contributions AS plays
        JOIN stations AS s ON s.id = plays.station_id
        JOIN users AS listeners ON listeners.id = plays.user_id
        WHERE plays.day_utc >= ?
          AND listeners.is_active = 1
          AND listeners.approval_status = 'approved'
          AND EXISTS (
              SELECT 1 FROM public_station_opt_ins AS o
              JOIN favorites AS f ON f.id = o.favorite_id
              JOIN profiles AS p ON p.id = f.profile_id
              JOIN users AS u ON u.id = p.user_id
              WHERE f.station_id = s.id
                AND u.is_active = 1 AND u.approval_status = 'approved'
          )
        GROUP BY s.id
        HAVING COUNT(DISTINCT plays.user_id) >= ?
        ORDER BY
            SUM(plays.play_count) DESC,
            MAX(plays.last_counted_at) DESC,
            name COLLATE NOCASE ASC
        """,
        (cutoff, MIN_PUBLIC_LISTENERS),
    )
    eligible: list[sqlite3.Row] = []
    for row in rows:
        if public_station_urls_safe(row["url"], row["url_resolved"]):
            eligible.append(row)
            if len(eligible) == safe_limit:
                break
    return eligible[:safe_limit]


def public_activity_stats(
    conn: sqlite3.Connection,
    *,
    top_limit: int = 3,
) -> dict[str, Any]:
    """Return anonymous global activity stats without private station identities."""
    top_rows = public_top_station_rows(conn, top_limit=top_limit)

    cutoff = (
        datetime.now(UTC).date() - timedelta(days=PUBLIC_PLAYS_RETENTION_DAYS - 1)
    ).isoformat()
    totals_row = conn.execute(
        """
        SELECT
            (
                SELECT COALESCE(SUM(plays.play_count), 0)
                FROM web_public_play_contributions AS plays
                JOIN users AS u ON u.id = plays.user_id
                WHERE plays.day_utc >= ?
                  AND u.is_active = 1
                  AND u.approval_status = 'approved'
            ) AS plays_count,
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
        """,
        (cutoff,),
    ).fetchone()

    return {
        "top_stations": [
            {
                "name": str(row["name"] or "Unknown station"),
                "play_count": _safe_int(row["play_count"]),
                **(
                    {"artwork_url": f"/api/public/stations/{int(row['station_id'])}/artwork"}
                    if str(row["favicon"] or "").strip()
                    else {}
                ),
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
