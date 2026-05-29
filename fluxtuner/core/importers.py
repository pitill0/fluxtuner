from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fluxtuner.players.security import is_supported_stream_url

MAX_TEXT_FIELD_LENGTH = 500
MAX_NAME_LENGTH = 200
MAX_TAG_LENGTH = 80


@dataclass(frozen=True)
class ImportResult:
    items: list[dict[str, Any]]
    skipped: int


def _clean_text(value: Any, *, max_length: int = MAX_TEXT_FIELD_LENGTH) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]


def _clean_optional_text(value: Any, *, max_length: int = MAX_TEXT_FIELD_LENGTH) -> str | None:
    clean_value = _clean_text(value, max_length=max_length)
    return clean_value or None


def _clean_tags(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []

    tags: list[str] = []
    seen: set[str] = set()

    for item in value:
        clean_tag = _clean_text(item, max_length=MAX_TAG_LENGTH)
        normalized = clean_tag.lower()
        if clean_tag and normalized not in seen:
            tags.append(clean_tag)
            seen.add(normalized)

    return tags


def _clean_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None

    clean_url = value.strip()
    if not is_supported_stream_url(clean_url):
        return None

    return clean_url


def validate_imported_favorite(item: Any) -> dict[str, Any] | None:
    """Return a safe favorite dictionary or None when the item is invalid."""
    if not isinstance(item, dict):
        return None

    url = _clean_url(item.get("url_resolved")) or _clean_url(item.get("url"))
    if not url:
        return None

    favorite: dict[str, Any] = {
        "name": _clean_text(item.get("name"), max_length=MAX_NAME_LENGTH) or "Unknown station",
        "url": url,
        "url_resolved": url,
        "country": _clean_text(item.get("country"), max_length=MAX_NAME_LENGTH),
        "codec": _clean_text(item.get("codec"), max_length=40),
        "tags": _clean_text(item.get("tags"), max_length=MAX_TEXT_FIELD_LENGTH),
        "bitrate": item.get("bitrate", 0),
        "custom_name": _clean_optional_text(item.get("custom_name"), max_length=MAX_NAME_LENGTH),
        "favorite_tags": _clean_tags(item.get("favorite_tags")),
    }

    return favorite


def validate_imported_playlist(item: Any) -> dict[str, Any] | None:
    """Return a safe playlist dictionary or None when the item is invalid."""
    if not isinstance(item, dict):
        return None

    name = _clean_text(item.get("name"), max_length=MAX_NAME_LENGTH)
    if not name:
        return None

    raw_station_keys = item.get("station_keys")
    if not isinstance(raw_station_keys, list):
        return None

    station_keys: list[str] = []
    seen: set[str] = set()

    for value in raw_station_keys:
        clean_url = _clean_url(value)
        if clean_url and clean_url not in seen:
            station_keys.append(clean_url)
            seen.add(clean_url)

    if not station_keys:
        return None

    return {
        "name": name,
        "station_keys": station_keys,
    }


def validate_imported_favorites(items: list[Any]) -> ImportResult:
    valid_items: list[dict[str, Any]] = []

    for item in items:
        favorite = validate_imported_favorite(item)
        if favorite:
            valid_items.append(favorite)

    return ImportResult(
        items=valid_items,
        skipped=len(items) - len(valid_items),
    )


def validate_imported_playlists(items: list[Any]) -> ImportResult:
    valid_items: list[dict[str, Any]] = []

    for item in items:
        playlist = validate_imported_playlist(item)
        if playlist:
            valid_items.append(playlist)

    return ImportResult(
        items=valid_items,
        skipped=len(items) - len(valid_items),
    )
