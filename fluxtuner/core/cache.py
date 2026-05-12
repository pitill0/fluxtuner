from __future__ import annotations

import json
import os
import time
from pathlib import Path
from fluxtuner.paths import CACHE_DIR
from typing import Any

APP_NAME = "fluxtuner"
CACHE_TTL_SECONDS = 6 * 60 * 60


def cache_dir() -> Path:
    base = os.environ.get("XDG_CACHE_HOME")
    if base:
        return Path(base) / APP_NAME
    return CACHE_DIR


CACHE_FILE = cache_dir() / "search_cache.json"


def _load_cache() -> dict[str, Any]:
    if not CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(data: dict[str, Any]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def make_search_key(
    query: str,
    country: str | None = None,
    min_bitrate: int | None = None,
    limit: int = 50,
) -> str:
    normalized_country = (country or "").strip().lower()
    normalized_query = query.strip().lower()
    bitrate = "" if min_bitrate is None else str(int(min_bitrate))
    return f"query={normalized_query}|country={normalized_country}|min_bitrate={bitrate}|limit={limit}"


def get_cached_search(key: str, ttl_seconds: int = CACHE_TTL_SECONDS) -> list[dict[str, Any]] | None:
    cache = _load_cache()
    entry = cache.get(key)
    if not isinstance(entry, dict):
        return None

    created_at = entry.get("created_at")
    results = entry.get("results")
    if not isinstance(created_at, (int, float)) or not isinstance(results, list):
        return None
    if time.time() - created_at > ttl_seconds:
        return None
    return results


def set_cached_search(key: str, results: list[dict[str, Any]]) -> None:
    cache = _load_cache()
    cache[key] = {
        "created_at": time.time(),
        "results": results,
    }
    _save_cache(cache)


def clear_search_cache() -> None:
    try:
        CACHE_FILE.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return
