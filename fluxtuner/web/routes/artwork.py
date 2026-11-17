# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Authenticated artwork delivery through the protected shared cache."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from fluxtuner.core.artwork_service import ArtworkService
from fluxtuner.web import guards as web_guards
from fluxtuner.web.artwork_keys import load_or_create_artwork_signing_key
from fluxtuner.web.artwork_tokens import verify_artwork_reference
from fluxtuner.web.security import SESSION_COOKIE_NAME

router = APIRouter()
_NO_STORE = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"}


@lru_cache(maxsize=1)
def get_artwork_service() -> ArtworkService:
    """Share inflight lookups and negative backoff across requests in each worker."""
    return ArtworkService()


@lru_cache(maxsize=1)
def get_artwork_signing_key() -> bytes:
    """Read the persistent server key once per worker, never expose it to clients."""
    return load_or_create_artwork_signing_key()


@router.get("/api/artwork/{reference}", include_in_schema=False)
def get_artwork(
    reference: str,
    request: Request,
    service: Annotated[ArtworkService, Depends(get_artwork_service)],
    signing_key: Annotated[bytes, Depends(get_artwork_signing_key)],
) -> Response:
    """Only server-issued, unexpired, session-bound references may fetch images."""
    web_guards.require_authenticated_user(request, auth_required_detail="Authentication required.")
    session_token = request.cookies.get(SESSION_COOKIE_NAME, "")
    url = verify_artwork_reference(reference, session_token, signing_key)
    if url is None:
        raise HTTPException(status_code=404, detail="Artwork not available.")
    artwork = service.get(url)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Artwork not available.")
    return Response(content=artwork.data, media_type=artwork.mime_type, headers=_NO_STORE)
