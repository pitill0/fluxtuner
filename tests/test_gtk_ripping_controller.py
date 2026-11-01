from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from fluxtuner.core.ripping import RippingAvailability
from fluxtuner.core.ripping_service import RippingService
from fluxtuner.gui import gtk_ripping_controller as controller_module
from fluxtuner.gui.gtk_ripping_controller import RippingController


def _harness(*, data_directory=Path("/tmp/fluxtuner-controller-test")):
    harness = SimpleNamespace(
        ripping_service=Mock(spec=RippingService),
        ripping_backend=Mock(),
        _ripping_shutting_down=False,
        _ripping_profile_context=Mock(return_value=(7, "Focus")),
        selected_station={"name": "Other station", "url": "https://example.com/other"},
        status_label=Mock(),
        schedule=Mock(return_value=23),
        remove=Mock(),
        dispatch=Mock(),
    )
    harness.ripping_service.start.return_value = 42
    harness.controller = RippingController(
        service=harness.ripping_service,
        check_availability=harness.ripping_backend.availability,
        profile_context=harness._ripping_profile_context,
        data_directory=data_directory,
        show_status=harness.status_label.set_text,
        is_shutting_down=lambda: harness._ripping_shutting_down,
        schedule=harness.schedule,
        remove_source=harness.remove,
        dispatch=harness.dispatch,
    )
    return harness


def _ripping_probe_harness():
    return _harness()


def _ripping_start_harness():
    harness = _harness()
    harness.controller.availability = RippingAvailability(True)
    harness.controller.ensure_timer = Mock()
    return harness


def _ripping_state_harness(tmp_path, *, state="running"):
    from fluxtuner.core.ripping import RippingRequest
    from fluxtuner.core.ripping_service import RippingSnapshot

    harness = _harness(data_directory=tmp_path)
    request = RippingRequest(
        station_name="Clicked station",
        source_url="https://example.com/clicked",
        output_directory=tmp_path / "tracks",
    )
    harness.ripping_service.wait.return_value = False
    harness.ripping_service.snapshot.return_value = RippingSnapshot(
        job_id=1, request=request, state=state
    )
    harness.controller._timer_id = 17
    return harness


def _ripping_stop_harness(tmp_path) -> SimpleNamespace:
    from fluxtuner.core.ripping import RippingRequest
    from fluxtuner.core.ripping_service import RippingSnapshot

    harness = _ripping_start_harness()
    harness.ripping_service.snapshot.return_value = RippingSnapshot(
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
    return harness


def test_ripping_controller_schedules_availability_probe(monkeypatch) -> None:
    harness = _ripping_probe_harness()
    worker = object()
    probe = Mock(return_value=worker)
    dispatcher = harness.dispatch
    monkeypatch.setattr(controller_module, "start_ripping_availability_probe", probe)

    harness.controller.probe_availability()

    probe.assert_called_once_with(
        check_availability=harness.ripping_backend.availability,
        dispatch=dispatcher,
        on_result=harness.controller.accept_availability,
    )
    harness.ripping_backend.availability.assert_not_called()
    assert harness.controller.probe_worker is worker
    harness.status_label.set_text.assert_not_called()


@pytest.mark.parametrize("available", [True, False])
@pytest.mark.parametrize("closing", [True, False])
def test_ripping_controller_accepts_availability_only_while_open(
    available: bool, closing: bool
) -> None:
    from fluxtuner.core.ripping import RippingAvailability

    harness = _ripping_probe_harness()
    harness._ripping_shutting_down = closing
    previous = harness.controller.availability
    selection = harness.selected_station
    result = RippingAvailability(available, "" if available else "Missing Brynse.")

    harness.controller.accept_availability(result)

    assert harness.controller.availability is (previous if closing else result)
    assert harness.selected_station is selection
    harness.status_label.set_text.assert_not_called()


def test_ripping_controller_contains_probe_scheduling_failure(monkeypatch) -> None:
    harness = _ripping_probe_harness()
    probe = Mock(side_effect=RuntimeError("worker unavailable"))
    monkeypatch.setattr(controller_module, "start_ripping_availability_probe", probe)

    harness.controller.probe_availability()

    assert harness.controller.probe_worker is None
    assert harness.controller.availability.available is False
    assert harness.controller.availability.reason == (
        "Could not schedule ripping availability check: worker unavailable"
    )
    harness.status_label.set_text.assert_not_called()


def test_ripping_controller_starts_clicked_station(tmp_path, monkeypatch) -> None:
    from uuid import UUID

    harness = _ripping_start_harness()
    selection = harness.selected_station
    clicked = {
        "name": "Clicked station",
        "url": "https://example.com/original",
        "url_resolved": "https://example.com/clicked",
    }
    run_id = UUID("12345678-1234-5678-1234-567812345678")
    new_uuid = Mock(return_value=run_id)
    monkeypatch.setattr(harness.controller, "_data_directory", tmp_path)
    monkeypatch.setattr(harness.controller, "_new_run_id", new_uuid)

    job_id = harness.controller.start(clicked)

    assert job_id == 42
    harness._ripping_profile_context.assert_called_once_with()
    new_uuid.assert_called_once_with()
    harness.ripping_service.start.assert_called_once()
    request = harness.ripping_service.start.call_args.args[0]
    assert request.source_url == "https://example.com/clicked"
    assert request.profile_id == 7
    assert request.profile_name == "Focus"
    assert request.output_directory == tmp_path / "rips" / "profile-7" / run_id.hex
    assert harness.selected_station is selection
    harness.status_label.set_text.assert_called_once_with("Starting ripping: Clicked station")
    harness.controller.ensure_timer.assert_called_once_with()


@pytest.mark.parametrize("closing", [False, True])
def test_ripping_controller_start_rejects_before_profile_lookup(monkeypatch, closing: bool) -> None:
    from fluxtuner.core.ripping import RippingAvailability

    harness = _ripping_start_harness()
    harness._ripping_shutting_down = closing
    harness.controller.availability = RippingAvailability(False, "Missing Brynse.")
    new_uuid = Mock()
    monkeypatch.setattr(harness.controller, "_new_run_id", new_uuid)

    job_id = harness.controller.start(
        {"name": "Clicked station", "url": "https://example.com/clicked"}
    )

    assert job_id is None
    harness._ripping_profile_context.assert_not_called()
    harness.ripping_service.start.assert_not_called()
    harness.controller.ensure_timer.assert_not_called()
    new_uuid.assert_not_called()
    if closing:
        harness.status_label.set_text.assert_not_called()
    else:
        harness.status_label.set_text.assert_called_once_with(
            "Ripping unavailable: Missing Brynse."
        )


def test_ripping_controller_start_contains_profile_failure(monkeypatch) -> None:
    from fluxtuner.core.ripping import RippingError

    harness = _ripping_start_harness()
    harness._ripping_profile_context.side_effect = RippingError("Ripping profile is unavailable.")
    new_uuid = Mock()
    monkeypatch.setattr(harness.controller, "_new_run_id", new_uuid)

    job_id = harness.controller.start(
        {"name": "Clicked station", "url": "https://example.com/clicked"}
    )

    assert job_id is None
    harness.ripping_service.start.assert_not_called()
    harness.controller.ensure_timer.assert_not_called()
    new_uuid.assert_not_called()
    harness.status_label.set_text.assert_called_once_with(
        "Could not start ripping: Ripping profile is unavailable."
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("starting", "Starting ripping: Clicked station"),
        ("running", "Ripping tracks: Clicked station"),
        ("stopping", "Stopping ripping: Clicked station"),
    ],
)
def test_gtk_ripping_state_refresh_projects_active_states(tmp_path, state, expected) -> None:
    harness = _ripping_state_harness(tmp_path, state=state)
    selection = harness.selected_station

    keep_polling = harness.controller.refresh()

    assert keep_polling is True
    assert harness.controller._timer_id == 17
    harness.ripping_service.wait.assert_called_once_with(timeout=0)
    harness.status_label.set_text.assert_called_once_with(expected)
    assert harness.selected_station is selection


def test_gtk_ripping_state_refresh_waits_for_workers_after_terminal_state(tmp_path) -> None:
    harness = _ripping_state_harness(tmp_path, state="completed")
    harness.ripping_service.wait.side_effect = [False, True]

    assert harness.controller.refresh() is True
    assert harness.controller._timer_id == 17
    assert harness.controller.refresh() is False
    assert harness.controller._timer_id is None
    harness.status_label.set_text.assert_called_once_with(
        "Ripping completed: Clicked station (0 tracks saved)"
    )
    assert harness.ripping_service.wait.call_args_list == [call(timeout=0), call(timeout=0)]


def test_gtk_ripping_state_refresh_deduplicates_within_each_job(tmp_path) -> None:
    from dataclasses import replace

    harness = _ripping_state_harness(tmp_path)

    assert harness.controller.refresh() is True
    harness.status_label.set_text.reset_mock()
    assert harness.controller.refresh() is True
    harness.status_label.set_text.assert_not_called()

    previous = harness.ripping_service.snapshot.return_value
    harness.ripping_service.snapshot.return_value = replace(previous, job_id=2)

    assert harness.controller.refresh() is True
    harness.status_label.set_text.assert_called_once_with("Ripping tracks: Clicked station")


def test_gtk_ripping_state_refresh_reports_late_outputs_after_failure(tmp_path) -> None:
    from dataclasses import replace

    from fluxtuner.core.ripping import RippedTrack, RippingResult

    harness = _ripping_state_harness(tmp_path, state="failed")
    snapshot = harness.ripping_service.snapshot.return_value
    snapshot = replace(snapshot, error=RuntimeError("stop failed"))
    harness.ripping_service.snapshot.return_value = snapshot

    assert harness.controller.refresh() is True
    harness.status_label.set_text.assert_called_once_with(
        "Ripping failed: Clicked station: stop failed"
    )
    harness.status_label.set_text.reset_mock()

    result = RippingResult(
        request=snapshot.request,
        codec="mp3",
        metaint=16000,
        stopped=True,
        tracks=(RippedTrack("Saved", snapshot.request.output_directory / "saved.mp3"),),
    )
    harness.ripping_service.snapshot.return_value = replace(snapshot, result=result)

    assert harness.controller.refresh() is True
    harness.status_label.set_text.assert_called_once_with(
        "Ripping failed: Clicked station: stop failed (1 track saved)"
        f" → {snapshot.request.output_directory}"
    )


def test_gtk_ripping_state_refresh_reads_snapshot_after_readiness_check(tmp_path) -> None:
    from dataclasses import replace

    harness = _ripping_state_harness(tmp_path, state="starting")
    initial = harness.ripping_service.snapshot.return_value

    def finish_during_check(*, timeout):
        assert timeout == 0
        harness.ripping_service.snapshot.return_value = replace(initial, state="stopped")
        return True

    harness.ripping_service.wait.side_effect = finish_during_check

    assert harness.controller.refresh() is False
    assert harness.controller._timer_id is None
    harness.status_label.set_text.assert_called_once_with(
        "Ripping stopped: Clicked station (0 tracks saved)"
    )


def test_gtk_ripping_state_refresh_discards_updates_during_shutdown(tmp_path) -> None:
    harness = _ripping_state_harness(tmp_path)
    harness._ripping_shutting_down = True

    assert harness.controller.refresh() is False
    assert harness.controller._timer_id is None
    harness.ripping_service.wait.assert_not_called()
    harness.ripping_service.snapshot.assert_not_called()
    harness.status_label.set_text.assert_not_called()


def test_gtk_ripping_state_refresh_without_job_finishes_silently(tmp_path) -> None:
    harness = _ripping_state_harness(tmp_path)
    harness.ripping_service.wait.return_value = True
    harness.ripping_service.snapshot.return_value = None

    assert harness.controller.refresh() is False
    assert harness.controller._timer_id is None
    harness.status_label.set_text.assert_not_called()


def test_ripping_controller_start_failure_does_not_schedule_timer(tmp_path, monkeypatch) -> None:
    harness = _ripping_start_harness()
    harness.ripping_service.start.side_effect = RuntimeError("Another job is active.")
    selection = harness.selected_station
    monkeypatch.setattr(harness.controller, "_data_directory", tmp_path)

    job_id = harness.controller.start(
        {"name": "Clicked station", "url": "https://example.com/clicked"},
    )

    assert job_id is None
    harness.controller.ensure_timer.assert_not_called()
    assert harness.selected_station is selection
    harness.status_label.set_text.assert_called_once_with(
        "Could not start ripping: Another job is active."
    )


@pytest.mark.parametrize("available", [True, False])
def test_ripping_controller_stop_uses_clicked_station(tmp_path, available) -> None:
    from fluxtuner.core.ripping import RippingAvailability

    harness = _ripping_stop_harness(tmp_path)
    harness.controller.availability = RippingAvailability(available)
    selection = harness.selected_station

    harness.controller.stop(
        {
            "name": "Clicked station",
            "url": "https://example.com/original",
            "url_resolved": "https://example.com/clicked",
        },
    )

    harness._ripping_profile_context.assert_called_once_with()
    harness.ripping_service.stop.assert_called_once_with()
    harness.ripping_service.wait.assert_not_called()
    harness.controller.ensure_timer.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with("Stopping ripping: Running station")
    assert harness.selected_station is selection


@pytest.mark.parametrize("case", ["other_station", "other_profile", "completed", "no_job"])
def test_ripping_controller_stop_rejects_unrelated_job(tmp_path, case) -> None:
    from dataclasses import replace

    harness = _ripping_stop_harness(tmp_path)
    station = {"name": "Clicked station", "url": "https://example.com/clicked"}
    if case == "other_station":
        station["url"] = "https://example.com/other"
    elif case == "other_profile":
        harness._ripping_profile_context.return_value = (8, "Other profile")
    elif case == "completed":
        snapshot = harness.ripping_service.snapshot.return_value
        harness.ripping_service.snapshot.return_value = replace(snapshot, state="completed")
    else:
        harness.ripping_service.snapshot.return_value = None
    selection = harness.selected_station

    harness.controller.stop(station)

    harness.ripping_service.stop.assert_not_called()
    harness.ripping_service.wait.assert_not_called()
    harness.controller.ensure_timer.assert_not_called()
    harness.status_label.set_text.assert_not_called()
    assert harness.selected_station is selection


def test_ripping_controller_stop_contains_profile_failure(tmp_path) -> None:
    from fluxtuner.core.ripping import RippingError

    harness = _ripping_stop_harness(tmp_path)
    harness._ripping_profile_context.side_effect = RippingError("Ripping profile is unavailable.")

    harness.controller.stop({"name": "Clicked station", "url": "https://example.com/clicked"})

    harness.ripping_service.stop.assert_not_called()
    harness.controller.ensure_timer.assert_not_called()
    harness.status_label.set_text.assert_called_once_with(
        "Could not stop ripping: Ripping profile is unavailable."
    )


def test_ripping_controller_stop_during_shutdown_is_ignored(tmp_path) -> None:
    harness = _ripping_stop_harness(tmp_path)
    harness._ripping_shutting_down = True

    harness.controller.stop({"name": "Clicked station", "url": "https://example.com/clicked"})

    harness._ripping_profile_context.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    harness.controller.ensure_timer.assert_not_called()
    harness.status_label.set_text.assert_not_called()


def test_ripping_controller_stop_reports_failure_and_keeps_tracking(tmp_path) -> None:
    from fluxtuner.core.ripping import RippingError

    harness = _ripping_stop_harness(tmp_path)
    harness.ripping_service.stop.side_effect = RippingError("Stop worker unavailable.")

    harness.controller.stop({"name": "Clicked station", "url": "https://example.com/clicked"})

    harness.ripping_service.stop.assert_called_once_with()
    harness.ripping_service.wait.assert_not_called()
    harness.controller.ensure_timer.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with(
        "Could not stop ripping: Stop worker unavailable."
    )


def test_ripping_timer_schedules_once_and_runs_on_dispatch():
    harness = _harness()
    harness.ripping_service.wait.return_value = False
    harness.ripping_service.snapshot.return_value = None

    harness.controller.ensure_timer()
    harness.controller.ensure_timer()

    harness.schedule.assert_called_once_with(200, harness.controller.refresh)
    harness.ripping_service.wait.assert_not_called()
    callback = harness.schedule.call_args.args[1]
    assert callback() is True
    harness.ripping_service.wait.assert_called_once_with(timeout=0)


@pytest.mark.parametrize("closing,timer_id", [(True, None), (False, 17)])
def test_ripping_timer_rejects_shutdown_or_duplicate(closing, timer_id):
    harness = _harness()
    harness._ripping_shutting_down = closing
    harness.controller._timer_id = timer_id
    harness.controller.ensure_timer()
    assert harness.controller._timer_id == timer_id
    harness.schedule.assert_not_called()


def test_ripping_monitor_cancellation_removes_source_once_without_stopping_backend():
    harness = _harness()
    harness.controller.ensure_timer()
    harness._ripping_shutting_down = True

    harness.controller.stop_monitoring()
    harness.controller.stop_monitoring()

    harness.remove.assert_called_once_with(23)
    assert harness.controller._timer_id is None
    harness.ripping_service.stop.assert_not_called()
    harness.ripping_service.wait.assert_not_called()
    assert harness.controller.refresh() is False
    harness.status_label.set_text.assert_not_called()


def test_ripping_probe_is_not_scheduled_during_shutdown(monkeypatch):
    harness = _harness()
    harness._ripping_shutting_down = True
    probe = Mock()
    monkeypatch.setattr(controller_module, "start_ripping_availability_probe", probe)
    harness.controller.probe_availability()
    probe.assert_not_called()


@pytest.mark.parametrize("action", ["start", "stop"])
def test_ripping_projection_error_is_not_reclassified_or_retried(tmp_path, action):
    harness = _ripping_stop_harness(tmp_path)
    harness.status_label.set_text.side_effect = RuntimeError("projection failed")

    with pytest.raises(RuntimeError, match="projection failed"):
        getattr(harness.controller, action)(
            {"name": "Clicked station", "url": "https://example.com/clicked"}
        )

    getattr(harness.ripping_service, action).assert_called_once()
    harness.status_label.set_text.assert_called_once()
    harness.controller.ensure_timer.assert_not_called()
