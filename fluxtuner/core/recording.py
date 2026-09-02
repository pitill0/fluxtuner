from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol


class RecordingError(RuntimeError):
    """Raised when a recording operation cannot be completed."""


class RecordingBackend(Protocol):
    """Minimal backend contract used by RecordingManager."""

    def start(self, source_url: str, output_path: Path) -> None: ...

    def stop(self) -> None: ...

    def is_recording(self) -> bool: ...


@dataclass(frozen=True)
class RecordingRequest:
    """Input required to start one recording session."""

    station_name: str
    source_url: str
    output_path: Path


@dataclass(frozen=True)
class RecordingSession:
    """Snapshot of one recording session."""

    station_name: str
    source_url: str
    output_path: Path
    started_at: str
    stopped_at: str | None = None

    @property
    def active(self) -> bool:
        return self.stopped_at is None


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class RecordingManager:
    """Coordinate one active recording independently from any UI."""

    def __init__(
        self,
        backend: RecordingBackend,
        *,
        clock: Callable[[], str] = _utc_now,
    ) -> None:
        self._backend = backend
        self._clock = clock
        self._active_session: RecordingSession | None = None

    @property
    def active_session(self) -> RecordingSession | None:
        return self._active_session

    def is_recording(self) -> bool:
        return self._active_session is not None and self._backend.is_recording()

    def start(self, request: RecordingRequest) -> RecordingSession:
        """Start one recording session."""
        if self._active_session is not None:
            raise RecordingError("A recording is already active.")

        station_name = request.station_name.strip()
        source_url = request.source_url.strip()

        if not station_name:
            raise RecordingError("Recording station name is required.")
        if not source_url:
            raise RecordingError("Recording source URL is required.")

        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._backend.start(source_url, request.output_path)

        session = RecordingSession(
            station_name=station_name,
            source_url=source_url,
            output_path=request.output_path,
            started_at=self._clock(),
        )
        self._active_session = session
        return session

    def stop(self) -> RecordingSession | None:
        """Stop the active recording and return its completed session."""
        session = self._active_session
        if session is None:
            return None

        self._backend.stop()
        completed = replace(session, stopped_at=self._clock())
        self._active_session = None
        return completed
