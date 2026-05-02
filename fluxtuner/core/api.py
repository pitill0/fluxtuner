from __future__ import annotations

from typing import Any

import requests

BASE_URL = "https://de1.api.radio-browser.info/json"
DEFAULT_HEADERS = {
    "User-Agent": "FluxTuner/0.1 (+https://example.local/fluxtuner)"
}


def normalize_station(station: dict[str, Any]) -> dict[str, Any]:
    """Return a compact station dictionary used by both CLI and TUI."""
    return {
        "name": station.get("name") or "Unknown station",
        "url": station.get("url_resolved") or station.get("url") or "",
        "country": station.get("country") or "Unknown",
        "tags": station.get("tags") or "",
        "codec": station.get("codec") or "",
        "bitrate": station.get("bitrate") or 0,
        "homepage": station.get("homepage") or "",
        "language": station.get("language") or "",
    }


def search_stations(
    name: str | None = None,
    tag: str | None = None,
    country: str | None = None,
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

    response = requests.get(
        f"{BASE_URL}/stations/search",
        params=params,
        headers=DEFAULT_HEADERS,
        timeout=12,
    )
    response.raise_for_status()
    return response.json()


def search_stations_by_text(query: str, limit: int = 40) -> list[dict[str, Any]]:
    """Search by station name and tag, merging duplicated stream URLs."""
    query = query.strip()
    if not query:
        return []

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for items in (
        search_stations(name=query, limit=limit),
        search_stations(tag=query, limit=limit),
    ):
        for item in items:
            station = normalize_station(item)
            url = station.get("url")
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            results.append(station)

    return results[:limit]


def search_stations_filtered(
    query: str,
    country: str | None = None,
    min_bitrate: int | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Search by text and optional filters used by the TUI.

    `query` is matched against station names and tags. `country` is passed to
    Radio Browser when provided. `min_bitrate` is applied locally because API
    results may be inconsistent across mirrors.
    """
    query = query.strip()
    country = country.strip() if country else None
    if not query:
        return []

    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for items in (
        search_stations(name=query, country=country, limit=limit),
        search_stations(tag=query, country=country, limit=limit),
    ):
        for item in items:
            station = normalize_station(item)
            url = station.get("url")
            if not url or url in seen_urls:
                continue
            bitrate = int(station.get("bitrate") or 0)
            if min_bitrate is not None and bitrate < min_bitrate:
                continue
            seen_urls.add(url)
            results.append(station)

    return results[:limit]
