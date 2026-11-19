# SPDX-License-Identifier: MIT

"""Internal station momentum calculations using anonymous UTC-day aggregates.

This module does not define a public API or make any publication/privacy decision.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta
from typing import Any


def seven_day_station_trends(
    conn: sqlite3.Connection,
    *,
    as_of: date | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Rank stations growing against the preceding seven UTC calendar days.

    The current window includes ``as_of`` and its preceding six days. Momentum
    is the absolute difference in plays between the two equal-length windows.
    Flat and declining stations are deliberately excluded. No user/profile data
    or historical profile play counts are involved.
    """
    if isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    safe_limit = max(0, int(limit))
    if safe_limit == 0:
        return []

    reference = as_of if as_of is not None else datetime.now(UTC).date()
    if not isinstance(reference, date) or isinstance(reference, datetime):
        raise TypeError("as_of must be a date")
    recent_start = reference - timedelta(days=6)
    previous_start = recent_start - timedelta(days=7)
    next_day = reference + timedelta(days=1)

    rows = conn.execute(
        """
        SELECT
            stations.id AS station_id,
            COALESCE(NULLIF(trim(stations.name), ''), 'Unknown station') AS name,
            SUM(CASE WHEN daily.day_utc >= ? THEN daily.play_count ELSE 0 END)
                AS recent_plays,
            SUM(CASE WHEN daily.day_utc < ? THEN daily.play_count ELSE 0 END)
                AS previous_plays
        FROM station_daily_plays AS daily
        JOIN stations ON stations.id = daily.station_id
        WHERE daily.day_utc >= ? AND daily.day_utc < ?
        GROUP BY stations.id
        HAVING recent_plays > previous_plays
        ORDER BY
            (recent_plays - previous_plays) DESC,
            recent_plays DESC,
            name COLLATE NOCASE ASC,
            stations.id ASC
        LIMIT ?
        """,
        (
            recent_start.isoformat(),
            recent_start.isoformat(),
            previous_start.isoformat(),
            next_day.isoformat(),
            safe_limit,
        ),
    ).fetchall()
    return [
        {
            "station_id": int(row["station_id"]),
            "name": str(row["name"]),
            "recent_plays": int(row["recent_plays"]),
            "previous_plays": int(row["previous_plays"]),
            "growth": int(row["recent_plays"]) - int(row["previous_plays"]),
        }
        for row in rows
    ]
