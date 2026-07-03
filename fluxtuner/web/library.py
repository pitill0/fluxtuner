# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fluxtuner.core.api import search_stations_filtered, search_stations_filtered_debug
from fluxtuner.core.favorites import add_favorite, load_favorites, remove_favorite
from fluxtuner.core.history import add_history, load_history
from fluxtuner.core.manual_playlists import (
    add_station_to_playlist,
    create_playlist,
    delete_playlist,
    get_playlist_stations,
    load_playlists,
    remove_station_from_playlist,
)
from fluxtuner.web.payloads import station_payload


def search_payload(
    *,
    query: str,
    country: str,
    min_bitrate: int,
    limit: int,
    debug: bool = False,
) -> dict[str, Any]:
    normalized_query = query.strip()
    country_filter = country.strip() or None
    bitrate_filter = min_bitrate if min_bitrate > 0 else None

    debug_info: dict[str, Any] | None = None
    if debug:
        stations, debug_info = search_stations_filtered_debug(
            query=normalized_query,
            country=country_filter,
            min_bitrate=bitrate_filter,
            limit=limit,
            use_cache=False,
        )
    else:
        stations = search_stations_filtered(
            query=normalized_query,
            country=country_filter,
            min_bitrate=bitrate_filter,
            limit=limit,
        )

    payload = {
        "query": normalized_query,
        "country": country_filter or "",
        "min_bitrate": min_bitrate,
        "limit": limit,
        "count": len(stations),
        "stations": [station_payload(station) for station in stations],
    }
    if debug_info is not None:
        payload["debug"] = debug_info

    return payload


def history_payload(*, user_id: int, profile_name: str | None, limit: int) -> dict[str, Any]:
    stations = load_history(profile_name=profile_name, user_id=user_id)[:limit]
    return {
        "count": len(stations),
        "stations": [station_payload(station) for station in stations],
    }


def record_history_payload(
    station_data: dict[str, Any],
    *,
    user_id: int,
    profile_name: str | None,
) -> dict[str, Any]:
    add_history(station_data, profile_name=profile_name, user_id=user_id)
    return {"status": "ok", "station": station_data}


def favorites_payload(*, user_id: int, profile_name: str | None) -> dict[str, Any]:
    stations = load_favorites(profile_name=profile_name, user_id=user_id)
    return {
        "count": len(stations),
        "stations": [station_payload(station) for station in stations],
    }


def create_favorite_payload(
    station_data: dict[str, Any],
    *,
    user_id: int,
    profile_name: str | None,
) -> dict[str, Any]:
    added = add_favorite(station_data, profile_name=profile_name, user_id=user_id)
    return {"status": "ok", "added": added, "station": station_data}


def delete_favorite_payload(
    url: str,
    *,
    user_id: int,
    profile_name: str | None,
) -> dict[str, Any]:
    removed = remove_favorite(url, profile_name=profile_name, user_id=user_id)
    return {"status": "ok", "removed": removed, "url": url}


def playlists_payload(*, user_id: int, profile_name: str | None) -> dict[str, Any]:
    items = load_playlists(profile_name=profile_name, user_id=user_id)
    return {
        "count": len(items),
        "playlists": [
            {
                "name": item["name"],
                "count": len(
                    get_playlist_stations(
                        item["name"],
                        profile_name=profile_name,
                        user_id=user_id,
                    )
                ),
            }
            for item in items
        ],
    }


def create_playlist_payload(
    name: str,
    *,
    user_id: int,
    profile_name: str | None,
) -> dict[str, Any]:
    created = create_playlist(name, profile_name=profile_name, user_id=user_id)
    return {"status": "ok", "created": created, "name": name}


def delete_playlist_payload(
    name: str,
    *,
    user_id: int,
    profile_name: str | None,
) -> dict[str, Any]:
    removed = delete_playlist(name, profile_name=profile_name, user_id=user_id)
    return {"status": "ok", "removed": removed, "name": name}


def playlist_stations_payload(
    name: str,
    *,
    user_id: int,
    profile_name: str | None,
) -> dict[str, Any]:
    stations = get_playlist_stations(name, profile_name=profile_name, user_id=user_id)
    return {
        "name": name,
        "count": len(stations),
        "stations": [station_payload(station) for station in stations],
    }


def add_station_to_playlist_payload(
    name: str,
    station_data: dict[str, Any],
    *,
    user_id: int,
    profile_name: str | None,
) -> dict[str, Any]:
    add_favorite(station_data, profile_name=profile_name, user_id=user_id)
    added = add_station_to_playlist(
        name,
        station_data,
        profile_name=profile_name,
        user_id=user_id,
    )
    return {"status": "ok", "added": added, "name": name, "station": station_data}


def remove_station_from_playlist_payload(
    name: str,
    url: str,
    *,
    user_id: int,
    profile_name: str | None,
) -> dict[str, Any]:
    removed = remove_station_from_playlist(
        name,
        {"url": url},
        profile_name=profile_name,
        user_id=user_id,
    )
    return {"status": "ok", "removed": removed, "name": name, "url": url}
