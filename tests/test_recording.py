from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

import pytest

from fluxtuner.core.recording import (
    RecordingError,
    RecordingManager,
    RecordingRequest,
    RecordingSession,
)


class FakeRecordingBackend:
    def __init__(self) -> None:
        self.recording = False
        self.start_calls: list[tuple[str, Path]] = []
        self.stop_calls = 0

    def start(self, source_url: str, output_path: Path) -> None:
        self.start_calls.append((source_url, output_path))
        self.recording = True

    def stop(self) -> None:
        self.stop_calls += 1
        self.recording = False

    def is_recording(self) -> bool:
        return self.recording


def _request(tmp_path: Path) -> RecordingRequest:
    return RecordingRequest(
        station_name="Flux FM",
        source_url="https://radio.example/stream",
        output_path=tmp_path / "recordings" / "flux-fm.mp3",
    )


def test_recording_manager_starts_session(tmp_path: Path) -> None:
    backend = FakeRecordingBackend()
    manager = RecordingManager(
        backend,
        clock=lambda: "2026-09-02T12:00:00+00:00",
    )
    request = _request(tmp_path)

    session = manager.start(request)

    assert backend.start_calls == [(request.source_url, request.output_path)]
    assert request.output_path.parent.is_dir()
    assert session.station_name == "Flux FM"
    assert session.started_at == "2026-09-02T12:00:00+00:00"
    assert session.active is True
    assert manager.active_session is session
    assert manager.is_recording() is True


def test_recording_manager_rejects_parallel_session(tmp_path: Path) -> None:
    backend = FakeRecordingBackend()
    manager = RecordingManager(backend)
    manager.start(_request(tmp_path))

    with pytest.raises(RecordingError, match="already active"):
        manager.start(
            RecordingRequest(
                station_name="Other station",
                source_url="https://radio.example/other",
                output_path=tmp_path / "other.mp3",
            )
        )

    assert len(backend.start_calls) == 1


def test_recording_manager_stop_returns_completed_session(tmp_path: Path) -> None:
    backend = FakeRecordingBackend()
    timestamps = iter(
        [
            "2026-09-02T12:00:00+00:00",
            "2026-09-02T12:10:00+00:00",
        ]
    )
    manager = RecordingManager(backend, clock=lambda: next(timestamps))
    manager.start(_request(tmp_path))

    completed = manager.stop()

    assert completed is not None
    assert completed.active is False
    assert completed.stopped_at == "2026-09-02T12:10:00+00:00"
    assert backend.stop_calls == 1
    assert manager.active_session is None
    assert manager.is_recording() is False


def test_recording_manager_stop_is_noop_when_idle() -> None:
    backend = FakeRecordingBackend()
    manager = RecordingManager(backend)

    assert manager.stop() is None
    assert backend.stop_calls == 0


def test_recording_manager_start_failure_leaves_manager_idle(
    tmp_path: Path,
) -> None:
    backend = FakeRecordingBackend()
    backend.start = Mock(side_effect=RuntimeError("recorder failed"))
    manager = RecordingManager(backend)

    with pytest.raises(RuntimeError, match="recorder failed"):
        manager.start(_request(tmp_path))

    assert manager.active_session is None


@pytest.mark.parametrize(
    ("station_name", "source_url", "message"),
    [
        ("", "https://radio.example/stream", "station name"),
        ("Flux FM", "", "source URL"),
    ],
)
def test_recording_manager_rejects_incomplete_request(
    tmp_path: Path,
    station_name: str,
    source_url: str,
    message: str,
) -> None:
    backend = FakeRecordingBackend()
    manager = RecordingManager(backend)

    with pytest.raises(RecordingError, match=message):
        manager.start(
            RecordingRequest(
                station_name=station_name,
                source_url=source_url,
                output_path=tmp_path / "recording.mp3",
            )
        )

    assert backend.start_calls == []


class FakeRecordingStore:
    def __init__(self) -> None:
        self.saved_sessions = []

    def save(self, session) -> int:
        self.saved_sessions.append(session)
        return 42


def test_stop_persists_completed_session_and_returns_recording_id(tmp_path: Path) -> None:
    backend = FakeRecordingBackend()
    store = FakeRecordingStore()
    timestamps = iter(
        [
            "2026-09-02T12:00:00+00:00",
            "2026-09-02T12:00:20+00:00",
        ]
    )
    manager = RecordingManager(
        backend,
        clock=lambda: next(timestamps),
        store=store,
    )

    manager.start(
        RecordingRequest(
            station_name="Flux FM",
            source_url="https://radio.example/stream",
            output_path=tmp_path / "recording.mka",
        )
    )
    completed = manager.stop()

    assert completed is not None
    assert completed.recording_id == 42
    assert completed.stopped_at == "2026-09-02T12:00:20+00:00"
    assert store.saved_sessions == [
        RecordingSession(
            station_name="Flux FM",
            source_url="https://radio.example/stream",
            output_path=tmp_path / "recording.mka",
            started_at="2026-09-02T12:00:00+00:00",
            stopped_at="2026-09-02T12:00:20+00:00",
        )
    ]


def test_persistence_failure_leaves_manager_idle(tmp_path: Path) -> None:
    backend = FakeRecordingBackend()

    class FailingStore:
        def save(self, _session) -> int:
            raise RecordingError("database unavailable")

    timestamps = iter(
        [
            "2026-09-02T12:00:00+00:00",
            "2026-09-02T12:00:20+00:00",
        ]
    )
    manager = RecordingManager(
        backend,
        clock=lambda: next(timestamps),
        store=FailingStore(),
    )

    manager.start(
        RecordingRequest(
            station_name="Flux FM",
            source_url="https://radio.example/stream",
            output_path=tmp_path / "recording.mka",
        )
    )

    with pytest.raises(RecordingError, match="database unavailable"):
        manager.stop()

    assert manager.active_session is None
    assert manager.is_recording() is False


def test_stop_captures_timestamp_before_backend_shutdown(tmp_path: Path) -> None:
    events: list[str] = []

    class TimingBackend(FakeRecordingBackend):
        def stop(self) -> None:
            events.append("backend-stop")
            super().stop()

    timestamps = iter(
        [
            "2026-09-02T12:00:00+00:00",
            "2026-09-02T12:00:20+00:00",
        ]
    )

    def clock() -> str:
        events.append("clock")
        return next(timestamps)

    manager = RecordingManager(TimingBackend(), clock=clock)
    manager.start(
        RecordingRequest(
            station_name="Flux FM",
            source_url="https://radio.example/stream",
            output_path=tmp_path / "recording.mka",
        )
    )

    events.clear()
    completed = manager.stop()

    assert completed is not None
    assert completed.stopped_at == "2026-09-02T12:00:20+00:00"
    assert events == ["clock", "backend-stop"]
