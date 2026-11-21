# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Privacy-conscious, name-only public genre popularity from daily counts."""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

MIN_PLAYS = 20
MIN_STATIONS = 3
MIN_ACTIVE_DAYS = 3
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

    Station diversity is not listener diversity: these aggregates have no
    user identities, so no claim about distinct listeners can be made.
    """
    final_day = as_of if as_of is not None else datetime.now(UTC).date() - timedelta(days=1)
    if not isinstance(final_day, date) or isinstance(final_day, datetime):
        raise TypeError("as_of must be a date")
    start = final_day - timedelta(days=6)
    next_day = final_day + timedelta(days=1)
    rows = conn.execute(
        """
        SELECT daily.station_id, daily.day_utc, daily.play_count, stations.tags
        FROM station_daily_plays AS daily
        JOIN stations ON stations.id = daily.station_id
        WHERE daily.day_utc >= ? AND daily.day_utc < ?
          AND daily.play_count > 0
        """,
        (start.isoformat(), next_day.isoformat()),
    )

    plays: dict[str, int] = defaultdict(int)
    stations: dict[str, set[int]] = defaultdict(set)
    days: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        for genre in _genres(row["tags"]):
            plays[genre] += int(row["play_count"])
            stations[genre].add(int(row["station_id"]))
            days[genre].add(str(row["day_utc"]))

    eligible = [
        genre
        for genre, count in plays.items()
        if count >= MIN_PLAYS
        and len(stations[genre]) >= MIN_STATIONS
        and len(days[genre]) >= MIN_ACTIVE_DAYS
    ]
    eligible.sort(key=lambda genre: (-plays[genre], genre.casefold()))
    return {
        "genres": [{"name": genre} for genre in eligible[:PUBLIC_GENRE_LIMIT]],
        "period_end_utc": final_day.isoformat(),
    }
