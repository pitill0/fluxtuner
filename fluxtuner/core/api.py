from __future__ import annotations

from typing import Any

import requests

BASE_URL = "https://de1.api.radio-browser.info/json"
DEFAULT_HEADERS = {
    "User-Agent": "FluxTuner/0.1 (+https://example.local/fluxtuner)"
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
