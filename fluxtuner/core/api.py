from __future__ import annotations

from typing import Any

import requests

from fluxtuner import __version__
from fluxtuner.core.cache import get_cached_search, make_search_key, set_cached_search
from fluxtuner.core.stations import station_key
from fluxtuner.logging_config import get_logger

BASE_URL = "https://de1.api.radio-browser.info/json"

DEFAULT_HEADERS = {"User-Agent": f"FluxTuner/{__version__} (+https://github.com/pitill0/fluxtuner)"}

DEFAULT_TIMEOUT = 12

logger = get_logger(__name__)


def normalize_station(station: dict[str, Any]) -> dict[str, Any]:
    """Return a compact station dictionary used by CLI, TUI and GUI."""
    raw_url = station.get("url") or ""
    resolved_url = station.get("url_resolved") or raw_url
    return {
        "name": station.get("name") or "Unknown station",
        "url": raw_url or resolved_url,
        "url_resolved": resolved_url,
        "country": station.get("country") or "Unknown",
        "countrycode": station.get("countrycode") or "",
        "tags": station.get("tags") or "",
        "codec": station.get("codec") or "",
        "bitrate": station.get("bitrate") or 0,
        "homepage": station.get("homepage") or "",
        "language": station.get("language") or "",
    }


def _safe_response_json(response: requests.Response) -> Any | None:
    try:
        return response.json()
    except ValueError:
        logger.debug("Radio Browser API returned invalid JSON", exc_info=True)
        return None


def _safe_get_json_list(
    url: str,
    *,
    params: dict[str, Any],
    timeout: int = DEFAULT_TIMEOUT,
) -> list[dict[str, Any]]:
    logger.debug(
        "Requesting Radio Browser API endpoint with filters: %s",
        sorted(params.keys()),
    )

    try:
        response = requests.get(
            url,
            params=params,
            headers=DEFAULT_HEADERS,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException:
        logger.debug("Radio Browser API request failed", exc_info=True)
        return []

    data = _safe_response_json(response)
    if not isinstance(data, list):
        logger.debug("Radio Browser API returned unexpected response type: %s", type(data).__name__)
        return []

    valid_items = [item for item in data if isinstance(item, dict)]
    skipped_items = len(data) - len(valid_items)

    if skipped_items:
        logger.debug("Skipped %s invalid Radio Browser API item(s)", skipped_items)

    logger.debug("Radio Browser API returned %s valid station item(s)", len(valid_items))

    return valid_items


def search_stations(
    name: str | None = None,
    tag: str | None = None,
    country: str | None = None,
    countrycode: str | None = None,
    limit: int = 25,
) -> list[dict[str, Any]]:
    """Search radio stations using the Radio Browser API."""
    params: dict[str, Any] = {
        "limit": limit,
        "hidebroken": "true",
        "order": "clickcount",
        "reverse": "true",
    }

    if name:
        params["name"] = name
    if tag:
        params["tag"] = tag
    if country:
        params["country"] = country
    if countrycode:
        params["countrycode"] = countrycode.upper()

    return _safe_get_json_list(
        f"{BASE_URL}/stations/search",
        params=params,
    )


def search_stations_by_text(query: str, limit: int = 40) -> list[dict[str, Any]]:
    """Search by station name and tag, merging duplicated stream URLs."""
    return search_stations_filtered(query=query, limit=limit)


def _country_api_filters(country: str | None) -> tuple[str | None, str | None]:
    """Return API filters for country name/code when the user input is unambiguous."""
    if not country:
        return None, None

    value = country.strip()
    if len(value) == 2 and value.isalpha():
        return None, value.upper()

    return value, None


def _matches_country(station: dict[str, Any], country: str | None) -> bool:
    """Fuzzy local country filter used as a safety net for GUI/user input."""
    if not country:
        return True

    needle = country.strip().lower()
    if not needle:
        return True

    country_name = str(station.get("country") or "").lower()
    country_code = str(station.get("countrycode") or "").lower()

    return (
        needle in country_name
        or needle == country_code
        or (len(needle) == 2 and needle == country_code)
    )


def _station_bitrate(station: dict[str, Any]) -> int:
    try:
        return int(station.get("bitrate") or 0)
    except (TypeError, ValueError):
        return 0


def _empty_search_debug(
    *,
    query: str,
    country: str | None,
    min_bitrate: int | None,
    limit: int,
) -> dict[str, Any]:
    return {
        "query": query,
        "country": country or "",
        "min_bitrate": min_bitrate,
        "limit": limit,
        "api_limit": 0,
        "cache_hit": False,
        "name_results": 0,
        "tag_results": 0,
        "country_results": 0,
        "fallback_name_results": 0,
        "fallback_tag_results": 0,
        "fallback_country_results": 0,
        "raw_results": 0,
        "deduped_results": 0,
        "country_filtered_results": 0,
        "bitrate_filtered_results": 0,
        "returned_results": 0,
    }


def _filtered_search_result(
    *,
    query: str,
    country: str | None = None,
    min_bitrate: int | None = None,
    limit: int = 50,
    use_cache: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    query = (query or "").strip()
    country = country.strip() if country else None

    if min_bitrate is not None:
        min_bitrate = max(0, int(min_bitrate))

    debug = _empty_search_debug(
        query=query,
        country=country,
        min_bitrate=min_bitrate,
        limit=limit,
    )

    if not query and not country and min_bitrate is None:
        logger.debug("Skipping search because no filters were provided")
        return [], debug

    cache_key = make_search_key(query, country, min_bitrate, limit)
    if use_cache:
        cached_results = get_cached_search(cache_key)
        if cached_results is not None:
            logger.debug("Returning %s cached search result(s)", len(cached_results))
            debug["cache_hit"] = True
            debug["returned_results"] = len(cached_results)
            return cached_results, debug

    api_limit = max(limit * 4, 200)
    debug["api_limit"] = api_limit
    api_country, api_countrycode = _country_api_filters(country)

    raw_batches: list[tuple[str, list[dict[str, Any]]]] = []

    def add_batch(source: str, items: list[dict[str, Any]]) -> None:
        debug[f"{source}_results"] = len(items)
        debug["raw_results"] += len(items)
        raw_batches.append((source, items))

    if query:
        add_batch(
            "name",
            search_stations(
                name=query,
                country=api_country,
                countrycode=api_countrycode,
                limit=api_limit,
            ),
        )
        add_batch(
            "tag",
            search_stations(
                tag=query,
                country=api_country,
                countrycode=api_countrycode,
                limit=api_limit,
            ),
        )

        # If the API country filter was too strict, fallback to a broad search
        # and apply the country filter locally.
        if country and not any(items for _, items in raw_batches):
            add_batch("fallback_name", search_stations(name=query, limit=api_limit))
            add_batch("fallback_tag", search_stations(tag=query, limit=api_limit))
    else:
        add_batch(
            "country",
            search_stations(
                country=api_country,
                countrycode=api_countrycode,
                limit=api_limit,
            ),
        )

        if country and not any(items for _, items in raw_batches):
            add_batch("fallback_country", search_stations(limit=api_limit))

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    batch_positions = [0 for _source, _items in raw_batches]

    while len(results) < limit:
        advanced = False
        for batch_index, (_source, items) in enumerate(raw_batches):
            item_index = batch_positions[batch_index]
            if item_index >= len(items):
                continue

            batch_positions[batch_index] += 1
            advanced = True

            station = normalize_station(items[item_index])
            url = station_key(station)
            if not url or url in seen_urls:
                debug["deduped_results"] += 1
                continue
            if not _matches_country(station, country):
                debug["country_filtered_results"] += 1
                continue
            if min_bitrate is not None and _station_bitrate(station) < min_bitrate:
                debug["bitrate_filtered_results"] += 1
                continue

            seen_urls.add(url)
            results.append(station)

            if len(results) >= limit:
                break

        if not advanced:
            break

    if use_cache:
        set_cached_search(cache_key, results)

    logger.debug("Search returned %s filtered result(s)", len(results))

    debug["returned_results"] = len(results)
    return results, debug


def search_stations_filtered(
    query: str,
    country: str | None = None,
    min_bitrate: int | None = None,
    limit: int = 50,
    use_cache: bool = True,
) -> list[dict[str, Any]]:
    """Search by text and optional country/bitrate filters.

    The GUI can search with a text query, a country filter, a bitrate filter,
    or any combination of the three.

    Country handling is intentionally forgiving:
    - two-letter values are sent as Radio Browser country codes, e.g. ``ES``;
    - longer values are sent as country names when possible;
    - results are also filtered locally with substring matching.

    Bitrate is applied locally after fetching a larger candidate set so that a
    high minimum bitrate does not accidentally hide valid results.
    """
    results, _debug = _filtered_search_result(
        query=query,
        country=country,
        min_bitrate=min_bitrate,
        limit=limit,
        use_cache=use_cache,
    )
    return results


def search_stations_filtered_debug(
    query: str,
    country: str | None = None,
    min_bitrate: int | None = None,
    limit: int = 50,
    use_cache: bool = True,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Search stations and return internal count metadata for diagnostics."""
    return _filtered_search_result(
        query=query,
        country=country,
        min_bitrate=min_bitrate,
        limit=limit,
        use_cache=use_cache,
    )
