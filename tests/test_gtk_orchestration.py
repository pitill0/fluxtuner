from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call

import pytest


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
        glib = SimpleNamespace()
        pango = SimpleNamespace()

        repository.GLib = glib  # type: ignore[attr-defined]
        repository.Gtk = gtk  # type: ignore[attr-defined]
        repository.Pango = pango  # type: ignore[attr-defined]

        sys.modules["gi"] = gi
        sys.modules["gi.repository"] = repository

        from fluxtuner.gui import window

    return window


window = _import_window_module()


def _playback_harness(*, station: dict[str, object] | None = None) -> SimpleNamespace:
    player = Mock()
    player.supports_mute.return_value = False
    status_label = Mock()
    return SimpleNamespace(
        selected_station=station,
        current_station=None,
        player=player,
        player_backend_name="mpv",
        player_capabilities=object(),
        profile_name="default",
        usage_tracker=Mock(),
        restored_muted=False,
        status_label=status_label,
        _station_url=Mock(return_value="https://radio.example/stream"),
        _apply_player_preferences_before_start=Mock(),
        _set_player_volume_from_scale=Mock(),
        _set_player_mute=Mock(),
        update_now_playing=Mock(),
        update_data_usage=Mock(),
        update_player_state=Mock(),
        _ensure_usage_timer=Mock(),
        _ensure_player_state_timer=Mock(),
        _update_play_stop_button=Mock(),
        _render_results=Mock(),
    )


def test_gtk_successful_playback_commits_side_effects_once(monkeypatch) -> None:
    station = {"name": "Flux FM", "url_resolved": "https://radio.example/stream"}
    harness = _playback_harness(station=station)
    add_history = Mock()

    monkeypatch.setattr(window, "station_is_supported", lambda *_args: True)
    monkeypatch.setattr(window, "add_history", add_history)

    window.MainWindow.play_selected_station(harness)

    harness.player.play.assert_called_once_with("https://radio.example/stream")
    harness._apply_player_preferences_before_start.assert_called_once_with()
    harness._set_player_volume_from_scale.assert_called_once_with()
    harness._set_player_mute.assert_not_called()
    assert harness.current_station is station
    harness.usage_tracker.start.assert_called_once_with(station)
    add_history.assert_called_once_with(station, profile_name="default")
    harness.update_now_playing.assert_called_once_with()
    harness.update_data_usage.assert_called_once_with()
    harness.update_player_state.assert_called_once_with()
    harness._ensure_usage_timer.assert_called_once_with()
    harness._ensure_player_state_timer.assert_called_once_with()
    harness._update_play_stop_button.assert_called_once_with()
    harness._render_results.assert_called_once_with()
    assert harness.status_label.set_text.call_args_list == [
        call("Buffering…"),
        call("Playing"),
    ]


def test_gtk_playback_failure_does_not_commit_state_or_history(monkeypatch) -> None:
    station = {"name": "Flux FM", "url_resolved": "https://radio.example/stream"}
    harness = _playback_harness(station=station)
    harness.player.play.side_effect = RuntimeError("player unavailable")
    add_history = Mock()

    monkeypatch.setattr(window, "station_is_supported", lambda *_args: True)
    monkeypatch.setattr(window, "add_history", add_history)

    window.MainWindow.play_selected_station(harness)

    assert harness.current_station is None
    harness.usage_tracker.start.assert_not_called()
    add_history.assert_not_called()
    harness.update_now_playing.assert_not_called()
    harness._ensure_usage_timer.assert_not_called()
    harness._ensure_player_state_timer.assert_not_called()
    harness._render_results.assert_not_called()
    assert harness.status_label.set_text.call_args_list == [
        call("Buffering…"),
        call("Playback failed: player unavailable"),
    ]


@pytest.mark.parametrize(
    ("station", "supported", "url", "message"),
    [
        (None, True, "https://radio.example/stream", "Select a station first."),
        (
            {"name": "Unsupported"},
            False,
            "https://radio.example/stream",
            "Unsupported station",
        ),
        (
            {"name": "Missing URL"},
            True,
            None,
            "Selected station has no playable URL.",
        ),
    ],
)
def test_gtk_invalid_playback_requests_do_not_call_player(
    monkeypatch,
    station,
    supported: bool,
    url: str | None,
    message: str,
) -> None:
    harness = _playback_harness(station=station)
    harness._station_url.return_value = url

    monkeypatch.setattr(window, "station_is_supported", lambda *_args: supported)
    monkeypatch.setattr(window, "unsupported_station_message", lambda *_args: message)

    window.MainWindow.play_selected_station(harness)

    harness.player.play.assert_not_called()
    harness.usage_tracker.start.assert_not_called()
    assert harness.current_station is None
    harness.status_label.set_text.assert_called_once_with(message)


def test_gtk_stop_clears_runtime_and_projects_stopped_state() -> None:
    station = {"name": "Flux FM"}
    harness = SimpleNamespace(
        current_station=station,
        player=Mock(),
        usage_tracker=Mock(),
        status_label=Mock(),
        _stop_usage_timer=Mock(),
        _stop_player_state_timer=Mock(),
        _stop_metadata_polling=Mock(),
        update_data_usage=Mock(),
        update_now_playing=Mock(),
        update_player_state=Mock(),
        _update_play_stop_button=Mock(),
        _render_results=Mock(),
    )

    window.MainWindow.on_stop_clicked(harness, Mock())

    harness._stop_usage_timer.assert_called_once_with()
    harness._stop_player_state_timer.assert_called_once_with()
    harness.player.stop.assert_called_once_with()
    harness._stop_metadata_polling.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    assert harness.current_station is None
    harness.update_data_usage.assert_called_once_with()
    harness.update_now_playing.assert_called_once_with()
    harness.update_player_state.assert_called_once_with()
    harness._update_play_stop_button.assert_called_once_with()
    harness._render_results.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with("Stopped")


def test_gtk_close_stops_runtime_dependencies() -> None:
    harness = SimpleNamespace(
        player=Mock(),
        usage_tracker=Mock(),
        _stop_usage_timer=Mock(),
        _stop_player_state_timer=Mock(),
    )

    result = window.MainWindow.on_close_request(harness, Mock())

    assert result is False
    harness._stop_usage_timer.assert_called_once_with()
    harness._stop_player_state_timer.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    harness.player.stop.assert_called_once_with()


def test_gtk_close_contains_player_stop_failure() -> None:
    harness = SimpleNamespace(
        player=Mock(),
        usage_tracker=Mock(),
        _stop_usage_timer=Mock(),
        _stop_player_state_timer=Mock(),
    )
    harness.player.stop.side_effect = RuntimeError("already gone")

    result = window.MainWindow.on_close_request(harness, Mock())

    assert result is False
    harness.usage_tracker.stop.assert_called_once_with()
