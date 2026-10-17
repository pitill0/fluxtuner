from __future__ import annotations

from pathlib import Path
from threading import Event, get_ident

import pytest

from fluxtuner.core.ripping import (
    RippingAvailability,
    RippingError,
    RippingRequest,
    RippingResult,
    RippingStarted,
)
from fluxtuner.core.ripping_service import RippingService


def test_service_runs_off_caller_thread_and_rejects_overlap(tmp_path: Path) -> None:
    class ControlledBackend:
        def __init__(self) -> None:
            self.entered = Event()
            self.release = Event()
            self.worker_ident = None

        def availability(self) -> RippingAvailability:
            return RippingAvailability(available=True)

        def run(self, request, *, on_started=None, on_track_written=None):
            self.worker_ident = get_ident()
            if on_started is not None:
                on_started(RippingStarted(codec="mp3", metaint=16000))
            self.entered.set()
            assert self.release.wait(timeout=5), "Backend was not released"
            return RippingResult(
                request=request,
                codec="mp3",
                metaint=16000,
                stopped=False,
            )

        def stop(self) -> None:
            self.release.set()

    backend = ControlledBackend()
    factory_threads = []

    def make_backend():
        factory_threads.append(get_ident())
        return backend

    request = RippingRequest(
        "Flux FM",
        "https://radio.example/stream",
        tmp_path / "tracks",
    )
    service = RippingService(backend_factory=make_backend)
    caller_ident = get_ident()
    job_id = service.start(request)

    try:
        assert backend.entered.wait(timeout=5), "Backend did not start"

        snapshot = service.snapshot()
        assert snapshot is not None
        assert snapshot.job_id == job_id
        assert snapshot.request is request
        assert snapshot.state == "running"
        assert snapshot.result is None
        assert backend.worker_ident != caller_ident
        assert factory_threads == [backend.worker_ident]

        with pytest.raises(RippingError, match="already active"):
            service.start(request)
    finally:
        backend.release.set()
        assert service.wait(timeout=5), "Worker did not terminate"

    completed = service.snapshot()
    assert completed is not None
    assert completed.job_id == job_id
    assert completed.state == "completed"
    assert completed.result is not None
    assert completed.result.request is request
    assert completed.result.stopped is False


@pytest.mark.parametrize("failure_stage", ["factory", "run"])
def test_service_preserves_failure_and_can_restart(tmp_path: Path, failure_stage: str) -> None:
    failure = RuntimeError("Backend failure")
    factory_calls = []

    class Backend:
        def __init__(self, fail: bool) -> None:
            self.fail = fail

        def availability(self) -> RippingAvailability:
            return RippingAvailability(available=True)

        def run(self, request, *, on_started=None, on_track_written=None):
            if self.fail:
                raise failure
            return RippingResult(
                request=request,
                codec="mp3",
                metaint=16000,
                stopped=False,
            )

        def stop(self) -> None:
            pass

    def make_backend():
        factory_calls.append(get_ident())
        first_attempt = len(factory_calls) == 1
        if first_attempt and failure_stage == "factory":
            raise failure
        return Backend(fail=first_attempt)

    request = RippingRequest(
        "Flux FM",
        "https://radio.example/stream",
        tmp_path / "tracks",
    )
    service = RippingService(backend_factory=make_backend)

    failed_job = service.start(request)
    assert service.wait(timeout=5)

    failed = service.snapshot()
    assert failed is not None
    assert failed.job_id == failed_job
    assert failed.state == "failed"
    assert failed.error is failure
    assert failed.result is None

    next_job = service.start(request)
    assert service.wait(timeout=5)

    completed = service.snapshot()
    assert completed is not None
    assert next_job > failed_job
    assert completed.job_id == next_job
    assert completed.state == "completed"
    assert completed.error is None
    assert completed.result is not None
    assert completed.result.request is request
    assert len(factory_calls) == 2
