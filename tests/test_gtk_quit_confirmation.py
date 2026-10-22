from __future__ import annotations

from unittest.mock import Mock

from fluxtuner.core.recording import RecordingManager
from fluxtuner.core.ripping_service import RippingService


def _dependencies(*, recording: bool, workers_finished: bool):
    manager = Mock(spec=RecordingManager)
    manager.active_session = object() if recording else None

    service = Mock(spec=RippingService)
    service.wait.return_value = workers_finished

    return manager, service


def _check(manager, service):
    from fluxtuner.gui.gtk_ripping import shutdown_has_pending_recordings

    return shutdown_has_pending_recordings(
        recording_manager=manager,
        ripping_service=service,
    )


def test_quit_confirmation_not_needed_without_pending_recordings() -> None:
    manager, service = _dependencies(recording=False, workers_finished=True)

    assert _check(manager, service) is False
    manager.stop.assert_not_called()
    service.stop.assert_not_called()


def test_quit_confirmation_required_for_ffmpeg_session() -> None:
    manager, service = _dependencies(recording=True, workers_finished=True)

    assert _check(manager, service) is True
    manager.stop.assert_not_called()
    service.stop.assert_not_called()


def test_quit_confirmation_required_for_live_brynse_workers() -> None:
    manager, service = _dependencies(recording=False, workers_finished=False)
    service.snapshot.return_value = Mock(state="completed")

    assert _check(manager, service) is True
    manager.stop.assert_not_called()
    service.stop.assert_not_called()


def test_quit_confirmation_required_when_both_recorders_are_active() -> None:
    manager, service = _dependencies(recording=True, workers_finished=False)

    assert _check(manager, service) is True
    manager.stop.assert_not_called()
    service.stop.assert_not_called()
