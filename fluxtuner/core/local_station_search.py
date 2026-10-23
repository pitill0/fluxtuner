"""Read-only, profile-scoped local station discovery."""

from __future__ import annotations

import sqlite3
from typing import Any

from fluxtuner.core.favorites import favorite_display_name, favorite_from_row
from fluxtuner.core.stations import station_bitrate, station_from_row, station_tags

# Only shared station metadata belongs in a discovery result by default.
# metadata_json may contain legacy or source-specific private fields.
_PUBLIC_STATION_FIELDS = (
    "stationuuid",
    "name",
    "url",
    "url_resolved",
    "homepage",
    "favicon",
    "country",
    "countrycode",
    "language",
    "tags",
    "codec",
    "bitrate",
)


def _local_station_from_row(
    row: sqlite3.Row,
) -> dict[str, Any]:
    """Expose shared station fields and only this profile's favorite data."""
    stored = station_from_row(row)
    station = {key: stored[key] for key in _PUBLIC_STATION_FIELDS}

    # Keep only the MIME hints recognized by the playback compatibility
    # contract. Do not expose other arbitrary metadata_json fields.
    for key in ("content_type", "content-type", "mime_type", "mimetype"):
        value = stored.get(key)
        if isinstance(value, str) and value.strip():
            station[key] = value

    if row["is_favorite"]:
        favorite = favorite_from_row(row)
        station["custom_name"] = favorite["custom_name"]
        station["favorite_tags"] = favorite["favorite_tags"]

    return station


def _rank(station: dict[str, Any], query: str) -> int:
    """Return a deterministic relevance tier; lower is better."""
    if not query:
        return 0

    needle = query.casefold()
    display_name = favorite_display_name(station).casefold()

    if display_name == needle:
        return 0
    if display_name.startswith(needle):
        return 1
    if needle in display_name:
        return 2

    tags = station_tags(station)
    tags.extend(station.get("favorite_tags") or [])

    if any(needle in str(tag).casefold() for tag in tags):
        return 3

    return 4


def _matches_country(station: dict[str, Any], country: str | None) -> bool:
    if not country:
        return True

    needle = country.casefold()
    country_name = str(station.get("country") or "").casefold()
    country_code = str(station.get("countrycode") or "").casefold()

    return needle in country_name or needle == country_code


def search_local_stations(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    query: str = "",
    country: str | None = None,
    min_bitrate: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search stations saved in favorites or playlists of one profile.

    Uses the caller's existing SQLite connection without writing,
    initializing storage or changing transaction boundaries.
    """
    if type(profile_id) is not int or profile_id <= 0:
        raise ValueError("An existing profile is required.")

    profile = conn.execute(
        "SELECT 1 FROM profiles WHERE id = ?",
        (profile_id,),
    ).fetchone()

    if profile is None:
        raise ValueError("The selected profile no longer exists.")

    clean_query = query.strip().casefold()
    clean_country = country.strip().casefold() if country else None
    normalized_bitrate = max(0, int(min_bitrate)) if min_bitrate is not None else None
    normalized_limit = max(1, int(limit))

    rows = conn.execute(
        """
        SELECT
            s.*,
            f.custom_name,
            f.favorite_tags_json,
            CASE WHEN f.station_id IS NULL THEN 0 ELSE 1 END AS is_favorite
        FROM stations AS s
        LEFT JOIN favorites AS f
          ON f.station_id = s.id
         AND f.profile_id = ?
        WHERE f.station_id IS NOT NULL
           OR EXISTS (
               SELECT 1
               FROM playlist_stations AS ps
               JOIN playlists AS p ON p.id = ps.playlist_id
               WHERE ps.station_id = s.id
                 AND p.profile_id = ?
           )
        ORDER BY s.station_key COLLATE BINARY ASC
        """,
        (profile_id, profile_id),
    ).fetchall()

    matches: list[dict[str, Any]] = []

    for row in rows:
        station = _local_station_from_row(row)

        if clean_query and _rank(station, clean_query) == 4:
            continue

        if not _matches_country(station, clean_country):
            continue

        if normalized_bitrate is not None and station_bitrate(station) < normalized_bitrate:
            continue

        matches.append(station)

    matches.sort(
        key=lambda station: (
            _rank(station, clean_query),
            favorite_display_name(station).casefold(),
            str(station.get("url_resolved") or station.get("url") or ""),
        )
    )

    return matches[:normalized_limit]
