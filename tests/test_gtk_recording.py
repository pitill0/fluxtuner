from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock


def _import_window_module():
    try:
        from fluxtuner.gui import window
    except ImportError as exc:
        if exc.name != "gi":
            raise

        gi = ModuleType("gi")
        gi.require_version = lambda *_args: None  # type: ignore[attr-defined]

        repository = ModuleType("gi.repository")

        class ApplicationWindow:
            pass

        gtk = SimpleNamespace(ApplicationWindow=ApplicationWindow)
        repository.GLib = SimpleNamespace()  # type: ignore[attr-defined]
        repository.Gtk = gtk  # type: ignore[attr-defined]
        repository.Pango = SimpleNamespace()  # type: ignore[attr-defined]

        sys.modules["gi"] = gi
        sys.modules["gi.repository"] = repository

        from fluxtuner.gui import window

    return window


window = _import_window_module()


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
            recording_id=9,
            station_name=active.station_name,
            output_path=active.output_path,
        )


def _recording_harness() -> SimpleNamespace:
    return SimpleNamespace(
        recording_available=True,
        recording_manager=FakeRecordingManager(),
        selected_station={
            "name": "Flux FM",
            "url_resolved": "https://radio.example/stream",
        },
        status_label=Mock(),
        record_button=Mock(),
        _station_url=Mock(return_value="https://radio.example/stream"),
        _station_display_name=Mock(return_value="Flux FM"),
        _update_record_button=Mock(),
    )


def test_gtk_recording_starts_selected_station(monkeypatch, tmp_path: Path) -> None:
    harness = _recording_harness()
    output = tmp_path / "flux-fm.mka"
    monkeypatch.setattr(window, "recording_output_path", lambda _name: output)

    window.MainWindow.start_selected_recording(harness)

    request = harness.recording_manager.started_request
    assert request is not None
    assert request.station_name == "Flux FM"
    assert request.source_url == "https://radio.example/stream"
    assert request.output_path == output
    harness._update_record_button.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with(f"Recording: Flux FM → {output.name}")


def test_gtk_record_button_stops_active_recording(monkeypatch, tmp_path: Path) -> None:
    harness = _recording_harness()
    output = tmp_path / "flux-fm.mka"
    monkeypatch.setattr(window, "recording_output_path", lambda _name: output)

    window.MainWindow.start_selected_recording(harness)
    harness._update_record_button.reset_mock()
    harness.status_label.set_text.reset_mock()

    harness.stop_recording = lambda: window.MainWindow.stop_recording(harness)
    window.MainWindow.on_record_clicked(harness, Mock())

    assert harness.recording_manager.stop_calls == 1
    assert harness.recording_manager.active_session is None
    harness._update_record_button.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with(
        f"Saved recording #9: Flux FM → {output.name}"
    )


def test_gtk_recording_does_not_depend_on_player(monkeypatch, tmp_path: Path) -> None:
    harness = _recording_harness()
    output = tmp_path / "independent.mka"
    monkeypatch.setattr(window, "recording_output_path", lambda _name: output)

    # The harness deliberately has no player/current_station attributes.
    window.MainWindow.start_selected_recording(harness)

    assert harness.recording_manager.started_request is not None


def test_gtk_recording_requires_selection() -> None:
    harness = _recording_harness()
    harness.selected_station = None

    window.MainWindow.start_selected_recording(harness)

    assert harness.recording_manager.started_request is None
    harness.status_label.set_text.assert_called_once_with("Select a station first.")


def test_gtk_recording_reports_missing_ffmpeg() -> None:
    harness = _recording_harness()
    harness.recording_available = False

    window.MainWindow.start_selected_recording(harness)

    assert harness.recording_manager.started_request is None
    harness.status_label.set_text.assert_called_once_with(
        "Recording unavailable: ffmpeg was not found in PATH."
    )


def test_gtk_shutdown_finalizes_active_recording() -> None:
    manager = FakeRecordingManager()
    manager.active_session = SimpleNamespace(
        station_name="Flux FM",
        output_path=Path("/tmp/flux-fm.mka"),
    )
    harness = SimpleNamespace(
        recording_manager=manager,
        player=Mock(),
        usage_tracker=Mock(),
        _stop_usage_timer=Mock(),
        _stop_player_state_timer=Mock(),
        _stop_metadata_polling=Mock(),
    )

    window.MainWindow.shutdown(harness)

    assert manager.stop_calls == 1
    harness.player.stop.assert_called_once_with()


def test_gtk_record_button_projection() -> None:
    harness = _recording_harness()

    window.MainWindow._update_record_button(harness)

    harness.record_button.set_label.assert_called_once_with("● Record")
    harness.record_button.set_tooltip_text.assert_called_once_with("Record selected station")
    harness.record_button.set_sensitive.assert_called_once_with(True)

    harness.record_button.reset_mock()
    harness.recording_manager.active_session = object()

    window.MainWindow._update_record_button(harness)

    harness.record_button.set_label.assert_called_once_with("■ Stop recording")
    harness.record_button.set_tooltip_text.assert_called_once_with("Stop recording")
    harness.record_button.set_sensitive.assert_called_once_with(True)
