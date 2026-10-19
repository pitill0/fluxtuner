# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from fluxtuner.core.m3u_import import MAX_FILE_BYTES, MAX_PLAYLIST_NAME_LENGTH
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
