from __future__ import annotations

from unittest.mock import Mock
from uuid import UUID

from fluxtuner.core.ripping import RippingAvailability
from fluxtuner.core.ripping_service import RippingService
from fluxtuner.gui.gtk_ripping import coordinate_ripping_start

RUN_ID = UUID("12345678-1234-5678-1234-567812345678")


def test_gtk_ripping_start_submits_explicit_station_and_profile(tmp_path) -> None:
    service = Mock(spec=RippingService)
    service.start.return_value = 42
    station = {
        "name": "Clicked station",
        "url": "https://example.com/original",
        "url_resolved": "https://example.com/resolved",
    }

    result = coordinate_ripping_start(
        station,
        availability=RippingAvailability(True),
        service=service,
        data_directory=tmp_path,
        profile_id=7,
        profile_name="Focus",
        run_id=RUN_ID,
    )

    service.start.assert_called_once()
    request = service.start.call_args.args[0]
    assert request.station_name == "Clicked station"
    assert request.source_url == "https://example.com/resolved"
    assert request.profile_id == 7
    assert request.profile_name == "Focus"
    assert request.output_directory == tmp_path / "rips" / "profile-7" / RUN_ID.hex
    assert result.job_id == 42
    assert result.status == "Starting ripping: Clicked station"
    assert not request.output_directory.exists()


def test_gtk_ripping_unavailable_does_not_submit_job(tmp_path) -> None:
    service = Mock(spec=RippingService)

    result = coordinate_ripping_start(
        {"name": "Clicked station", "url": "https://example.com/stream"},
        availability=RippingAvailability(False, "Brynse is not installed."),
        service=service,
        data_directory=tmp_path,
        profile_id=7,
        profile_name="Focus",
        run_id=RUN_ID,
    )

    service.start.assert_not_called()
    assert result.job_id is None
    assert result.status == "Ripping unavailable: Brynse is not installed."


def test_gtk_ripping_start_contains_service_failure(tmp_path) -> None:
    service = Mock(spec=RippingService)
    service.start.side_effect = RuntimeError("Another ripping job is active.")

    result = coordinate_ripping_start(
        {"name": "Clicked station", "url": "https://example.com/stream"},
        availability=RippingAvailability(True),
        service=service,
        data_directory=tmp_path,
        profile_id=7,
        profile_name="Focus",
        run_id=RUN_ID,
    )

    service.start.assert_called_once()
    assert result.job_id is None
    assert result.status == "Could not start ripping: Another ripping job is active."
