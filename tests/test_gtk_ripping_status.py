from __future__ import annotations

import pytest

from fluxtuner.core.ripping import (
    RippedTrack,
    RippingError,
    RippingRequest,
    RippingResult,
)
from fluxtuner.core.ripping_service import RippingSnapshot


@pytest.fixture
def ripping_request(tmp_path) -> RippingRequest:
    return RippingRequest(
        station_name="Clicked station",
        source_url="https://example.com/stream",
        output_directory=tmp_path / "tracks",
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("starting", "Starting ripping: Clicked station"),
        ("running", "Ripping tracks: Clicked station"),
        ("stopping", "Stopping ripping: Clicked station"),
    ],
)
def test_gtk_ripping_status_distinguishes_active_states(ripping_request, state, expected) -> None:
    from fluxtuner.gui.gtk_ripping import ripping_status

    snapshot = RippingSnapshot(job_id=1, request=ripping_request, state=state)

    assert ripping_status(snapshot) == expected


@pytest.mark.parametrize("state", ["completed", "stopped"])
def test_gtk_ripping_status_reports_only_finalized_outputs(ripping_request, state) -> None:
    from fluxtuner.gui.gtk_ripping import ripping_status

    tracks = (
        RippedTrack("First", ripping_request.output_directory / "first.mp3"),
        RippedTrack("Second", ripping_request.output_directory / "second.mp3"),
    )
    result = RippingResult(
        request=ripping_request,
        codec="mp3",
        metaint=16000,
        stopped=state == "stopped",
        tracks=tracks,
        incomplete_track_title="Unfinished",
    )
    snapshot = RippingSnapshot(job_id=1, request=ripping_request, state=state, result=result)

    assert ripping_status(snapshot) == (
        f"Ripping {state}: Clicked station (2 tracks saved) → {ripping_request.output_directory}"
    )


def test_gtk_ripping_status_cancelled_before_run_has_no_output_claim(ripping_request) -> None:
    from fluxtuner.gui.gtk_ripping import ripping_status

    snapshot = RippingSnapshot(job_id=1, request=ripping_request, state="stopped")

    assert ripping_status(snapshot) == ("Ripping stopped: Clicked station (0 tracks saved)")


@pytest.mark.parametrize("track_source", ["error", "result"])
def test_gtk_ripping_status_preserves_outputs_on_failure(ripping_request, track_source) -> None:
    from fluxtuner.gui.gtk_ripping import ripping_status

    tracks = (RippedTrack("First", ripping_request.output_directory / "first.mp3"),)
    result = None
    error = RippingError("stream lost", tracks=tracks)
    if track_source == "result":
        error = RippingError("stream lost")
        result = RippingResult(
            request=ripping_request,
            codec="mp3",
            metaint=16000,
            stopped=True,
            tracks=tracks,
        )
    snapshot = RippingSnapshot(
        job_id=1,
        request=ripping_request,
        state="failed",
        result=result,
        error=error,
    )

    assert ripping_status(snapshot) == (
        "Ripping failed: Clicked station: stream lost (1 track saved)"
        f" → {ripping_request.output_directory}"
    )


def test_gtk_ripping_status_failure_without_outputs(ripping_request) -> None:
    from fluxtuner.gui.gtk_ripping import ripping_status

    snapshot = RippingSnapshot(
        job_id=1,
        request=ripping_request,
        state="failed",
        error=RuntimeError("stream lost"),
    )

    assert ripping_status(snapshot) == "Ripping failed: Clicked station: stream lost"
