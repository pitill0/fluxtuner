"""Run ripping jobs independently of any user interface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from threading import Lock, Thread, current_thread
from time import monotonic
from typing import Literal

from fluxtuner.core.ripping import (
    RippingBackend,
    RippingError,
    RippingRequest,
    RippingResult,
    RippingStarted,
)

RippingState = Literal["starting", "running", "stopping", "completed", "stopped", "failed"]


@dataclass(frozen=True)
class RippingSnapshot:
    job_id: int
    request: RippingRequest
    state: RippingState
    result: RippingResult | None = None
    error: Exception | None = None


class RippingService:
    """Own one worker at a time without importing GTK or a concrete backend."""

    def __init__(self, *, backend_factory: Callable[[], RippingBackend]) -> None:
        self._backend_factory = backend_factory
        self._lock = Lock()
        self._worker: Thread | None = None
        self._stop_worker: Thread | None = None
        self._backend: RippingBackend | None = None
        self._snapshot: RippingSnapshot | None = None
        self._next_job_id = 0

    def snapshot(self) -> RippingSnapshot | None:
        with self._lock:
            return self._snapshot

    def start(self, request: RippingRequest) -> int:
        with self._lock:
            if any(
                thread is not None and thread.is_alive()
                for thread in (self._worker, self._stop_worker)
            ):
                raise RippingError("A ripping job is already active.")

            self._stop_worker = None
            self._backend = None
            self._next_job_id += 1
            job_id = self._next_job_id
            self._snapshot = RippingSnapshot(
                job_id=job_id,
                request=request,
                state="starting",
            )
            worker = Thread(
                target=self._run,
                args=(job_id, request),
                name=f"fluxtuner-ripping-{job_id}",
                daemon=True,
            )
            self._worker = worker
            try:
                worker.start()
            except Exception as exc:
                error = RippingError(f"Could not start ripping worker: {exc}")
                self._worker = None
                self._snapshot = replace(
                    self._snapshot,
                    state="failed",
                    error=error,
                )
                raise error from exc
            return job_id

    def stop(self) -> None:
        """Delegate stopping without blocking the caller."""
        with self._lock:
            snapshot = self._snapshot
            if snapshot is None:
                return
            if snapshot.state == "starting":
                self._snapshot = replace(snapshot, state="stopping")
                return
            if snapshot.state != "running":
                return
            backend = self._backend
            if backend is None:
                raise RippingError("The active ripping backend is unavailable.")

            self._start_stop_locked(snapshot, backend)

    def _start_stop_locked(self, snapshot: RippingSnapshot, backend: RippingBackend) -> None:
        """Start the stop worker while the service lock is held."""
        self._snapshot = replace(snapshot, state="stopping")
        worker = Thread(
            target=self._stop,
            args=(snapshot.job_id, backend),
            name=f"fluxtuner-ripping-stop-{snapshot.job_id}",
            daemon=True,
        )
        self._stop_worker = worker
        try:
            worker.start()
        except Exception as exc:
            error = RippingError(f"Could not start ripping stop worker: {exc}")
            self._stop_worker = None
            self._snapshot = replace(snapshot, state="failed", error=error)
            raise error from exc

    def wait(self, *, timeout: float = 0.0) -> bool:
        """Wait up to timeout; blocking waits belong outside the UI thread."""
        deadline = monotonic() + max(0.0, timeout)
        with self._lock:
            worker = self._worker
            stop_worker = self._stop_worker
        if any(
            thread is current_thread() for thread in (worker, stop_worker) if thread is not None
        ):
            raise RippingError("A ripping worker cannot wait for itself.")
        if worker is not None:
            worker.join(timeout=max(0.0, deadline - monotonic()))

        with self._lock:
            if self._worker is not worker:
                return True
            stop_worker = self._stop_worker
        if stop_worker is current_thread():
            raise RippingError("A ripping worker cannot wait for itself.")
        if stop_worker is not None:
            stop_worker.join(timeout=max(0.0, deadline - monotonic()))

        with self._lock:
            if self._worker is not worker:
                return True
            return all(
                thread is None or not thread.is_alive()
                for thread in (self._worker, self._stop_worker)
            )

    def _stop(self, job_id: int, backend: RippingBackend) -> None:
        try:
            backend.stop()
        except Exception as exc:
            with self._lock:
                snapshot = self._snapshot
                if snapshot is not None and snapshot.job_id == job_id:
                    self._snapshot = replace(snapshot, state="failed", error=exc)

    def _run(self, job_id: int, request: RippingRequest) -> None:
        def on_started(_event: RippingStarted) -> None:
            with self._lock:
                snapshot = self._snapshot
                if snapshot is None or snapshot.job_id != job_id:
                    return
                if snapshot.state == "starting":
                    self._snapshot = replace(snapshot, state="running")
                elif snapshot.state == "stopping" and self._stop_worker is None:
                    backend = self._backend
                    if backend is not None:
                        self._start_stop_locked(snapshot, backend)

        try:
            backend = self._backend_factory()
            with self._lock:
                snapshot = self._snapshot
                if (
                    snapshot is not None
                    and snapshot.job_id == job_id
                    and snapshot.state == "stopping"
                ):
                    self._snapshot = replace(snapshot, state="stopped")
                    return
                self._backend = backend
            result = backend.run(request, on_started=on_started)
            finished = RippingSnapshot(
                job_id=job_id,
                request=request,
                state="stopped" if result.stopped else "completed",
                result=result,
            )
        except Exception as exc:
            finished = RippingSnapshot(
                job_id=job_id,
                request=request,
                state="failed",
                error=exc,
            )

        with self._lock:
            snapshot = self._snapshot
            if snapshot is not None and snapshot.job_id == job_id:
                self._backend = None
                if snapshot.error is not None:
                    finished = replace(finished, state="failed", error=snapshot.error)
                self._snapshot = finished
