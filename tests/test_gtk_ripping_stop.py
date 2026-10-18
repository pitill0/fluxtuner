from __future__ import annotations

from dataclasses import replace
from unittest.mock import Mock

import pytest

from fluxtuner.core.ripping import RippingError, RippingRequest
from fluxtuner.core.ripping_service import RippingService, RippingSnapshot


@pytest.fixture
def active_snapshot(tmp_path) -> RippingSnapshot:
    return RippingSnapshot(
        job_id=42,
        request=RippingRequest(
            station_name="Running station",
            source_url="https://example.com/clicked",
            output_directory=tmp_path / "tracks",
            profile_id=7,
            profile_name="Focus",
        ),
        state="running",
    )


@pytest.mark.parametrize("state", ["starting", "running", "stopping"])
def test_gtk_ripping_stop_delegates_matching_active_station(active_snapshot, state) -> None:
    from fluxtuner.gui.gtk_ripping import (
        coordinate_ripping_stop,
        ripping_station_is_active,
    )

    snapshot = replace(active_snapshot, state=state)
    station = {
        "name": "Display name changed",
        "url": "https://example.com/original",
        "url_resolved": " https://example.com/clicked ",
    }
    service = Mock(spec=RippingService)
    service.snapshot.return_value = snapshot

    assert ripping_station_is_active(snapshot, station, profile_id=7) is True
    message = coordinate_ripping_stop(station, service=service, profile_id=7)

    assert message == "Stopping ripping: Running station"
    service.stop.assert_called_once_with()
    service.wait.assert_not_called()
    service.start.assert_not_called()


@pytest.mark.parametrize(
    "case",
    [
        "no_job",
        "other_station",
        "missing_url",
        "other_profile",
        "completed",
        "stopped",
        "failed",
    ],
)
def test_gtk_ripping_stop_rejects_unrelated_or_terminal_job(active_snapshot, case) -> None:
    from fluxtuner.gui.gtk_ripping import (
        coordinate_ripping_stop,
        ripping_station_is_active,
    )

    snapshot = active_snapshot
    station = {"name": "Clicked station", "url": "https://example.com/clicked"}
    profile_id = 7
    if case == "no_job":
        snapshot = None
    elif case == "other_station":
        station["url"] = "https://example.com/other"
    elif case == "missing_url":
        station.pop("url")
    elif case == "other_profile":
        profile_id = 8
    else:
        snapshot = replace(snapshot, state=case)
    service = Mock(spec=RippingService)
    service.snapshot.return_value = snapshot

    assert ripping_station_is_active(snapshot, station, profile_id=profile_id) is False
    message = coordinate_ripping_stop(station, service=service, profile_id=profile_id)

    assert message is None
    service.stop.assert_not_called()
    service.wait.assert_not_called()
    service.start.assert_not_called()


def test_gtk_ripping_stop_contains_service_failure(active_snapshot) -> None:
    from fluxtuner.gui.gtk_ripping import coordinate_ripping_stop

    service = Mock(spec=RippingService)
    service.snapshot.return_value = active_snapshot
    service.stop.side_effect = RippingError("Stop worker unavailable.")

    message = coordinate_ripping_stop(
        {"name": "Clicked station", "url": "https://example.com/clicked"},
        service=service,
        profile_id=7,
    )

    assert message == "Could not stop ripping: Stop worker unavailable."
    service.stop.assert_called_once_with()
    service.wait.assert_not_called()
