from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock, call


def _ripping_shutdown_harness() -> SimpleNamespace:
    from fluxtuner.core.ripping_service import RippingService
    from fluxtuner.gui.gtk_shutdown import ShutdownController

    service = Mock(spec=RippingService)
    service.wait.return_value = True
    recording_manager = Mock()
    recording_manager.active_session = None
    harness = SimpleNamespace(
        ripping_service=service,
        recording_manager=recording_manager,
        _ripping_controller=Mock(),
        close_to_tray=False,
        close=Mock(),
        player=Mock(),
        usage_tracker=Mock(),
        _stop_usage_timer=Mock(),
        _stop_player_state_timer=Mock(),
        _stop_metadata_polling=Mock(),
        _show_quit_confirmation=Mock(),
        _show_shutdown_warning=Mock(),
        status_label=Mock(),
    )

    def stop_activity():
        harness._ripping_controller.stop_monitoring()
        harness._stop_usage_timer()
        harness._stop_player_state_timer()
        harness._stop_metadata_polling()
        harness.usage_tracker.stop()

    harness._shutdown_controller = ShutdownController(
        recording_manager=recording_manager,
        ripping_service=service,
        stop_activity=stop_activity,
        stop_playback=harness.player.stop,
        prepare_quit=lambda: setattr(harness, "close_to_tray", False),
        show_status=harness.status_label.set_text,
        show_confirmation=lambda **kwargs: harness._show_quit_confirmation(**kwargs),
        show_warning=lambda **kwargs: harness._show_shutdown_warning(**kwargs),
        schedule=Mock(return_value=23),
        remove_source=Mock(),
    )
    recording_stop = Mock()
    recording_stop.requested = False
    recording_stop.error = None
    recording_stop.poll.return_value = True
    harness._shutdown_controller._recording_stop = recording_stop
    return harness


def _shutdown_coordinator_harness():
    harness = _ripping_shutdown_harness()
    harness._shutdown_controller._recording_stop = Mock()
    harness._shutdown_controller._recording_stop.requested = False
    harness._shutdown_controller._recording_stop.poll.return_value = True
    harness._shutdown_controller._recording_stop.error = None
    harness._shutdown_controller._deadline = None
    harness._shutdown_controller._warning_open = False
    return harness


def test_gtk_ripping_shutdown_rejects_future_probe_results() -> None:
    harness = _ripping_shutdown_harness()

    harness._shutdown_controller.shutdown()

    assert harness._shutdown_controller.shutting_down is True


def test_gtk_ripping_window_shutdown_reports_pending_workers() -> None:
    harness = _ripping_shutdown_harness()
    harness.ripping_service.wait.return_value = False

    ready = harness._shutdown_controller.shutdown()

    assert ready is False
    assert harness._shutdown_controller.shutting_down is True
    harness.ripping_service.stop.assert_called_once_with()
    harness.ripping_service.wait.assert_called_once_with(timeout=0)
    harness.player.stop.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()


def test_gtk_ripping_window_shutdown_repeats_only_completion_check() -> None:
    harness = _ripping_shutdown_harness()
    harness.ripping_service.wait.side_effect = [False, True]
    harness.recording_manager.active_session = object()

    assert harness._shutdown_controller.shutdown() is False
    assert harness._shutdown_controller.shutdown() is True

    harness.ripping_service.stop.assert_called_once_with()
    assert harness.ripping_service.wait.call_args_list == [call(timeout=0), call(timeout=0)]
    harness._stop_usage_timer.assert_called_once_with()
    harness._stop_player_state_timer.assert_called_once_with()
    harness._stop_metadata_polling.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    harness._shutdown_controller._recording_stop.request.assert_called_once_with()
    harness.recording_manager.stop.assert_not_called()
    harness.player.stop.assert_called_once_with()


def test_gtk_ripping_window_shutdown_cancels_controller_monitoring_once() -> None:
    harness = _ripping_shutdown_harness()
    harness.ripping_service.wait.return_value = False

    assert harness._shutdown_controller.shutdown() is False
    assert harness._shutdown_controller.shutdown() is False

    harness._ripping_controller.stop_monitoring.assert_called_once_with()


def test_gtk_ripping_window_shutdown_contains_and_reports_stop_failure() -> None:
    from fluxtuner.core.ripping import RippingError

    harness = _ripping_shutdown_harness()
    error = RippingError("Stop worker unavailable.")
    harness.ripping_service.stop.side_effect = error
    harness.ripping_service.wait.side_effect = [False, True]

    assert harness._shutdown_controller.shutdown() is False
    # A Brynse stop failure must not authorize automatic exit.
    assert harness._shutdown_controller.shutdown() is False

    assert harness._shutdown_controller._ripping_stop.error is error
    harness.ripping_service.stop.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with(
        "Could not stop ripping: Stop worker unavailable."
    )
    harness.player.stop.assert_called_once_with()


def test_gtk_ripping_window_shutdown_without_workers_is_ready() -> None:
    harness = _ripping_shutdown_harness()

    assert harness._shutdown_controller.shutdown() is True

    harness.ripping_service.stop.assert_called_once_with()
    harness.ripping_service.wait.assert_called_once_with(timeout=0)
    harness.status_label.set_text.assert_not_called()


def test_gtk_ripping_close_wait_latest_completion_replaces_pending_callback(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.ripping_service.wait.side_effect = [False, False, True]
    schedule = Mock(return_value=23)
    monkeypatch.setattr(harness._shutdown_controller, "_schedule", schedule, raising=False)
    first = Mock()
    latest = Mock()

    assert harness._shutdown_controller.shutdown(on_complete=first) is False
    assert harness._shutdown_controller.shutdown(on_complete=latest) is False
    first.assert_not_called()
    latest.assert_not_called()

    assert harness._shutdown_controller.poll() is False

    # Preserve the first pending completion (Quit priority).
    first.assert_called_once_with()
    latest.assert_not_called()
    schedule.assert_called_once()


def test_gtk_ripping_close_wait_ready_needs_no_timer_or_callback(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    schedule = Mock()
    monkeypatch.setattr(harness._shutdown_controller, "_schedule", schedule, raising=False)
    completed = Mock()

    assert harness._shutdown_controller.shutdown(on_complete=completed) is True

    schedule.assert_not_called()
    completed.assert_not_called()
    assert harness._shutdown_controller._timer_id is None


def test_gtk_ripping_close_wait_ready_cancels_pending_timer(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.ripping_service.wait.side_effect = [False, True]
    schedule = Mock(return_value=23)
    remove = Mock()
    monkeypatch.setattr(harness._shutdown_controller, "_schedule", schedule, raising=False)
    monkeypatch.setattr(harness._shutdown_controller, "_remove_source", remove, raising=False)
    completed = Mock()

    assert harness._shutdown_controller.shutdown(on_complete=completed) is False
    assert harness._shutdown_controller.shutdown(on_complete=completed) is True

    remove.assert_called_once_with(23)
    assert harness._shutdown_controller._timer_id is None
    assert harness._shutdown_controller._on_complete is None
    completed.assert_not_called()

    assert harness._shutdown_controller.poll() is False
    assert harness.ripping_service.wait.call_count == 2
    completed.assert_not_called()


def test_gtk_quit_request_without_recordings_starts_shutdown(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness._shutdown_controller.confirmation_pending = False
    harness._show_quit_confirmation = Mock()
    completed = Mock()

    from fluxtuner.gui.gtk_ripping import shutdown_has_pending_recordings

    assert (
        shutdown_has_pending_recordings(
            recording_manager=harness.recording_manager,
            ripping_service=harness.ripping_service,
        )
        is False
    )

    harness._shutdown_controller.request_quit(on_complete=completed)

    harness._show_quit_confirmation.assert_not_called()
    harness.ripping_service.stop.assert_called_once_with()
    completed.assert_called_once_with()


def test_gtk_quit_request_requires_confirmation(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.recording_manager.active_session = object()
    harness._shutdown_controller.confirmation_pending = False
    harness._show_quit_confirmation = Mock()
    completed = Mock()

    harness._shutdown_controller.request_quit(on_complete=completed)

    harness._show_quit_confirmation.assert_called_once()
    harness.recording_manager.stop.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    harness.player.stop.assert_not_called()
    completed.assert_not_called()


def test_gtk_quit_confirmation_cancel_or_accept(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.recording_manager.active_session = object()
    harness._shutdown_controller.confirmation_pending = False
    callbacks = []
    completed = Mock()

    def capture_dialog(*, on_confirm, on_cancel):
        callbacks.append((on_confirm, on_cancel))

    harness._show_quit_confirmation = Mock(side_effect=capture_dialog)

    harness._shutdown_controller.request_quit(on_complete=completed)
    harness._shutdown_controller.request_quit(on_complete=completed)

    assert len(callbacks) == 1
    harness.ripping_service.stop.assert_not_called()
    harness.recording_manager.stop.assert_not_called()

    callbacks[0][1]()

    harness.ripping_service.stop.assert_not_called()
    harness.recording_manager.stop.assert_not_called()
    completed.assert_not_called()

    harness._shutdown_controller.request_quit(on_complete=completed)
    assert len(callbacks) == 2

    callbacks[1][0]()

    harness.ripping_service.stop.assert_called_once_with()
    harness._shutdown_controller._recording_stop.request.assert_called_once_with()
    harness.recording_manager.stop.assert_not_called()
    completed.assert_called_once_with()


def test_gtk_shutdown_combined_worker_pending_does_not_complete(monkeypatch) -> None:
    harness = _shutdown_coordinator_harness()
    harness.recording_manager.active_session = object()
    harness._shutdown_controller._recording_stop.requested = True
    harness._shutdown_controller._recording_stop.poll.return_value = False
    completed = Mock()
    monkeypatch.setattr(
        harness._shutdown_controller, "_schedule", Mock(return_value=29), raising=False
    )

    assert harness._shutdown_controller.shutdown(on_complete=completed) is False
    harness._shutdown_controller._recording_stop.request.assert_called_once_with()
    harness.recording_manager.stop.assert_not_called()
    completed.assert_not_called()
    assert harness._shutdown_controller._timer_id == 29


def test_gtk_shutdown_combined_worker_finishes_then_completes(monkeypatch) -> None:
    harness = _shutdown_coordinator_harness()
    harness._shutdown_controller.shutting_down = True
    harness._shutdown_controller._on_complete = Mock()
    harness._shutdown_controller._timer_id = 29
    harness._shutdown_controller._deadline = 100.0
    harness._shutdown_controller._recording_stop.requested = True
    harness._shutdown_controller._recording_stop.poll.side_effect = [False, True]
    harness._shutdown_controller._ripping_stop.poll = Mock(return_value=True)
    monkeypatch.setattr(harness._shutdown_controller, "_clock", lambda: 10.0)

    assert harness._shutdown_controller.poll() is True
    callback = harness._shutdown_controller._on_complete
    callback.assert_not_called()
    assert harness._shutdown_controller.poll() is False
    callback.assert_called_once_with()


def test_gtk_shutdown_deadline_offers_wait_or_force(monkeypatch) -> None:
    harness = _shutdown_coordinator_harness()
    harness._shutdown_controller.shutting_down = True
    harness._shutdown_controller._on_complete = Mock()
    finish = harness._shutdown_controller._on_complete
    harness._shutdown_controller._deadline = 10.0
    harness._shutdown_controller._timer_id = 29
    harness._shutdown_controller._ripping_stop.poll = Mock(return_value=False)
    harness._show_shutdown_warning = Mock()
    clock = [11.0, 11.0, 20.0]
    monkeypatch.setattr(harness._shutdown_controller, "_clock", lambda: clock.pop(0))

    assert harness._shutdown_controller.poll() is True
    harness._show_shutdown_warning.assert_called_once()
    callbacks = harness._show_shutdown_warning.call_args.kwargs
    finish.assert_not_called()
    assert harness._shutdown_controller.poll() is True
    harness._show_shutdown_warning.assert_called_once()

    callbacks["on_wait"]()
    assert harness._shutdown_controller._warning_open is False
    assert harness._shutdown_controller._deadline == 23.0
    finish.assert_not_called()
    assert harness._shutdown_controller.poll() is True
    assert harness._show_shutdown_warning.call_count == 1


def test_gtk_shutdown_failure_requires_explicit_decision(monkeypatch) -> None:
    harness = _shutdown_coordinator_harness()
    harness._shutdown_controller.shutting_down = True
    harness._shutdown_controller._on_complete = Mock()
    finish = harness._shutdown_controller._on_complete
    harness._shutdown_controller._timer_id = 29
    harness._shutdown_controller._deadline = 100.0
    harness._shutdown_controller._ripping_stop.poll = Mock(return_value=True)
    harness._shutdown_controller._recording_stop.error = RuntimeError("disk failure")
    harness._show_shutdown_warning = Mock()
    monkeypatch.setattr(harness._shutdown_controller, "_clock", lambda: 110.0)

    assert harness._shutdown_controller.poll() is True
    assert harness._show_shutdown_warning.call_args.kwargs["has_error"] is True
    finish.assert_not_called()
    harness._show_shutdown_warning.call_args.kwargs["on_force"]()
    finish.assert_called_once_with()


def test_shutdown_side_effect_order_and_duplicate_request():
    from fluxtuner.gui.gtk_shutdown import ShutdownController

    events = []
    manager = Mock()
    manager.active_session = object()
    service = Mock()
    service.stop.side_effect = lambda: events.append("ripping stop")
    service.wait.side_effect = lambda **kwargs: events.append("ripping poll") or False
    controller = ShutdownController(
        recording_manager=manager,
        ripping_service=service,
        stop_activity=lambda: events.append("activity stop"),
        stop_playback=lambda: events.append("playback stop"),
        prepare_quit=Mock(),
        show_status=Mock(),
        show_confirmation=Mock(),
        show_warning=Mock(),
        schedule=lambda interval, callback: events.append("schedule") or 23,
        remove_source=Mock(),
        clock=lambda: 10.0,
    )
    controller._recording_stop = Mock(requested=False, error=None)
    controller._recording_stop.request.side_effect = lambda: events.append("recording stop")
    completed = Mock()

    assert controller.shutdown(on_complete=completed) is False
    assert controller.shutdown(on_complete=completed) is False

    assert events == [
        "ripping stop",
        "activity stop",
        "recording stop",
        "playback stop",
        "ripping poll",
        "schedule",
        "ripping poll",
    ]
    assert controller.shutting_down is True
    assert controller._deadline == 22.0
    assert controller.pending_completion is completed
    completed.assert_not_called()


def test_quit_confirmation_settles_once_and_stale_accept_cannot_stop_after_cancel():
    harness = _ripping_shutdown_harness()
    harness.recording_manager.active_session = object()
    completed = Mock()
    harness._shutdown_controller.request_quit(on_complete=completed)
    callbacks = harness._show_quit_confirmation.call_args.kwargs

    callbacks["on_cancel"]()
    callbacks["on_confirm"]()
    callbacks["on_cancel"]()

    assert harness._shutdown_controller.confirmation_pending is False
    assert harness._shutdown_controller.shutting_down is False
    harness.ripping_service.stop.assert_not_called()
    harness._shutdown_controller._recording_stop.request.assert_not_called()
    completed.assert_not_called()
