from __future__ import annotations

from threading import Event
from unittest.mock import Mock

from fluxtuner.gui.gtk_recording_shutdown import AsyncRecordingStop


def test_async_stop_completes_without_blocking_caller() -> None:
    entered = Event()
    release = Event()

    def stop() -> None:
        entered.set()
        assert release.wait(timeout=2)

    worker = AsyncRecordingStop(stop=stop)
    try:
        worker.request()

        assert entered.wait(timeout=1)
        assert worker.poll() is False
        assert worker.error is None
    finally:
        release.set()

    assert worker.wait(timeout=2) is True
    assert worker.poll() is True
    assert worker.error is None


def test_async_stop_repeated_request_invokes_stop_once() -> None:
    stop = Mock()
    worker = AsyncRecordingStop(stop=stop)

    worker.request()
    worker.request()

    assert worker.wait(timeout=2) is True
    stop.assert_called_once_with()
    assert worker.error is None


def test_async_stop_failure_is_retained_after_worker_finishes() -> None:
    failure = RuntimeError("recording persistence failed")

    def stop() -> None:
        raise failure

    worker = AsyncRecordingStop(stop=stop)
    worker.request()

    assert worker.wait(timeout=2) is True
    assert worker.poll() is True
    assert worker.error is failure
