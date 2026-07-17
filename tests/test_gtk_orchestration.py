from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call

import pytest

from fluxtuner.gui.gtk_metadata import MetadataLifecycle
from fluxtuner.gui.gtk_playback import (
    coordinate_playback_start,
    coordinate_playback_stop,
)


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
        _stop_metadata_polling=Mock(),
    )

    result = window.MainWindow.on_close_request(harness, Mock())

    assert result is False
    harness._stop_usage_timer.assert_called_once_with()
    harness._stop_player_state_timer.assert_called_once_with()
    harness._stop_metadata_polling.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    harness.player.stop.assert_called_once_with()


def test_gtk_close_contains_player_stop_failure() -> None:
    harness = SimpleNamespace(
        player=Mock(),
        usage_tracker=Mock(),
        _stop_usage_timer=Mock(),
        _stop_player_state_timer=Mock(),
        _stop_metadata_polling=Mock(),
    )
    harness.player.stop.side_effect = RuntimeError("already gone")

    result = window.MainWindow.on_close_request(harness, Mock())

    assert result is False
    harness._stop_metadata_polling.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()


def test_gtk_playback_coordinator_applies_supported_preferences() -> None:
    station = {"name": "Flux FM"}
    player = Mock()
    player.supports_mute.return_value = True
    usage_tracker = Mock()
    before_start = Mock()
    after_start = Mock()
    apply_mute = Mock()
    add_history = Mock()

    result = coordinate_playback_start(
        station,
        player=player,
        player_backend_name="mpv",
        player_capabilities=object(),
        profile_name="default",
        restored_muted=True,
        station_supported=lambda *_args: True,
        unsupported_message=lambda *_args: "unsupported",
        station_url=lambda _station: "https://radio.example/stream",
        announce_buffering=Mock(),
        apply_preferences_before_start=before_start,
        apply_volume_after_start=after_start,
        apply_mute_after_start=apply_mute,
        usage_tracker=usage_tracker,
        add_history_entry=add_history,
    )

    assert result.success is True
    assert result.station is station
    before_start.assert_called_once_with()
    player.play.assert_called_once_with("https://radio.example/stream")
    after_start.assert_called_once_with()
    apply_mute.assert_called_once_with(True)
    usage_tracker.start.assert_called_once_with(station)
    add_history.assert_called_once_with(station, profile_name="default")


def test_gtk_playback_coordinator_rejects_before_side_effects() -> None:
    station = {"name": "Unsupported"}
    player = Mock()
    usage_tracker = Mock()
    add_history = Mock()

    result = coordinate_playback_start(
        station,
        player=player,
        player_backend_name="mpv",
        player_capabilities=object(),
        profile_name="default",
        restored_muted=False,
        station_supported=lambda *_args: False,
        unsupported_message=lambda *_args: "Unsupported station",
        station_url=lambda _station: "https://radio.example/stream",
        announce_buffering=Mock(),
        apply_preferences_before_start=Mock(),
        apply_volume_after_start=Mock(),
        apply_mute_after_start=Mock(),
        usage_tracker=usage_tracker,
        add_history_entry=add_history,
    )

    assert result.success is False
    assert result.status == "Unsupported station"
    player.play.assert_not_called()
    usage_tracker.start.assert_not_called()
    add_history.assert_not_called()


def test_gtk_playback_stop_coordinator_stops_player_and_usage() -> None:
    player = Mock()
    usage_tracker = Mock()

    result = coordinate_playback_stop(
        player=player,
        usage_tracker=usage_tracker,
    )

    assert result.status == "Stopped"
    player.stop.assert_called_once_with()
    usage_tracker.stop.assert_called_once_with()


def test_gtk_metadata_lifecycle_rejects_stale_and_duplicate_projection() -> None:
    lifecycle = MetadataLifecycle()
    generation = lifecycle.start()
    metadata = {
        "artist": "Current artist",
        "title": "Current title",
        "raw": "Current artist - Current title",
    }

    assert lifecycle.accept(generation - 1, metadata) is None

    projection = lifecycle.accept(generation, metadata)

    assert projection is not None
    assert projection.artist == "Current artist"
    assert projection.track == "Current title"
    assert projection.raw == "Current artist - Current title"
    assert lifecycle.accept(generation, metadata) is None


def test_gtk_metadata_lifecycle_stale_finish_does_not_unlock_current_fetch() -> None:
    lifecycle = MetadataLifecycle()
    generation = lifecycle.start()

    assert lifecycle.begin_fetch() == generation
    assert lifecycle.begin_fetch() is None

    lifecycle.finish_fetch(generation - 1)

    assert lifecycle.fetch_in_progress is True

    lifecycle.finish_fetch(generation)

    assert lifecycle.fetch_in_progress is False


def test_gtk_metadata_projection_remains_in_main_window() -> None:
    lifecycle = MetadataLifecycle()
    generation = lifecycle.start()
    harness = SimpleNamespace(
        _metadata_lifecycle=lifecycle,
        artist_detail_label=Mock(),
        track_detail_label=Mock(),
    )
    metadata = {
        "artist": "Current artist",
        "title": "Current title",
        "raw": "Current artist - Current title",
    }

    first = window.MainWindow._update_metadata_labels(
        harness,
        generation,
        metadata,
    )
    second = window.MainWindow._update_metadata_labels(
        harness,
        generation,
        metadata,
    )

    assert first is False
    assert second is False
    harness.artist_detail_label.set_text.assert_called_once_with("Current artist")
    harness.track_detail_label.set_text.assert_called_once_with("Current title")


def test_gtk_stop_invalidates_in_flight_metadata(monkeypatch) -> None:
    source_remove = Mock()
    monkeypatch.setattr(window.GLib, "source_remove", source_remove, raising=False)
    lifecycle = MetadataLifecycle()
    lifecycle.start()
    assert lifecycle.begin_fetch() is not None
    previous_generation = lifecycle.generation

    harness = SimpleNamespace(
        _metadata_lifecycle=lifecycle,
        _metadata_timer_id=42,
        _clear_metadata_labels=Mock(),
    )

    window.MainWindow._stop_metadata_polling(harness)

    assert lifecycle.generation == previous_generation + 1
    assert lifecycle.fetch_in_progress is False
    assert lifecycle.last_raw is None
    assert harness._metadata_timer_id is None
    source_remove.assert_called_once_with(42)
    harness._clear_metadata_labels.assert_called_once_with()


def test_gtk_metadata_worker_contains_fetch_failure(monkeypatch) -> None:
    idle_add = Mock()
    monkeypatch.setattr(window.GLib, "idle_add", idle_add, raising=False)
    monkeypatch.setattr(
        window,
        "fetch_stream_metadata",
        Mock(side_effect=RuntimeError("metadata unavailable")),
    )

    harness = SimpleNamespace(
        _metadata_fetch_finished=Mock(),
        _update_metadata_labels=Mock(),
    )

    window.MainWindow._metadata_worker(
        harness,
        "https://radio.example/stream",
        9,
    )

    idle_add.assert_called_once_with(harness._metadata_fetch_finished, 9)


def test_gtk_stale_search_success_does_not_replace_current_view() -> None:
    current_stations = [{"name": "Current"}]
    stale_stations = [{"name": "Stale"}]
    harness = SimpleNamespace(
        _search_generation=2,
        active_playlist_tag="focus",
        last_search_results=current_stations,
        stations=current_stations,
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        _set_view_status=Mock(),
    )

    result = window.MainWindow._search_finished(
        harness,
        1,
        stale_stations,
    )

    assert result is False
    assert harness.active_playlist_tag == "focus"
    assert harness.last_search_results is current_stations
    assert harness.stations is current_stations
    harness._render_results.assert_not_called()
    harness._update_playlist_status.assert_not_called()
    harness._set_view_status.assert_not_called()


def test_gtk_current_search_success_projects_results() -> None:
    stations = [{"name": "Current"}]
    harness = SimpleNamespace(
        _search_generation=3,
        active_playlist_tag="focus",
        last_search_results=[],
        stations=[],
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        _set_view_status=Mock(),
    )

    result = window.MainWindow._search_finished(
        harness,
        3,
        stations,
    )

    assert result is False
    assert harness.active_playlist_tag is None
    assert harness.last_search_results is stations
    assert harness.stations is stations
    harness._render_results.assert_called_once_with()
    harness._update_playlist_status.assert_called_once_with()
    harness._set_view_status.assert_called_once_with("Search results", 1)


def test_gtk_stale_search_failure_does_not_replace_current_status() -> None:
    harness = SimpleNamespace(
        _search_generation=5,
        status_label=Mock(),
    )

    result = window.MainWindow._search_failed(
        harness,
        4,
        "old failure",
    )

    assert result is False
    harness.status_label.set_text.assert_not_called()

    window.MainWindow._search_failed(
        harness,
        5,
        "current failure",
    )

    harness.status_label.set_text.assert_called_once_with("Search failed: current failure")


def test_gtk_search_worker_binds_callbacks_to_generation(monkeypatch) -> None:
    idle_add = Mock()
    monkeypatch.setattr(window.GLib, "idle_add", idle_add, raising=False)

    class ImmediateThread:
        def __init__(self, *, target, daemon):
            assert daemon is True
            self.target = target

        def start(self) -> None:
            self.target()

    monkeypatch.setattr(window.threading, "Thread", ImmediateThread)

    harness = SimpleNamespace(
        _search_generation=7,
        search_entry=SimpleNamespace(get_text=lambda: " jazz "),
        country_entry=SimpleNamespace(get_text=lambda: " Spain "),
        min_bitrate_entry=SimpleNamespace(get_text=lambda: "128"),
        status_label=Mock(),
        search_service=SimpleNamespace(
            search=Mock(
                return_value=SimpleNamespace(
                    stations=[{"name": "Jazz FM"}],
                )
            )
        ),
        _search_failed=Mock(),
        _search_finished=Mock(),
    )

    window.MainWindow.on_search_clicked(harness, Mock())

    assert harness._search_generation == 8
    harness.status_label.set_text.assert_called_once_with("Searching…")
    request = harness.search_service.search.call_args.args[0]
    assert request.query == "jazz"
    assert request.country == "Spain"
    assert request.min_bitrate == 128
    assert request.limit == 50
    idle_add.assert_called_once_with(
        harness._search_finished,
        8,
        [{"name": "Jazz FM"}],
    )
