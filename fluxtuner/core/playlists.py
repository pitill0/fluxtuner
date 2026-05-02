from __future__ import annotations

import random
from typing import Any

from fluxtuner.core.favorites import load_favorites


def get_tag_counts() -> list[tuple[str, int]]:
    """Return favorite tag counts sorted by tag name."""
    counts: dict[str, int] = {}
    for favorite in load_favorites():
        for tag in favorite.get("favorite_tags", []):
            clean_tag = str(tag).strip()
            if clean_tag:
                counts[clean_tag] = counts.get(clean_tag, 0) + 1
    return sorted(counts.items(), key=lambda item: item[0].lower())


def get_all_tags() -> list[str]:
    """Return all favorite tags sorted by name."""
    return [tag for tag, _count in get_tag_counts()]


def get_by_tag(tag: str) -> list[dict[str, Any]]:
    """Return favorites that include the given user tag."""
    clean_tag = tag.strip().lower()
    if not clean_tag:
        return []
    return [
        favorite
        for favorite in load_favorites()
        if clean_tag in {str(item).lower() for item in favorite.get("favorite_tags", [])}
    ]


def random_by_tag(tag: str) -> dict[str, Any] | None:
    """Return a random favorite from a tag-based dynamic playlist."""
    stations = get_by_tag(tag)
    if not stations:
        return None
    return random.choice(stations)
