from __future__ import annotations

import json
import time
from typing import Any

from fluxtuner.core.storage import write_json_atomic
from fluxtuner.logging_config import get_logger
from fluxtuner.paths import cache_file

logger = get_logger(__name__)
CACHE_TTL_SECONDS = 6 * 60 * 60

CACHE_FILE = cache_file("search_cache.json")


def _load_cache() -> dict[str, Any]:
    if not CACHE_FILE.exists():
        return {}
    try:
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except OSError:
        logger.debug("Could not read search cache; ignoring cache", exc_info=True)
        return {}
    except json.JSONDecodeError:
        logger.debug("Invalid search cache JSON; ignoring cache", exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}


def _save_cache(data: dict[str, Any]) -> None:
    try:
        write_json_atomic(CACHE_FILE, data, sort_keys=True)
    except OSError:
        logger.debug("Could not write search cache; continuing without cache update", exc_info=True)


def make_search_key(
    query: str,
    country: str | None = None,
    min_bitrate: int | None = None,
    limit: int = 50,
) -> str:
    normalized_country = (country or "").strip().lower()
    normalized_query = query.strip().lower()
    bitrate = "" if min_bitrate is None else str(int(min_bitrate))
    return (
        f"query={normalized_query}|country={normalized_country}|min_bitrate={bitrate}|limit={limit}"
    )


def get_cached_search(
    key: str, ttl_seconds: int = CACHE_TTL_SECONDS
) -> list[dict[str, Any]] | None:
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
