# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Owner-authenticated publication preferences for saved stations."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from typing import Any

from fastapi import APIRouter, Body, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from fluxtuner.core import db, public_station_visibility
from fluxtuner.web import context, guards
from fluxtuner.web.m3u_import import _profile_id

router = APIRouter(prefix="/api/stations")
_UNAVAILABLE = "Station unavailable."
required_body = Body(...)


class PublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    published: bool


def _authorize(request: Request, *, mutation: bool) -> int:
    user = guards.require_authenticated_user(
        request, auth_required_detail="Authentication required."
    )
    if mutation:
        guards.require_csrf(request, csrf_error_detail="CSRF token is missing or invalid.")
    return int(user["id"])


def _profile(conn: sqlite3.Connection, *, user_id: int, name: str | None) -> int:
    try:
        return _profile_id(conn, user_id=user_id, profile_name=context.effective_profile_name(name))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Profile unavailable.") from exc


@router.get("/{station_id}/publication")
def publication_status(
    request: Request,
    response: Response,
    station_id: int = Path(..., gt=0),
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, bool]:
    user_id = _authorize(request, mutation=False)
    response.headers["Cache-Control"] = "no-store"
    try:
        with closing(db.connect()) as conn:
            profile_id = _profile(conn, user_id=user_id, name=profile)
            published = public_station_visibility.get_station_publication(
                conn, user_id=user_id, profile_id=profile_id, station_id=station_id
            )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=_UNAVAILABLE) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Publication unavailable.") from exc
    return {"published": published}


@router.put("/{station_id}/publication")
def publication_update(
    request: Request,
    response: Response,
    station_id: int = Path(..., gt=0),
    payload: PublicationRequest = required_body,
    profile: str | None = Query(default=None, max_length=80),
) -> dict[str, Any]:
    user_id = _authorize(request, mutation=True)
    response.headers["Cache-Control"] = "no-store"
    try:
        with closing(db.connect()) as conn:
            profile_id = _profile(conn, user_id=user_id, name=profile)
            public_station_visibility.set_station_publication(
                conn,
                user_id=user_id,
                profile_id=profile_id,
                station_id=station_id,
                published=payload.published,
            )
            conn.commit()
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=_UNAVAILABLE) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail="Publication unavailable.") from exc
    return {"published": payload.published}
