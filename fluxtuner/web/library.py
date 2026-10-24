# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any, Literal

from fluxtuner.core import db
from fluxtuner.core.api import search_stations_filtered_debug
from fluxtuner.core.custom_stations import add_custom_station
from fluxtuner.core.favorites import add_favorite, list_favorites, load_favorites, remove_favorite
from fluxtuner.core.history import add_history, load_history
from fluxtuner.core.manual_playlists import (
    add_station_to_playlist,
    create_playlist,
    delete_playlist,
    get_playlist_stations,
    load_playlists,
    remove_station_from_playlist,
)
from fluxtuner.core.profiles import get_profile_by_name
from fluxtuner.core.search_service import SearchRequest, SearchService
from fluxtuner.web.payloads import station_payload

SEARCH_STATUS_OK = "ok"
SEARCH_STATUS_PARTIAL = "partial"
SEARCH_STATUS_UNAVAILABLE = "unavailable"


def _aggregate_search_status(debug_info: dict[str, Any]) -> str:
    sources = debug_info.get("sources")
    if not isinstance(sources, dict) or not sources:
        return SEARCH_STATUS_OK

    statuses = [source.get("status") for source in sources.values() if isinstance(source, dict)]
    if not statuses or all(status == SEARCH_STATUS_OK for status in statuses):
        return SEARCH_STATUS_OK
    if any(status == SEARCH_STATUS_OK for status in statuses):
        return SEARCH_STATUS_PARTIAL
    return SEARCH_STATUS_UNAVAILABLE


def search_payload(
    *,
    query: str,
    country: str,
    min_bitrate: int,
    limit: int,
    debug: bool = False,
    source: Literal["radio-browser", "local", "all"] = "radio-browser",
    user_id: int | None = None,
    profile_name: str | None = None,
) -> dict[str, Any]:
    normalized_query = query.strip()
    country_filter = country.strip() or None
    bitrate_filter = min_bitrate if min_bitrate > 0 else None

    if source == "radio-browser":
        # Preserve the existing remote search API and diagnostic contract.
        stations, debug_info = search_stations_filtered_debug(
            query=normalized_query,
            country=country_filter,
            min_bitrate=bitrate_filter,
            limit=limit,
            use_cache=not debug,
        )
        status = _aggregate_search_status(debug_info)
    else:
        if source not in ("local", "all"):
            raise ValueError("Unknown station discovery source.")
        if user_id is None:
            raise ValueError("Authenticated user is required.")

        requested_profile = db.DEFAULT_PROFILE_NAME if profile_name is None else profile_name
        if not requested_profile:
            raise ValueError("The requested profile is unavailable.")

        # Only the authenticated Web user's profile is eligible for discovery.
        # Never use the desktop user or create profiles during search.
        with db.connect() as conn:
            profile = get_profile_by_name(conn, requested_profile, user_id=user_id)
            if profile is None:
                raise ValueError("The requested profile is unavailable.")

            result = SearchService(
                local_connection=conn,
                profile_id=int(profile["id"]),
            ).search(
                SearchRequest(
                    query=normalized_query,
                    country=country_filter,
                    min_bitrate=bitrate_filter,
                    limit=limit,
                    use_cache=not debug,
                    source=source,
                )
            )

        stations = result.stations
        if source == "local":
            status = SEARCH_STATUS_OK
        elif result.remote_status == "error":
            status = SEARCH_STATUS_PARTIAL if stations else SEARCH_STATUS_UNAVAILABLE
        elif result.remote_status == "partial_error":
            status = SEARCH_STATUS_PARTIAL
        else:
            status = SEARCH_STATUS_OK

        debug_info = {
            "source": source,
            "total_found": result.total_found,
            "unsupported_count": result.unsupported_count,
            "remote_status": result.remote_status,
            "source_observations": result.source_observations,
        }

    payload = {
        "status": status,
        "query": normalized_query,
        "country": country_filter or "",
        "min_bitrate": min_bitrate,
        "limit": limit,
        "count": len(stations),
        "stations": [station_payload(station) for station in stations],
    }
    if debug:
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


def create_custom_station_payload(
    *,
    user_id: int,
    profile_name: str | None,
    name: str,
    url: str,
) -> dict[str, Any]:
    """Save a manual station within the authenticated user's profile."""
    with db.connect() as conn:
        if profile_name is None:
            profile_id = db.ensure_default_profile(conn, user_id=user_id)
        else:
            profile = get_profile_by_name(conn, profile_name, user_id=user_id)
            if profile is None:
                raise LookupError("The selected profile is unavailable.")
            profile_id = int(profile["id"])

        added = add_custom_station(
            conn, profile_id=profile_id, name=name, url=url, record_manual_provenance=True
        )
        saved = next(
            station
            for station in list_favorites(conn, profile_id=profile_id)
            if station.get("url_resolved") == url.strip()
        )
        payload = {
            "status": "ok",
            "added": added,
            "station": station_payload(saved),
        }
        conn.commit()
        return payload
