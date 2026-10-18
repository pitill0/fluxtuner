from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from fluxtuner.core.ripping import RippedTrack, RippingAvailability, RippingError
from fluxtuner.core.ripping_requests import build_ripping_request
from fluxtuner.core.ripping_service import RippingService, RippingSnapshot
from fluxtuner.core.stations import station_url


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


def start_ripping_availability_probe(
    *,
    check_availability: Callable[[], RippingAvailability],
    dispatch: Callable[[Callable[[], bool]], object],
    on_result: Callable[[RippingAvailability], None],
) -> threading.Thread:
    """Probe in a worker; dispatch must schedule delivery on the UI thread."""

    def probe() -> None:
        try:
            availability = check_availability()
        except Exception as exc:  # noqa: BLE001 - contained capability failure.
            availability = RippingAvailability(
                False,
                f"Could not check ripping availability: {exc}",
            )

        def deliver() -> bool:
            on_result(availability)
            return False

        dispatch(deliver)

    worker = threading.Thread(
        target=probe,
        name="fluxtuner-ripping-availability",
        daemon=True,
    )
    worker.start()
    return worker


def ripping_status(snapshot: RippingSnapshot) -> str:
    """Describe a snapshot using only finalized tracks as saved outputs."""
    station_name = snapshot.request.station_name
    active_labels = {
        "starting": "Starting ripping",
        "running": "Ripping tracks",
        "stopping": "Stopping ripping",
    }
    if snapshot.state in active_labels:
        return f"{active_labels[snapshot.state]}: {station_name}"

    tracks: tuple[RippedTrack, ...] = ()
    if snapshot.result is not None:
        tracks = snapshot.result.tracks
    elif isinstance(snapshot.error, RippingError):
        tracks = snapshot.error.tracks

    if snapshot.state == "failed":
        error = str(snapshot.error) if snapshot.error is not None else "Unknown error"
        message = f"Ripping failed: {station_name}: {error}"
        if not tracks:
            return message
    else:
        message = f"Ripping {snapshot.state}: {station_name}"

    count = len(tracks)
    noun = "track" if count == 1 else "tracks"
    message += f" ({count} {noun} saved)"
    if tracks:
        message += f" → {snapshot.request.output_directory}"
    return message


def ripping_station_is_active(
    snapshot: RippingSnapshot | None,
    station: dict[str, Any],
    *,
    profile_id: int,
) -> bool:
    """Match an explicit station and profile against an active operation."""
    return (
        snapshot is not None
        and snapshot.state in ("starting", "running", "stopping")
        and snapshot.request.profile_id == profile_id
        and snapshot.request.source_url == station_url(station)
    )


def coordinate_ripping_stop(
    station: dict[str, Any],
    *,
    service: RippingService,
    profile_id: int,
) -> str | None:
    """Delegate a matching operation's stop without waiting for its workers."""
    try:
        snapshot = service.snapshot()
        if snapshot is None or not ripping_station_is_active(
            snapshot, station, profile_id=profile_id
        ):
            return None
        service.stop()
    except Exception as exc:  # noqa: BLE001 - user-facing stop failure.
        return f"Could not stop ripping: {exc}"
    return f"Stopping ripping: {snapshot.request.station_name}"
