# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Authenticated remote catalog subscription endpoints."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from contextlib import closing
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Query, Request

from fluxtuner.core import db
from fluxtuner.core.remote_subscription_store import (
    delete_subscription,
    get_entries,
    get_subscription,
    list_subscriptions,
    mark_not_modified,
)
from fluxtuner.network.network_policy import SystemStreamTargetResolver
from fluxtuner.network.remote_station_collection import (
    ConditionalCollectionResult,
    fetch_conditional_remote_station_collection,
)
from fluxtuner.web import guards
from fluxtuner.web import remote_subscription_service as service
from fluxtuner.web.m3u_import import _profile_id
from fluxtuner.web.payloads import station_payload
from fluxtuner.web.security import SESSION_COOKIE_NAME

router = APIRouter(prefix="/api/stations/subscriptions")


def _authorize(request: Request, *, mutation: bool = True) -> int:
    user = guards.require_authenticated_user(
        request, auth_required_detail="Authentication required."
    )
    if mutation:
        guards.require_csrf(request, csrf_error_detail="CSRF token is missing or invalid.")
    return int(user["id"])


def _session(request: Request) -> str:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Session required.")
    return token


def _catalog_label(display_name: str | None, url: str, source_id: int) -> str:
    """Build a safe, concise label without exposing URL credentials or query tokens."""
    if display_name and display_name.strip():
        return display_name.strip()
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    # Only expose the well-known owner/repository prefix, never branch, file,
    # path, userinfo, or query fragments that could contain secret material.
    if host == "raw.githubusercontent.com":
        pieces = parsed.path.strip("/").split("/")
        if len(pieces) >= 4 and all(
            piece and all(char.isascii() and (char.isalnum() or char in "._-") for char in piece)
            for piece in pieces[:2]
        ):
            return f"{pieces[0]}/{pieces[1]}"
    return host or f"Catalog #{source_id}"


def _list_owned(user_id: int, profile: str | None) -> list[dict[str, Any]]:
    with closing(db.connect()) as conn:
        profile_id = _profile_id(conn, user_id=user_id, profile_name=profile)
        return [
            {
                "source_id": item["source_id"],
                "display_name": item.get("display_name"),
                "label": _catalog_label(
                    item.get("display_name"), str(item["catalog_url"]), int(item["source_id"])
                ),
                "revision": item["revision"],
                "refreshed_at": item["refreshed_at"],
            }
            for item in list_subscriptions(conn, profile_id=profile_id)
        ]


def _owned_catalog(
    user_id: int,
    profile: str | None,
    source_id: int,
) -> dict[str, Any]:
    with closing(db.connect()) as conn:
        profile_id = _profile_id(
            conn,
            user_id=user_id,
            profile_name=profile,
        )
        return get_subscription(
            conn,
            profile_id=profile_id,
            source_id=source_id,
        )


def _owned_url(
    user_id: int,
    profile: str | None,
    source_id: int,
) -> str:
    return str(_owned_catalog(user_id, profile, source_id)["catalog_url"])


def _check_creation_access(
    user_id: int,
    profile: str | None,
    url: str,
) -> None:
    """Reject invalid profile and duplicate URL before network I/O."""
    with closing(db.connect()) as conn:
        profile_id = _profile_id(
            conn,
            user_id=user_id,
            profile_name=profile,
        )
        duplicate = conn.execute(
            """
            SELECT 1 FROM remote_catalog_subscriptions
            WHERE profile_id = ? AND catalog_url = ?
            """,
            (profile_id, url),
        ).fetchone()
        if duplicate is not None:
            raise ValueError("Catalog is already subscribed.")


def _remove_owned(user_id: int, profile: str | None, source_id: int) -> None:
    with closing(db.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        profile_id = _profile_id(conn, user_id=user_id, profile_name=profile)
        delete_subscription(conn, profile_id=profile_id, source_id=source_id)
        conn.commit()


async def _download_catalog(
    url: str,
    *,
    etag: str | None = None,
    last_modified: str | None = None,
) -> ConditionalCollectionResult:
    """Download through the existing bounded and SSRF-protected transport."""
    try:
        return await asyncio.to_thread(
            fetch_conditional_remote_station_collection,
            url,
            SystemStreamTargetResolver(),
            etag=etag,
            last_modified=last_modified,
        )
    except (ValueError, OSError, TimeoutError, RuntimeError) as exc:
        raise HTTPException(
            status_code=502,
            detail="Could not retrieve the remote collection.",
        ) from exc


def _mark_unchanged(
    user_id: int,
    profile: str | None,
    source_id: int,
    revision: int,
) -> dict[str, Any]:
    """Accept HTTP 304 only for a still-current, committed catalog."""
    with closing(db.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        profile_id = _profile_id(
            conn,
            user_id=user_id,
            profile_name=profile,
        )
        current = mark_not_modified(
            conn,
            profile_id=profile_id,
            source_id=source_id,
            expected_revision=revision,
        )
        conn.commit()
    return {
        "status": "not_modified",
        "source_id": source_id,
        "revision": current,
        "not_modified": True,
    }


@router.get("")
async def subscriptions_list(
    request: Request,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user_id = _authorize(request, mutation=False)
    try:
        items = await asyncio.to_thread(_list_owned, user_id, profile)
        return {"subscriptions": items}
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


async def _read_subscription_input(request: Request) -> tuple[str, str | None]:
    """Parse a bounded URL + optional name request; keep remote import contracts unchanged."""
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="Expected a JSON URL request.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > 4096:
            raise HTTPException(status_code=413, detail="URL request exceeds 4 KiB.")
        data.extend(chunk)
    try:
        payload = json.loads(data)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=400, detail="Invalid JSON URL request.") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("url"), str):
        raise HTTPException(status_code=400, detail="A collection URL is required.")
    url = payload["url"]
    if not url or len(url) > 2048:
        raise HTTPException(status_code=400, detail="Invalid collection URL length.")
    name = payload.get("display_name")
    if name is not None:
        if not isinstance(name, str) or len(name) > 120:
            raise HTTPException(status_code=400, detail="Invalid catalog name.")
        name = name.strip() or None
    return url, name


@router.post("")
async def subscriptions_create(
    request: Request,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user_id = _authorize(request)
    _session(request)
    url, display_name = await _read_subscription_input(request)
    try:
        await asyncio.to_thread(
            _check_creation_access,
            user_id,
            profile,
            url,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None

    result = await _download_catalog(url)
    if result.status != 200 or result.data is None:
        raise HTTPException(
            status_code=502,
            detail="Initial catalog must return a complete snapshot.",
        )
    try:
        return await asyncio.to_thread(
            service.create_from_snapshot,
            result.data,
            user_id=user_id,
            profile_name=profile,
            catalog_url=url,
            display_name=display_name,
            etag=result.etag,
            last_modified=result.last_modified,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=409,
            detail="Catalog is already subscribed.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


def _catalog_stations(
    user_id: int,
    profile: str | None,
    source_id: int,
) -> dict[str, Any]:
    """Read the committed catalog snapshot for one owned profile."""
    with closing(db.connect()) as conn:
        profile_id = _profile_id(conn, user_id=user_id, profile_name=profile)
        entries = get_entries(conn, profile_id=profile_id, source_id=source_id)
        subscription = get_subscription(conn, profile_id=profile_id, source_id=source_id)
        label = _catalog_label(None, str(subscription["catalog_url"]), source_id)
        source = conn.execute(
            "SELECT display_name FROM station_sources WHERE id = ? AND profile_id = ?",
            (source_id, profile_id),
        ).fetchone()
        if source is not None:
            label = _catalog_label(
                source["display_name"], str(subscription["catalog_url"]), source_id
            )
        stations = [station_payload({"name": entry.name, "url": entry.url}) for entry in entries]
        return {
            "label": label,
            "source_id": source_id,
            "count": len(stations),
            "stations": stations,
        }


@router.get("/{source_id}/stations")
async def subscriptions_stations(
    source_id: int,
    request: Request,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user_id = _authorize(request, mutation=False)
    try:
        return await asyncio.to_thread(_catalog_stations, user_id, profile, source_id)
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/{source_id}/preview")
async def subscriptions_preview(
    source_id: int,
    request: Request,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user_id = _authorize(request)
    session = _session(request)
    try:
        subscription = await asyncio.to_thread(
            _owned_catalog,
            user_id,
            profile,
            source_id,
        )
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    result = await _download_catalog(
        str(subscription["catalog_url"]),
        etag=subscription["etag"],
        last_modified=subscription["last_modified"],
    )

    try:
        if result.status == 304:
            return await asyncio.to_thread(
                _mark_unchanged,
                user_id,
                profile,
                source_id,
                int(subscription["revision"]),
            )

        if result.status != 200 or result.data is None:
            raise ValueError("Remote catalog returned no valid snapshot.")

        return await asyncio.to_thread(
            service.preview_refresh,
            result.data,
            user_id=user_id,
            profile_name=profile,
            source_id=source_id,
            session_token=session,
            etag=result.etag,
            last_modified=result.last_modified,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.post("/{source_id}/confirm")
async def subscriptions_confirm(
    source_id: int,
    request: Request,
    revision: int = Query(ge=1),
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user_id = _authorize(request)
    session = _session(request)
    receipt = request.headers.get("X-FluxTuner-Refresh-Receipt", "")
    try:
        return await asyncio.to_thread(
            service.confirm_stored_refresh,
            user_id=user_id,
            profile_name=profile,
            source_id=source_id,
            revision=revision,
            receipt=receipt,
            session_token=session,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None


@router.delete("/{source_id}")
async def subscriptions_delete(
    source_id: int,
    request: Request,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, str]:
    user_id = _authorize(request)
    try:
        await asyncio.to_thread(_remove_owned, user_id, profile, source_id)
        return {"status": "ok"}
    except (LookupError, ValueError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
