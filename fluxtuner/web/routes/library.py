# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from contextlib import closing
from typing import Any, Literal

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request

from fluxtuner.core import db
from fluxtuner.web import context as web_context
from fluxtuner.web import guards as web_guards
from fluxtuner.web import library
from fluxtuner.web.m3u_import import _profile_id
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
    limit: int = Query(default=25, ge=1, le=100),
    debug: bool = Query(default=False),
    source: Literal["radio-browser", "local", "all"] = Query(default="radio-browser"),
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)

    try:
        return library.search_payload(
            query=q,
            country=country,
            min_bitrate=min_bitrate,
            limit=limit,
            debug=debug,
            source=source,
            user_id=int(user["id"]),
            profile_name=web_context.effective_profile_name(profile),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


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


def _manual_stations(
    user_id: int,
    profile: str | None,
) -> dict[str, Any]:
    """Read manual entries belonging to one authenticated profile."""
    with closing(db.connect()) as conn:
        profile_id = _profile_id(conn, user_id=user_id, profile_name=profile)
        rows = conn.execute(
            """
            SELECT DISTINCT s.name, s.url, s.url_resolved,
                   f.custom_name
            FROM station_sources AS src
            JOIN station_source_memberships AS member
              ON member.source_id = src.id
            JOIN stations AS s ON s.id = member.station_id
            JOIN favorites AS f
              ON f.station_id = s.id
             AND f.profile_id = src.profile_id
            WHERE src.profile_id = ?
              AND src.kind = 'manual_entry'
            ORDER BY COALESCE(f.custom_name, s.name), s.url
            """,
            (profile_id,),
        ).fetchall()

        stations = [station_payload(dict(row)) for row in rows]
        return {"count": len(stations), "stations": stations}


@router.get("/api/stations/custom")
def list_custom_stations(
    request: Request,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    try:
        return _manual_stations(
            int(user["id"]),
            web_context.effective_profile_name(profile),
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/api/stations/custom")
def create_custom_station(
    request: Request,
    payload: dict[str, Any] = required_body,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user = _require_authenticated_user(request)
    _require_csrf(request)

    if (
        set(payload) != {"name", "url"}
        or not isinstance(payload.get("name"), str)
        or not isinstance(payload.get("url"), str)
    ):
        raise HTTPException(
            status_code=400,
            detail="Provide only a station name and stream URL as text.",
        )

    try:
        return library.create_custom_station_payload(
            user_id=int(user["id"]),
            profile_name=profile,
            name=payload["name"],
            url=payload["url"],
        )
    except LookupError:
        raise HTTPException(
            status_code=404, detail="The selected profile is unavailable."
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
