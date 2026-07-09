from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any


def station_url(station: dict[str, Any] | str | None) -> str | None:
    """Return the preferred playable URL for a station or raw stream URL."""
    if not station:
        return None

    if isinstance(station, str):
        clean_url = station.strip()
        return clean_url or None

    url = station.get("url_resolved") or station.get("url")
    if not url:
        return None

    clean_url = str(url).strip()
    return clean_url or None


def station_key(station: dict[str, Any] | str | None) -> str | None:
    """Return the stable key used to identify a station across favorites/playlists."""
    return station_url(station)


def station_name(station: dict[str, Any] | None) -> str:
    """Return the original station name with a safe fallback."""
    if not station:
        return "Unknown station"

    name = station.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()

    return "Unknown station"


def station_tags(station: dict[str, Any] | None) -> list[str]:
    """Return stream tags as a normalized list."""
    if not station:
        return []

    raw_tags = station.get("tags") or ""
    if isinstance(raw_tags, str):
        return [tag.strip() for tag in raw_tags.split(",") if tag.strip()]

    if isinstance(raw_tags, list):
        return [str(tag).strip() for tag in raw_tags if str(tag).strip()]

    return []


def favorite_tags(station: dict[str, Any] | None) -> list[str]:
    """Return user-defined favorite tags as a normalized list."""
    if not station:
        return []

    raw_tags = station.get("favorite_tags") or []
    if not isinstance(raw_tags, list):
        return []

    return sorted({str(tag).strip() for tag in raw_tags if str(tag).strip()})


def all_station_tags(station: dict[str, Any] | None) -> set[str]:
    """Return stream and favorite tags as lowercase values."""
    values: set[str] = set()

    values.update(tag.lower() for tag in station_tags(station))
    values.update(tag.lower() for tag in favorite_tags(station))

    return values


def station_matches_tag(station: dict[str, Any] | None, tag: str) -> bool:
    """Return True when a station has the given stream or favorite tag."""
    clean_tag = tag.strip().lower()
    if not clean_tag:
        return True

    return clean_tag in all_station_tags(station)


def station_short_id(station: dict[str, Any] | None, length: int = 8) -> str:
    """Return a short stable station identifier for UI tables."""
    if not station:
        return "-"

    raw_value = (
        station.get("stationuuid") or station.get("changeuuid") or station_key(station) or ""
    )

    return str(raw_value)[:length] if raw_value else "-"


def station_bitrate(station: dict[str, Any] | None) -> int:
    """Return station bitrate as an integer."""
    if not station:
        return 0

    try:
        return int(station.get("bitrate") or 0)
    except (TypeError, ValueError):
        return 0


def station_country(station: dict[str, Any] | None) -> str:
    """Return station country with a safe fallback."""
    if not station:
        return "Unknown"

    country = station.get("country")
    if isinstance(country, str) and country.strip():
        return country.strip()

    return "Unknown"


def station_codec(station: dict[str, Any] | None) -> str:
    """Return station codec with a safe fallback."""
    if not station:
        return "?"

    codec = station.get("codec")
    if isinstance(codec, str) and codec.strip():
        return codec.strip()

    return "?"


def station_tags_text(station: dict[str, Any] | None, fallback: str = "No tags") -> str:
    """Return normalized stream tags as display text."""
    tags = station_tags(station)
    return ", ".join(tags) if tags else fallback


def same_station(
    first: dict[str, Any] | None,
    second: dict[str, Any] | None,
) -> bool:
    """Return True when two station dictionaries refer to the same stream."""
    first_key = station_key(first)
    second_key = station_key(second)

    return bool(first_key and second_key and first_key == second_key)


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None

    clean_value = str(value).strip()
    return clean_value or None


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def station_metadata(station: dict[str, Any]) -> str:
    """Serialize a station dict for lossless-ish metadata preservation."""
    return json.dumps(
        station,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def upsert_station(conn: sqlite3.Connection, station: dict[str, Any]) -> int:
    """Insert or update a station and return its database id.

    FluxTuner 0.6.0 identifies saved stations by the playable URL returned by
    station_key(). SQLite keeps that same key so existing favorites, history and
    playlists can migrate without changing user-visible behavior.
    """
    key = station_key(station)
    if not key:
        raise ValueError("Station URL is required.")

    now = datetime.now(UTC).isoformat()
    url = _clean_text(station.get("url")) or key
    url_resolved = _clean_text(station.get("url_resolved")) or url

    conn.execute(
        """
        INSERT INTO stations (
            station_key,
            stationuuid,
            name,
            url,
            url_resolved,
            homepage,
            favicon,
            country,
            countrycode,
            language,
            tags,
            codec,
            bitrate,
            metadata_json,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(station_key) DO UPDATE SET
            stationuuid = excluded.stationuuid,
            name = excluded.name,
            url = excluded.url,
            url_resolved = excluded.url_resolved,
            homepage = excluded.homepage,
            favicon = excluded.favicon,
            country = excluded.country,
            countrycode = excluded.countrycode,
            language = excluded.language,
            tags = excluded.tags,
            codec = excluded.codec,
            bitrate = excluded.bitrate,
            metadata_json = excluded.metadata_json,
            updated_at = excluded.updated_at
        """,
        (
            key,
            _clean_text(station.get("stationuuid")),
            station_name(station),
            url,
            url_resolved,
            _clean_text(station.get("homepage")),
            _clean_text(station.get("favicon")),
            _clean_text(station.get("country")),
            _clean_text(station.get("countrycode")),
            _clean_text(station.get("language")),
            _clean_text(station.get("tags")),
            _clean_text(station.get("codec")),
            _safe_int(station.get("bitrate")),
            station_metadata(station),
            now,
            now,
        ),
    )

    row = conn.execute(
        "SELECT id FROM stations WHERE station_key = ?",
        (key,),
    ).fetchone()

    if row is None:
        raise RuntimeError("Could not persist station.")

    return int(row["id"])


def station_from_row(row: sqlite3.Row) -> dict[str, Any]:
    """Return a FluxTuner station dict from a stations row."""
    try:
        metadata = json.loads(str(row["metadata_json"] or "{}"))
    except json.JSONDecodeError:
        metadata = {}

    if not isinstance(metadata, dict):
        metadata = {}

    station = dict(metadata)

    station["stationuuid"] = row["stationuuid"] or station.get("stationuuid") or ""
    station["name"] = row["name"] or station.get("name") or "Unknown station"
    station["url"] = row["url"] or station.get("url") or ""
    station["url_resolved"] = row["url_resolved"] or station.get("url_resolved") or station["url"]
    station["homepage"] = row["homepage"] or station.get("homepage") or ""
    station["favicon"] = row["favicon"] or station.get("favicon") or ""
    station["country"] = row["country"] or station.get("country") or ""
    station["countrycode"] = row["countrycode"] or station.get("countrycode") or ""
    station["language"] = row["language"] or station.get("language") or ""
    station["tags"] = row["tags"] or station.get("tags") or ""
    station["codec"] = row["codec"] or station.get("codec") or ""
    station["bitrate"] = _safe_int(row["bitrate"])

    return station


def get_station_by_key(conn: sqlite3.Connection, key: str) -> dict[str, Any] | None:
    """Load a station by FluxTuner station key."""
    row = conn.execute(
        "SELECT * FROM stations WHERE station_key = ?",
        (key,),
    ).fetchone()

    if row is None:
        return None

    return station_from_row(row)
