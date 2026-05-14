from __future__ import annotations

import json
from pathlib import Path
from fluxtuner.paths import data_file, migrate_legacy_file
from fluxtuner.core.stations import station_key, station_name
from typing import Any

LEGACY_FAVORITES_FILE = Path.home() / ".fluxtuner_favorites.json"
FAVORITES_FILE = data_file("favorites.json")
migrate_legacy_file(LEGACY_FAVORITES_FILE, FAVORITES_FILE)


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
    return station_name(station)


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


def update_favorite(url: str, *, custom_name: str | None | object = ..., favorite_tags: list[str] | None | object = ...) -> bool:
    favorites = load_favorites()
    changed = False

    for item in favorites:
        if station_key(item) != url and item.get("url") != url:
            continue

        if custom_name is not ...:
            clean_name = str(custom_name or "").strip()
            item["custom_name"] = clean_name or None
            changed = True

        if favorite_tags is not ...:
            tags = favorite_tags or []
            item["favorite_tags"] = sorted({str(tag).strip() for tag in tags if str(tag).strip()})
            changed = True

        break

    if changed:
        save_favorites(favorites)
    return changed


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
