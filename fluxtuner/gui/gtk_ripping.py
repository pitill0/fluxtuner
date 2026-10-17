from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from fluxtuner.core.ripping import RippingAvailability
from fluxtuner.core.ripping_requests import build_ripping_request
from fluxtuner.core.ripping_service import RippingService


@dataclass(frozen=True)
class RippingStartResult:
    status: str
    job_id: int | None = None


def coordinate_ripping_start(
    station: dict[str, Any],
    *,
    availability: RippingAvailability,
    service: RippingService,
    data_directory: Path,
    profile_id: int,
    profile_name: str | None,
    run_id: UUID,
) -> RippingStartResult:
    """Submit an explicit station using an already checked capability."""
    if not availability.available:
        return RippingStartResult(
            status=f"Ripping unavailable: {availability.reason}",
        )

    try:
        request = build_ripping_request(
            station,
            data_directory=data_directory,
            profile_id=profile_id,
            profile_name=profile_name,
            run_id=run_id,
        )
        job_id = service.start(request)
    except Exception as exc:  # noqa: BLE001 - translated into a UI result.
        return RippingStartResult(status=f"Could not start ripping: {exc}")

    return RippingStartResult(
        status=f"Starting ripping: {request.station_name}",
        job_id=job_id,
    )
