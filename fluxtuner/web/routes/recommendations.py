# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Authenticated user-to-user recommendation endpoints."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any, Literal

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from fluxtuner.core import db, share_inbox, share_resolution, share_service
from fluxtuner.web import context, guards
from fluxtuner.web.m3u_import import _profile_id

router = APIRouter(prefix="/api/recommendations")
required_body = Body(...)
optional_body = Body(default=None)
_AUTH = "Authentication required."
_CSRF = "CSRF token is missing or invalid."
_UNAVAILABLE = "Recommendation unavailable."


class SendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    recipient_username: str = Field(min_length=1, max_length=80)
    kind: Literal["station", "playlist"]
    station_key: str | None = Field(default=None, max_length=4096)
    playlist_name: str | None = Field(default=None, max_length=120)


class ResolveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    destination_playlist_name: str | None = Field(default=None, max_length=120)


def _authorize(request: Request, *, mutation: bool) -> int:
    user = guards.require_authenticated_user(request, auth_required_detail=_AUTH)
    if mutation:
        guards.require_csrf(request, csrf_error_detail=_CSRF)
    return int(user["id"])


def _selected_profile(conn: sqlite3.Connection, user_id: int, name: str | None) -> int:
    try:
        return _profile_id(conn, user_id=user_id, profile_name=context.effective_profile_name(name))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Profile unavailable.") from exc


@router.get("")
def recommendations_list(
    request: Request,
    direction: Literal["inbox", "sent"] = Query(default="inbox"),
    status: Literal["all", "pending", "resolved"] = Query(default="all"),
    limit: int = Query(default=20, ge=1, le=share_inbox.MAX_PAGE_SIZE),
    offset: int = Query(default=0, ge=0, le=share_inbox.MAX_OFFSET),
) -> dict[str, Any]:
    user_id = _authorize(request, mutation=False)
    try:
        with closing(db.connect()) as conn:
            items = share_inbox.list_shares(
                conn,
                user_id=user_id,
                direction=direction,
                status=status,
                limit=limit,
                offset=offset,
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=_UNAVAILABLE) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Recommendations unavailable.") from exc
    return {"recommendations": items}


@router.post("", status_code=201)
def recommendations_create(
    request: Request,
    payload: SendRequest = required_body,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, int]:
    user_id = _authorize(request, mutation=True)
    if (payload.kind == "station") != (payload.station_key is not None):
        raise HTTPException(status_code=400, detail="Invalid recommendation selection.")
    if (payload.kind == "playlist") != (payload.playlist_name is not None):
        raise HTTPException(status_code=400, detail="Invalid recommendation selection.")

    try:
        with closing(db.connect()) as conn:
            profile_id = _selected_profile(conn, user_id, profile)
            identifier = share_service.create_share(
                conn,
                sender_user_id=user_id,
                recipient_username=payload.recipient_username,
                source_profile_id=profile_id,
                kind=payload.kind,
                station_key=payload.station_key,
                playlist_name=payload.playlist_name,
            )
    except ValueError as exc:
        # Suppress recipient existence, inbox capacity, and source ownership details.
        raise HTTPException(status_code=409, detail="Recommendation could not be sent.") from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Recommendations unavailable.") from exc
    return {"id": identifier}


def _resolve(
    request: Request,
    identifier: int,
    action: Literal["accept", "reject"],
    payload: ResolveRequest | None,
    profile: str | None,
) -> dict[str, Any]:
    user_id = _authorize(request, mutation=True)
    try:
        with closing(db.connect()) as conn:
            destination_id = (
                _selected_profile(conn, user_id, profile) if action == "accept" else None
            )
            return share_resolution.resolve_share(
                conn,
                recipient_user_id=user_id,
                share_id=identifier,
                action=action,
                destination_profile_id=destination_id,
                destination_playlist_name=(
                    payload.destination_playlist_name if payload is not None else None
                ),
            )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=_UNAVAILABLE) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Recommendations unavailable.") from exc


@router.post("/{identifier}/accept")
def recommendations_accept(
    request: Request,
    identifier: int = Path(..., gt=0),
    payload: ResolveRequest | None = optional_body,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    return _resolve(request, identifier, "accept", payload, profile)


@router.post("/{identifier}/reject")
def recommendations_reject(
    request: Request,
    identifier: int = Path(..., gt=0),
) -> dict[str, Any]:
    return _resolve(request, identifier, "reject", None, None)
