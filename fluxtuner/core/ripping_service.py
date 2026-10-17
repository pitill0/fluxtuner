"""Run ripping jobs independently of any user interface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from threading import Lock, Thread, current_thread
from typing import Literal

from fluxtuner.core.ripping import (
    RippingBackend,
    RippingError,
    RippingRequest,
    RippingResult,
    RippingStarted,
)

RippingState = Literal["starting", "running", "completed", "stopped", "failed"]


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
        self._snapshot: RippingSnapshot | None = None
        self._next_job_id = 0

    def snapshot(self) -> RippingSnapshot | None:
        with self._lock:
            return self._snapshot

    def start(self, request: RippingRequest) -> int:
        with self._lock:
            if self._worker is not None and self._worker.is_alive():
                raise RippingError("A ripping job is already active.")

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

    def wait(self, *, timeout: float = 0.0) -> bool:
        """Wait up to timeout; blocking waits belong outside the UI thread."""
        with self._lock:
            worker = self._worker
        if worker is None:
            return True
        if worker is current_thread():
            raise RippingError("A ripping worker cannot wait for itself.")
        worker.join(timeout=timeout)
        return not worker.is_alive()

    def _run(self, job_id: int, request: RippingRequest) -> None:
        def on_started(_event: RippingStarted) -> None:
            with self._lock:
                snapshot = self._snapshot
                if (
                    snapshot is not None
                    and snapshot.job_id == job_id
                    and snapshot.state == "starting"
                ):
                    self._snapshot = replace(snapshot, state="running")

        try:
            backend = self._backend_factory()
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
                self._snapshot = finished
