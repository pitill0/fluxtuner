# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Privacy-conscious, name-only public genre popularity from daily counts."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from fluxtuner.core.public_station_visibility import public_station_urls_safe

MIN_PLAYS = 20
MIN_STATIONS = 3
MIN_ACTIVE_DAYS = 3
MIN_DISTINCT_LISTENERS = 3
PUBLIC_GENRE_LIMIT = 5

# Only these canonical, non-identifying categories may leave the server.
# Personal favorite tags and arbitrary station tags are never published.
_GENRE_ALIASES = {
    "ambient": "Ambient",
    "blues": "Blues",
    "classical": "Classical",
    "country": "Country",
    "dance": "Dance",
    "disco": "Disco",
    "electronic": "Electronic",
    "electronica": "Electronic",
    "electro": "Electronic",
    "funk": "Funk",
    "hip hop": "Hip-Hop",
    "hip-hop": "Hip-Hop",
    "hiphop": "Hip-Hop",
    "house": "House",
    "jazz": "Jazz",
    "latin": "Latin",
    "metal": "Metal",
    "pop": "Pop",
    "reggae": "Reggae",
    "rock": "Rock",
    "soul": "Soul",
    "techno": "Techno",
}


def _genres(value: object) -> set[str]:
    """Recognize complete comma-separated tags, never substrings or private labels."""
    return {
        canonical
        for raw in str(value or "").split(",")
        if (canonical := _GENRE_ALIASES.get(" ".join(raw.casefold().split()))) is not None
    }


def public_popular_genres(
    conn: sqlite3.Connection, *, as_of: date | None = None
) -> dict[str, object]:
    """Rank categories using completed UTC days and omit sparse categories.

    Require distinct listeners and explicit station publication consent.
    """
    final_day = as_of if as_of is not None else datetime.now(UTC).date() - timedelta(days=1)
    if not isinstance(final_day, date) or isinstance(final_day, datetime):
        raise TypeError("as_of must be a date")
    start = final_day - timedelta(days=6)
    next_day = final_day + timedelta(days=1)
    rows = conn.execute(
        """
        SELECT
            daily.station_id,
            daily.user_id,
            daily.day_utc,
            daily.play_count,
            stations.tags,
            stations.url,
            stations.url_resolved
        FROM web_public_play_contributions AS daily
        JOIN stations ON stations.id = daily.station_id
        JOIN users AS listeners ON listeners.id = daily.user_id
        WHERE daily.day_utc >= ? AND daily.day_utc < ?
          AND daily.play_count > 0
          AND listeners.is_active = 1
          AND listeners.approval_status = 'approved'
          AND EXISTS (
              SELECT 1 FROM public_station_opt_ins AS o
              JOIN favorites AS f ON f.id = o.favorite_id
              JOIN profiles AS p ON p.id = f.profile_id
              JOIN users AS u ON u.id = p.user_id
              WHERE f.station_id = stations.id
                AND u.is_active = 1
                AND u.approval_status = 'approved'
          )
        """,
        (start.isoformat(), next_day.isoformat()),
    )

    plays: dict[str, int] = defaultdict(int)
    stations: dict[str, set[int]] = defaultdict(set)
    days: dict[str, set[str]] = defaultdict(set)
    listeners: dict[str, set[int]] = defaultdict(set)
    for row in rows:
        if not public_station_urls_safe(row["url"], row["url_resolved"]):
            continue
        for genre in _genres(row["tags"]):
            plays[genre] += int(row["play_count"])
            stations[genre].add(int(row["station_id"]))
            days[genre].add(str(row["day_utc"]))
            listeners[genre].add(int(row["user_id"]))

    eligible = [
        genre
        for genre, count in plays.items()
        if count >= MIN_PLAYS
        and len(stations[genre]) >= MIN_STATIONS
        and len(days[genre]) >= MIN_ACTIVE_DAYS
        and len(listeners[genre]) >= MIN_DISTINCT_LISTENERS
    ]
    eligible.sort(key=lambda genre: (-plays[genre], genre.casefold()))
    return {
        "genres": [{"name": genre} for genre in eligible[:PUBLIC_GENRE_LIMIT]],
        "period_end_utc": final_day.isoformat(),
    }
