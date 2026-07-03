# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request

from fluxtuner.web import context as web_context
from fluxtuner.web import guards as web_guards
from fluxtuner.web import library
from fluxtuner.web.payloads import station_payload
from fluxtuner.web.validation import (
    is_supported_web_url,
    playlist_name,
    playlist_name_too_long,
    station_stream_url,
)

INVALID_STATION_URL_DETAIL = "Station URL must be a valid HTTP or HTTPS URL."
PLAYLIST_REQUIRED_DETAIL = "Playlist name is required."
FIELD_TOO_LONG_DETAIL = "One or more fields exceed the maximum allowed length."
MAX_PLAYLIST_NAME_LENGTH = 120
AUTH_REQUIRED_DETAIL = "Authentication required."
CSRF_ERROR_DETAIL = "CSRF token is missing or invalid."

router = APIRouter()
required_body = Body(...)


def _require_authenticated_user(request: Request) -> dict[str, Any]:
    return web_guards.require_authenticated_user(
        request,
        auth_required_detail=AUTH_REQUIRED_DETAIL,
    )


def _require_csrf(request: Request) -> None:
    web_guards.require_csrf(
        request,
        csrf_error_detail=CSRF_ERROR_DETAIL,
    )


def _require_station_stream_url(station_data: dict[str, Any]) -> None:
    if not is_supported_web_url(station_stream_url(station_data)):
        raise HTTPException(status_code=400, detail=INVALID_STATION_URL_DETAIL)


@router.get("/api/search")
def search(
    request: Request,
    q: str = Query(default="", max_length=120),
    country: str = Query(default="", max_length=80),
    min_bitrate: int = Query(default=0, ge=0, le=1000),
    limit: int = Query(default=25, ge=1, le=50),
    debug: bool = Query(default=False),
) -> dict[str, Any]:
    _require_authenticated_user(request)

    return library.search_payload(
        query=q,
        country=country,
        min_bitrate=min_bitrate,
        limit=limit,
        debug=debug,
    )


@router.get("/api/history")
def history(
    request: Request,
    limit: int = Query(default=25, ge=1, le=100),
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)

    return library.history_payload(
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
        limit=limit,
    )


@router.post("/api/history")
def record_history(
    request: Request,
    station: dict[str, Any] = required_body,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_csrf(request)

    station_data = station_payload(station)
    _require_station_stream_url(station_data)

    return library.record_history_payload(
        station_data,
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )


@router.get("/api/favorites")
def favorites(
    request: Request,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)

    return library.favorites_payload(
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )


@router.post("/api/favorites")
def create_favorite(
    request: Request,
    station: dict[str, Any] = required_body,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_csrf(request)

    station_data = station_payload(station)
    _require_station_stream_url(station_data)

    return library.create_favorite_payload(
        station_data,
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )


@router.delete("/api/favorites")
def delete_favorite(
    request: Request,
    url: str = Query(..., min_length=1, max_length=4096),
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_csrf(request)

    return library.delete_favorite_payload(
        url,
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )


@router.get("/api/playlists")
def playlists(
    request: Request,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)

    return library.playlists_payload(
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )


@router.post("/api/playlists")
def create_web_playlist(
    request: Request,
    payload: dict[str, Any] = required_body,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_csrf(request)

    name = playlist_name(payload)
    if not name:
        raise HTTPException(status_code=400, detail=PLAYLIST_REQUIRED_DETAIL)
    if playlist_name_too_long(name):
        raise HTTPException(status_code=400, detail=FIELD_TOO_LONG_DETAIL)

    return library.create_playlist_payload(
        name,
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )


@router.delete("/api/playlists/{name}")
def delete_web_playlist(
    request: Request,
    name: str = Path(..., min_length=1, max_length=MAX_PLAYLIST_NAME_LENGTH),
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_csrf(request)

    return library.delete_playlist_payload(
        name,
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )


@router.get("/api/playlists/{name}/stations")
def playlist_stations(
    request: Request,
    name: str = Path(..., min_length=1, max_length=MAX_PLAYLIST_NAME_LENGTH),
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)

    return library.playlist_stations_payload(
        name,
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )


@router.post("/api/playlists/{name}/stations")
def add_web_station_to_playlist(
    request: Request,
    name: str = Path(..., min_length=1, max_length=MAX_PLAYLIST_NAME_LENGTH),
    station: dict[str, Any] = required_body,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_csrf(request)

    station_data = station_payload(station)
    _require_station_stream_url(station_data)

    return library.add_station_to_playlist_payload(
        name,
        station_data,
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )


@router.delete("/api/playlists/{name}/stations")
def remove_web_station_from_playlist(
    request: Request,
    name: str = Path(..., min_length=1, max_length=MAX_PLAYLIST_NAME_LENGTH),
    url: str = Query(..., min_length=1, max_length=4096),
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_csrf(request)

    return library.remove_station_from_playlist_payload(
        name,
        url,
        user_id=int(user["id"]),
        profile_name=web_context.effective_profile_name(profile),
    )
