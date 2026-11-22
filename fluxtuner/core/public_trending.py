# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Conservative public station momentum selection.

Activity thresholds reduce sparse-data exposure but cannot establish a minimum
number of distinct listeners: daily aggregates contain no listener identities.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta

from fluxtuner.core.public_station_visibility import (
    public_station_urls_safe,
)

MIN_RECENT_PLAYS = 10
MIN_DISTINCT_LISTENERS = 3
MIN_ACTIVE_DAYS = 3
MIN_ELIGIBLE_STATIONS = 3
PUBLIC_TREND_LIMIT = 3


def public_station_trends(
    conn: sqlite3.Connection, *, as_of: date | None = None
) -> dict[str, object]:
    """Return name-only trends for completed UTC days, without playback totals.

    ``as_of`` is the final day of the seven-day comparison window. A public
    caller should leave it unset to exclude the current incomplete UTC day.
    """
    final_day = as_of if as_of is not None else datetime.now(UTC).date() - timedelta(days=1)
    if not isinstance(final_day, date) or isinstance(final_day, datetime):
        raise TypeError("as_of must be a date")
    recent_start = final_day - timedelta(days=6)
    previous_start = recent_start - timedelta(days=7)
    next_day = final_day + timedelta(days=1)

    rows = conn.execute(
        """
        SELECT
            s.id AS station_id,
            s.url AS url,
            s.url_resolved AS url_resolved,
            COALESCE(NULLIF(trim(s.name), ''), 'Unknown station') AS name,
            SUM(CASE WHEN daily.day_utc >= ? THEN daily.play_count ELSE 0 END)
                AS recent_plays,
            SUM(CASE WHEN daily.day_utc < ? THEN daily.play_count ELSE 0 END)
                AS previous_plays,
            COUNT(DISTINCT CASE WHEN daily.day_utc >= ? THEN daily.day_utc END)
                AS active_days,
            COUNT(DISTINCT CASE WHEN daily.day_utc >= ? THEN daily.user_id END)
                AS distinct_listeners
        FROM web_public_play_contributions AS daily
        JOIN stations AS s ON s.id = daily.station_id
        JOIN users AS listeners ON listeners.id = daily.user_id
        WHERE daily.day_utc >= ? AND daily.day_utc < ?
          AND listeners.is_active = 1
          AND listeners.approval_status = 'approved'
          AND (
              EXISTS (
                  SELECT 1 FROM public_station_opt_ins AS o
                  JOIN favorites AS f ON f.id = o.favorite_id
                  JOIN profiles AS p ON p.id = f.profile_id
                  JOIN users AS u ON u.id = p.user_id
                  WHERE f.station_id = s.id
                    AND u.is_active = 1 AND u.approval_status = 'approved'
              )
          )
        GROUP BY s.id
        HAVING recent_plays >= ? AND active_days >= ?
           AND distinct_listeners >= ?
           AND recent_plays > previous_plays
        ORDER BY
            (recent_plays - previous_plays) DESC,
            recent_plays DESC,
            name COLLATE NOCASE ASC,
            s.id ASC
        """,
        (
            recent_start.isoformat(),
            recent_start.isoformat(),
            recent_start.isoformat(),
            recent_start.isoformat(),
            previous_start.isoformat(),
            next_day.isoformat(),
            MIN_RECENT_PLAYS,
            MIN_ACTIVE_DAYS,
            MIN_DISTINCT_LISTENERS,
        ),
    )

    names = []
    for row in rows:
        if public_station_urls_safe(row["url"], row["url_resolved"]):
            names.append({"name": str(row["name"])})
            if len(names) == PUBLIC_TREND_LIMIT:
                break
    if len(names) < MIN_ELIGIBLE_STATIONS:
        names = []
    return {"stations": names, "period_end_utc": final_day.isoformat()}
