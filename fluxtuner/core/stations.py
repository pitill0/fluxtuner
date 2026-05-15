from __future__ import annotations

from typing import Any


def station_url(station: dict[str, Any] | None) -> str | None:
    """Return the preferred playable URL for a station."""
    if not station:
        return None

    url = station.get("url_resolved") or station.get("url")
    if not url:
        return None

    return str(url)


def station_key(station: dict[str, Any] | None) -> str | None:
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
    values = set()

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


def same_station(
    first: dict[str, Any] | None,
    second: dict[str, Any] | None,
) -> bool:
    """Return True when two station dictionaries refer to the same stream."""
    first_key = station_key(first)
    second_key = station_key(second)

    return bool(first_key and second_key and first_key == second_key)
