from pathlib import Path
from types import SimpleNamespace

from fluxtuner.tui import FluxTunerTUI


class FakeRecordingManager:
    def __init__(self) -> None:
        self.active_session = None
        self.started_request = None
        self.stop_calls = 0

    def start(self, request):
        self.started_request = request
        self.active_session = SimpleNamespace(
            station_name=request.station_name,
            output_path=request.output_path,
        )
        return self.active_session

    def stop(self):
        self.stop_calls += 1
        active = self.active_session
        self.active_session = None
        if active is None:
            return None
        return SimpleNamespace(
            recording_id=7,
            station_name=active.station_name,
            output_path=active.output_path,
        )


class FakeTUI:
    def __init__(self) -> None:
        self.recording_available = True
        self.recording_manager = FakeRecordingManager()
        self.selected_station = {
            "name": "Test Radio",
            "url": "https://example.com/stream",
        }
        self.status = ""
        self.button_updates = 0
        self.notifications = []

    def set_status(self, message: str) -> None:
        self.status = message

    def update_record_button(self) -> None:
        self.button_updates += 1

    def stop_recording(self) -> None:
        FluxTunerTUI.stop_recording(self)  # type: ignore[arg-type]

    def notify(self, message: str, **kwargs) -> None:
        self.notifications.append((message, kwargs))


def test_tui_recording_starts_selected_station(monkeypatch, tmp_path: Path) -> None:
    app = FakeTUI()
    output = tmp_path / "test-radio.mka"
    monkeypatch.setattr("fluxtuner.tui.recording_output_path", lambda _name: output)

    FluxTunerTUI.toggle_recording(app)  # type: ignore[arg-type]

    request = app.recording_manager.started_request
    assert request is not None
    assert request.station_name == "Test Radio"
    assert request.source_url == "https://example.com/stream"
    assert request.output_path == output
    assert "Recording: Test Radio" in app.status


def test_tui_recording_toggle_stops_active_recording(monkeypatch, tmp_path: Path) -> None:
    app = FakeTUI()
    output = tmp_path / "test-radio.mka"
    monkeypatch.setattr("fluxtuner.tui.recording_output_path", lambda _name: output)

    FluxTunerTUI.toggle_recording(app)  # type: ignore[arg-type]
    FluxTunerTUI.toggle_recording(app)  # type: ignore[arg-type]

    assert app.recording_manager.stop_calls == 1
    assert app.recording_manager.active_session is None
    assert "Saved recording #7" in app.status


def test_tui_recording_does_not_require_playback(monkeypatch, tmp_path: Path) -> None:
    app = FakeTUI()
    output = tmp_path / "independent.mka"
    monkeypatch.setattr("fluxtuner.tui.recording_output_path", lambda _name: output)

    FluxTunerTUI.toggle_recording(app)  # type: ignore[arg-type]

    assert app.recording_manager.started_request is not None


def test_tui_recording_requires_selected_station() -> None:
    app = FakeTUI()
    app.selected_station = None

    FluxTunerTUI.toggle_recording(app)  # type: ignore[arg-type]

    assert app.recording_manager.started_request is None
    assert app.status == "No station selected to record."


def test_tui_recording_reports_missing_ffmpeg() -> None:
    app = FakeTUI()
    app.recording_available = False

    FluxTunerTUI.toggle_recording(app)  # type: ignore[arg-type]

    assert app.recording_manager.started_request is None
    assert "ffmpeg" in app.status
