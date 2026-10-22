from __future__ import annotations

from collections.abc import Callable
from threading import Thread


class AsyncRecordingStop:
    """Run one recording stop outside the GTK main thread."""

    def __init__(self, *, stop: Callable[[], object]) -> None:
        self._stop = stop
        self._worker: Thread | None = None
        self._requested = False
        self.error: Exception | None = None

    def request(self) -> None:
        """Start stopping once without waiting for completion."""
        if self._requested:
            return

        self._requested = True

        def run() -> None:
            try:
                self._stop()
            except Exception as exc:
                self.error = exc

        worker = Thread(
            target=run,
            name="fluxtuner-ffmpeg-shutdown",
            daemon=True,
        )
        self._worker = worker

        try:
            worker.start()
        except Exception as exc:
            self.error = exc
            self._worker = None

    @property
    def requested(self) -> bool:
        return self._requested

    def poll(self) -> bool:
        """Report worker completion without blocking."""
        return self._requested and (self._worker is None or not self._worker.is_alive())

    def wait(self, *, timeout: float = 0.0) -> bool:
        """Wait for completion; never call with a positive timeout in GTK."""
        worker = self._worker
        if not self._requested:
            return False
        if worker is not None:
            worker.join(timeout=max(0.0, timeout))
        return self.poll()
