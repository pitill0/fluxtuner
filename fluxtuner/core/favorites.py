from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FAVORITES_FILE = Path.home() / ".fluxtuner_favorites.json"


def station_key(station: dict[str, Any]) -> str | None:
    """Return the stable favorite key for a station."""
    return station.get("url_resolved") or station.get("url")


def load_favorites() -> list[dict[str, Any]]:
    if not FAVORITES_FILE.exists():
        return []

    try:
        data = json.loads(FAVORITES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    return [normalize_favorite(item) for item in data if isinstance(item, dict)]


def save_favorites(favorites: list[dict[str, Any]]) -> None:
    normalized = [normalize_favorite(item) for item in favorites if station_key(item)]
    FAVORITES_FILE.write_text(
        json.dumps(normalized, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def normalize_favorite(station: dict[str, Any]) -> dict[str, Any]:
    """Return a favorite with the current metadata schema.

    Older FluxTuner favorites were saved as raw Radio Browser station dictionaries.
    This keeps them compatible while adding custom display names and user tags.
    """
    favorite = dict(station)
    favorite.setdefault("custom_name", None)
    favorite.setdefault("favorite_tags", [])

    # Backward compatibility: early v13 experiments used a generic "tags" list for
    # user tags, while Radio Browser uses "tags" as a comma-separated string.
    raw_user_tags = favorite.get("favorite_tags")
    if not isinstance(raw_user_tags, list):
        raw_user_tags = []
    favorite["favorite_tags"] = sorted({str(tag).strip() for tag in raw_user_tags if str(tag).strip()})

    if not favorite.get("url_resolved"):
        favorite["url_resolved"] = favorite.get("url")

    return favorite


def favorite_display_name(station: dict[str, Any]) -> str:
    custom_name = station.get("custom_name")
    if isinstance(custom_name, str) and custom_name.strip():
        return custom_name.strip()
    return str(station.get("name") or "Unknown station")


def add_favorite(station: dict[str, Any]) -> bool:
    favorites = load_favorites()
    key = station_key(station)

    if not key:
        return False

    if any(station_key(item) == key for item in favorites):
        return False

    favorite = normalize_favorite(station)
    favorites.append(favorite)
    save_favorites(favorites)
    return True


def remove_favorite(url: str) -> bool:
    favorites = load_favorites()
    original_len = len(favorites)
    favorites = [item for item in favorites if station_key(item) != url and item.get("url") != url]
    save_favorites(favorites)
    return len(favorites) != original_len


def update_favorite(
    key: str,
    favorite_name: str | None = None,
    favorite_tags: list[str] | None = None,
) -> bool:
    """Update favorite metadata by station key/url."""
    favorites = load_favorites()
    changed = False

    normalized_tags = favorite_tags if favorite_tags is not None else None

    for favorite in favorites:
        if station_key(favorite) != key:
            continue

        if favorite_name is not None:
            cleaned_name = favorite_name.strip()
            if cleaned_name:
                favorite["favorite_name"] = cleaned_name
            else:
                favorite.pop("favorite_name", None)
            changed = True

        if normalized_tags is not None:
            favorite["favorite_tags"] = sorted({tag.strip() for tag in normalized_tags if tag.strip()})
            changed = True

        break

    if not changed:
        return False

    save_favorites(favorites)
    return True

def filter_favorites_by_tag(tag: str) -> list[dict[str, Any]]:
    clean_tag = tag.strip().lower()
    if not clean_tag:
        return load_favorites()
    return [
        favorite
        for favorite in load_favorites()
        if clean_tag in {str(item).lower() for item in favorite.get("favorite_tags", [])}
    ]


def all_favorite_tags() -> list[str]:
    tags: set[str] = set()
    for favorite in load_favorites():
        tags.update(str(tag).strip() for tag in favorite.get("favorite_tags", []) if str(tag).strip())
    return sorted(tags, key=str.lower)
