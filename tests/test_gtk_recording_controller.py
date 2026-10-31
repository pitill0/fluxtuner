from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest

from fluxtuner.core.recording import RecordingManager
from fluxtuner.gui.gtk_recording import RecordingController


def _actions():
    manager = Mock(spec=RecordingManager)
    manager.active_session = None
    events = Mock()
    controller = RecordingController(
        manager=manager,
        show_status=events.status,
        refresh_controls=events.refresh,
    )
    events.attach_mock(manager.start, "start")
    events.attach_mock(manager.stop, "stop")
    return controller, manager, events


def _start(controller, **overrides):
    station = {"name": "Target station", "url_resolved": "https://radio.example/target"}
    options = {
        "available": True,
        "station_url": Mock(return_value="https://radio.example/target"),
        "station_name": Mock(return_value="Target station"),
        "output_path": Mock(return_value=Path("/tmp/target.mka")),
    }
    options.update(overrides)
    controller.start(station, **options)
    return station, options


def test_recording_start_uses_explicit_target_and_preserves_projection_order():
    controller, manager, events = _actions()

    station, options = _start(controller)

    request = manager.start.call_args.args[0]
    assert request.station_name == "Target station"
    assert request.source_url == "https://radio.example/target"
    assert request.output_path == Path("/tmp/target.mka")
    options["station_url"].assert_called_once_with(station)
    options["station_name"].assert_called_once_with(station)
    options["output_path"].assert_called_once_with("Target station")
    assert events.mock_calls == [
        call.start(request),
        call.refresh(),
        call.status("Recording: Target station → target.mka"),
    ]


def test_unavailable_recording_does_not_resolve_target_or_touch_backend():
    controller, manager, events = _actions()
    url, name, output = Mock(), Mock(), Mock()

    _start(controller, available=False, station_url=url, station_name=name, output_path=output)

    url.assert_not_called()
    name.assert_not_called()
    output.assert_not_called()
    manager.start.assert_not_called()
    assert events.mock_calls == [
        call.status("Recording unavailable: ffmpeg was not found in PATH."),
        call.refresh(),
    ]


@pytest.mark.parametrize("url", [None, ""])
def test_recording_without_url_does_not_build_a_destination(url):
    controller, manager, events = _actions()
    name, output = Mock(), Mock()

    _start(controller, station_url=Mock(return_value=url), station_name=name, output_path=output)

    name.assert_not_called()
    output.assert_not_called()
    manager.start.assert_not_called()
    assert events.mock_calls == [call.status("Selected station has no stream URL."), call.refresh()]


def test_recording_start_failure_reports_before_refreshing_controls():
    controller, manager, events = _actions()
    manager.start.side_effect = RuntimeError("backend unavailable")

    _start(controller)

    request = manager.start.call_args.args[0]
    assert events.mock_calls == [
        call.start(request),
        call.status("Could not start recording: backend unavailable"),
        call.refresh(),
    ]


@pytest.mark.parametrize("failing_step", ["station_url", "station_name", "output_path"])
def test_preparation_failure_keeps_existing_exception_boundary(failing_step):
    controller, manager, events = _actions()

    with pytest.raises(OSError, match="preparation failed"):
        _start(controller, **{failing_step: Mock(side_effect=OSError("preparation failed"))})

    manager.start.assert_not_called()
    assert events.mock_calls == []


def test_stop_without_active_recording_does_not_call_backend():
    controller, manager, events = _actions()

    controller.stop()

    manager.stop.assert_not_called()
    assert events.mock_calls == [call.status("No recording is active."), call.refresh()]


def test_stop_failure_preserves_manager_state_and_projection_order():
    controller, manager, events = _actions()
    active = object()
    manager.active_session = active
    manager.stop.side_effect = RuntimeError("finalization failed")

    controller.stop()

    assert manager.active_session is active
    assert events.mock_calls == [
        call.stop(),
        call.status("Could not finalize recording: finalization failed"),
        call.refresh(),
    ]


def test_stop_with_no_completed_record_refreshes_before_status():
    controller, manager, events = _actions()
    manager.active_session = object()
    manager.stop.return_value = None

    controller.stop()

    assert events.mock_calls == [call.stop(), call.refresh(), call.status("Recording stopped.")]


def test_stop_completed_record_preserves_persisted_identity_and_message():
    controller, manager, events = _actions()
    manager.active_session = object()
    manager.stop.return_value = SimpleNamespace(
        recording_id=42, station_name="Stored station", output_path=Path("/tmp/saved.mka")
    )

    controller.stop()

    assert events.mock_calls == [
        call.stop(),
        call.refresh(),
        call.status("Saved recording #42: Stored station → saved.mka"),
    ]


def test_controller_reads_current_manager_state_instead_of_copying_it():
    controller, manager, events = _actions()
    manager.active_session = object()
    manager.stop.return_value = None
    controller.stop()
    events.reset_mock()
    manager.active_session = None

    controller.stop()

    assert events.mock_calls == [call.status("No recording is active."), call.refresh()]


def test_projection_failure_does_not_repeat_or_reclassify_successful_start():
    controller, manager, events = _actions()
    events.refresh.side_effect = RuntimeError("projection failed")

    with pytest.raises(RuntimeError, match="projection failed"):
        _start(controller)

    manager.start.assert_called_once()
    events.status.assert_not_called()
