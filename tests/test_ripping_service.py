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


def test_service_stop_delegates_without_blocking_caller(tmp_path: Path) -> None:
    entered_run = Event()
    release_run = Event()
    entered_stop = Event()
    release_stop = Event()
    stop_threads: list[int] = []
    caller_thread = get_ident()

    class Backend:
        def availability(self) -> RippingAvailability:
            return RippingAvailability(available=True)

        def run(self, request, *, on_started=None, on_track_written=None):
            if on_started is not None:
                on_started(RippingStarted(codec="mp3", metaint=16000))
            entered_run.set()
            assert release_run.wait(timeout=5)
            return RippingResult(
                request=request,
                codec="mp3",
                metaint=16000,
                stopped=True,
            )

        def stop(self) -> None:
            stop_threads.append(get_ident())
            entered_stop.set()
            assert release_stop.wait(timeout=5)
            release_run.set()

    backend = Backend()
    service = RippingService(backend_factory=lambda: backend)
    request = RippingRequest(
        station_name="Test station",
        source_url="https://example.com/stream",
        output_directory=tmp_path,
    )

    try:
        job_id = service.start(request)
        assert entered_run.wait(timeout=5)

        service.stop()

        assert entered_stop.wait(timeout=5)
        assert stop_threads[0] != caller_thread
        snapshot = service.snapshot()
        assert snapshot is not None
        assert snapshot.job_id == job_id
        assert snapshot.state == "stopping"
        assert not service.wait(timeout=0)

        with pytest.raises(RippingError, match="already active"):
            service.start(request)

        release_stop.set()
        assert service.wait(timeout=5)
        snapshot = service.snapshot()
        assert snapshot is not None
        assert snapshot.job_id == job_id
        assert snapshot.state == "stopped"
        assert snapshot.error is None
        assert snapshot.result is not None
        assert snapshot.result.stopped
    finally:
        release_stop.set()
        release_run.set()
        assert service.wait(timeout=5)


def test_service_preserves_stop_failure_and_can_restart(tmp_path: Path) -> None:
    entered_run = Event()
    release_run = Event()
    failure = RippingError("Backend stop failure")
    factory_calls: list[int] = []

    class Backend:
        def __init__(self, *, first_job: bool) -> None:
            self.first_job = first_job

        def availability(self) -> RippingAvailability:
            return RippingAvailability(available=True)

        def run(self, request, *, on_started=None, on_track_written=None):
            if on_started is not None:
                on_started(RippingStarted(codec="mp3", metaint=16000))
            if self.first_job:
                entered_run.set()
                assert release_run.wait(timeout=5)
            return RippingResult(
                request=request,
                codec="mp3",
                metaint=16000,
                stopped=self.first_job,
            )

        def stop(self) -> None:
            release_run.set()
            raise failure

    def factory():
        factory_calls.append(get_ident())
        return Backend(first_job=len(factory_calls) == 1)

    service = RippingService(backend_factory=factory)
    request = RippingRequest(
        station_name="Test station",
        source_url="https://example.com/stream",
        output_directory=tmp_path,
    )

    try:
        first_job = service.start(request)
        assert entered_run.wait(timeout=5)
        service.stop()
        assert service.wait(timeout=5)

        failed = service.snapshot()
        assert failed is not None
        assert failed.job_id == first_job
        assert failed.state == "failed"
        assert failed.error is failure
        assert failed.result is not None
        assert failed.result.request is request
        assert failed.result.stopped

        second_job = service.start(request)
        assert second_job > first_job
        assert service.wait(timeout=5)

        completed = service.snapshot()
        assert completed is not None
        assert completed.job_id == second_job
        assert completed.state == "completed"
        assert completed.error is None
        assert completed.result is not None
        assert not completed.result.stopped
        assert len(factory_calls) == 2
    finally:
        release_run.set()
        assert service.wait(timeout=5)
