# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query, Request

from fluxtuner.web import guards as web_guards
from fluxtuner.web.metadata import (
    MetadataCacheSnapshot,
    MetadataCoordinator,
    StreamTargetValidationError,
)

AUTH_REQUIRED_DETAIL = "Authentication required."
INVALID_METADATA_URL_DETAIL = "Stream URL must be a valid HTTP or HTTPS URL."
METADATA_UNAVAILABLE_DETAIL = "Stream metadata service is unavailable."

router = APIRouter()


def _coordinator(request: Request) -> MetadataCoordinator:
    coordinator = getattr(request.app.state, "metadata_coordinator", None)
    if coordinator is None or not callable(getattr(coordinator, "get_or_schedule", None)):
        raise HTTPException(status_code=503, detail=METADATA_UNAVAILABLE_DETAIL)
    return cast(MetadataCoordinator, coordinator)


def _snapshot_payload(snapshot: MetadataCacheSnapshot) -> dict[str, Any]:
    return {
        "url": snapshot.url,
        "status": snapshot.status.value,
        "metadata": dict(snapshot.metadata) if snapshot.metadata is not None else None,
        "failure_count": snapshot.failure_count,
    }


@router.get("/api/metadata")
def stream_metadata(
    request: Request,
    url: str = Query(..., min_length=1, max_length=2048),
) -> dict[str, Any]:
    """Return cached metadata state and schedule a bounded refresh when due."""
    web_guards.require_authenticated_user(
        request,
        auth_required_detail=AUTH_REQUIRED_DETAIL,
    )

    try:
        snapshot = _coordinator(request).get_or_schedule(url)
    except StreamTargetValidationError as exc:
        raise HTTPException(status_code=400, detail=INVALID_METADATA_URL_DETAIL) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=METADATA_UNAVAILABLE_DETAIL) from exc

    return _snapshot_payload(snapshot)
