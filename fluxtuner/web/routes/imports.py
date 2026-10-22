# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response

from fluxtuner.core.m3u_import import MAX_FILE_BYTES, MAX_PLAYLIST_NAME_LENGTH
from fluxtuner.network.network_policy import SystemStreamTargetResolver
from fluxtuner.network.remote_station_collection import fetch_remote_station_collection
from fluxtuner.web import guards
from fluxtuner.web import m3u_import as service

router = APIRouter()


async def _read_upload(request: Request) -> bytes:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type and content_type not in {
        "application/octet-stream",
        "audio/x-mpegurl",
        "audio/mpegurl",
        "application/vnd.apple.mpegurl",
        "text/plain",
    }:
        raise HTTPException(status_code=415, detail="Upload the playlist file as raw bytes.")

    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="The playlist exceeds 1 MiB.")
        data.extend(chunk)
    return bytes(data)


def _authorize(request: Request) -> int:
    user = guards.require_authenticated_user(
        request, auth_required_detail="Authentication required."
    )
    guards.require_csrf(request, csrf_error_detail="CSRF token is missing or invalid.")
    return int(user["id"])


async def _read_remote_url(request: Request) -> str:
    """Read a tiny JSON request without accepting unbounded request bodies."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Expected a JSON URL request.")
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 4096:
            raise HTTPException(status_code=413, detail="URL request exceeds 4 KiB.")
        raw.extend(chunk)
    try:
        import json

        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON URL request.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
        raise HTTPException(status_code=400, detail="A collection URL is required.")
    url = payload["url"]
    if not url or len(url) > 2048:
        raise HTTPException(status_code=400, detail="Invalid collection URL length.")
    return url


@router.post("/api/stations/import/remote")
async def fetch_remote_import(request: Request) -> Response:
    """Return one validated byte snapshot; the browser owns preview and confirmation."""
    _authorize(request)
    url = await _read_remote_url(request)
    try:
        data = await asyncio.to_thread(
            fetch_remote_station_collection, url, SystemStreamTargetResolver()
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    except (OSError, TimeoutError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502, detail="Could not retrieve the remote collection."
        ) from exc
    return Response(
        content=data, media_type="application/octet-stream", headers={"Cache-Control": "no-store"}
    )


@router.post("/api/stations/import/preview")
async def preview_import(
    request: Request,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user_id = _authorize(request)
    data = await _read_upload(request)
    try:
        return await asyncio.to_thread(
            service.preview_payload, data, user_id=user_id, profile_name=profile
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/api/stations/import")
async def confirm_import(
    request: Request,
    playlist: str = Query(min_length=1, max_length=MAX_PLAYLIST_NAME_LENGTH),
    existing: bool = Query(default=False),
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user_id = _authorize(request)
    data = await _read_upload(request)
    try:
        return await asyncio.to_thread(
            service.import_payload,
            data,
            user_id=user_id,
            profile_name=profile,
            playlist_name=playlist,
            existing=existing,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except service.DestinationConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
