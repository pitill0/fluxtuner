from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FAVORITES_FILE = Path.home() / ".fluxtuner_favorites.json"


def load_favorites() -> list[dict[str, Any]]:
    if not FAVORITES_FILE.exists():
        return []

    try:
        data = json.loads(FAVORITES_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    return data


def save_favorites(favorites: list[dict[str, Any]]) -> None:
    FAVORITES_FILE.write_text(
        json.dumps(favorites, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_favorite(station: dict[str, Any]) -> None:
    favorites = load_favorites()
    url = station.get("url")

    if not url:
        return

    if any(item.get("url") == url for item in favorites):
        return

    favorites.append(station)
    save_favorites(favorites)


def remove_favorite(url: str) -> None:
    favorites = load_favorites()
    favorites = [item for item in favorites if item.get("url") != url]
    save_favorites(favorites)
