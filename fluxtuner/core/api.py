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
    query = (query or "").strip()
    country = country.strip() if country else None

    if min_bitrate is not None:
        min_bitrate = max(0, int(min_bitrate))

    if not query and not country and min_bitrate is None:
        logger.debug("Skipping search because no filters were provided")
        return []

    cache_key = make_search_key(query, country, min_bitrate, limit)
    if use_cache:
        cached_results = get_cached_search(cache_key)
        if cached_results is not None:
            logger.debug("Returning %s cached search result(s)", len(cached_results))
            return cached_results

    api_limit = max(limit * 4, 200)
    api_country, api_countrycode = _country_api_filters(country)

    raw_batches: list[list[dict[str, Any]]] = []

    if query:
        raw_batches.extend(
            [
                search_stations(
                    name=query,
                    country=api_country,
                    countrycode=api_countrycode,
                    limit=api_limit,
                ),
                search_stations(
                    tag=query,
                    country=api_country,
                    countrycode=api_countrycode,
                    limit=api_limit,
                ),
            ]
        )

        # If the API country filter was too strict, fallback to a broad search
        # and apply the country filter locally.
        if country and not any(raw_batches):
            raw_batches.extend(
                [
                    search_stations(name=query, limit=api_limit),
                    search_stations(tag=query, limit=api_limit),
                ]
            )
    else:
        raw_batches.append(
            search_stations(
                country=api_country,
                countrycode=api_countrycode,
                limit=api_limit,
            )
        )

        if country and not any(raw_batches):
            raw_batches.append(search_stations(limit=api_limit))

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for items in raw_batches:
        for item in items:
            station = normalize_station(item)
            url = station_key(station)
            if not url or url in seen_urls:
                continue
            if not _matches_country(station, country):
                continue
            if min_bitrate is not None and _station_bitrate(station) < min_bitrate:
                continue

            seen_urls.add(url)
            results.append(station)

            if len(results) >= limit:
                break
        if len(results) >= limit:
            break

    if use_cache:
        set_cached_search(cache_key, results)

    logger.debug("Search returned %s filtered result(s)", len(results))

    return results
