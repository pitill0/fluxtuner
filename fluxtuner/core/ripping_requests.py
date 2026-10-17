"""Prepare explicit ripping requests without UI or database access."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from fluxtuner.core.ripping import RippingRequest
from fluxtuner.core.ripping_paths import ripping_output_directory


def build_ripping_request(
    station: dict[str, Any],
    *,
    data_directory: Path,
    profile_id: int,
    profile_name: str | None,
    run_id: UUID,
) -> RippingRequest:
    """Capture station, profile identity and destination before starting a job."""
    output_directory = ripping_output_directory(
        data_directory=data_directory,
        profile_id=profile_id,
        run_id=run_id,
    )
    return RippingRequest.from_station(
        station,
        output_directory=output_directory,
        profile_name=profile_name,
        profile_id=profile_id,
    )
