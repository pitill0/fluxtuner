from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, call

import pytest
from gtk_library_helpers import bind_library_harness, bind_library_menu

from fluxtuner.gui.gtk_metadata import MetadataLifecycle
from fluxtuner.gui.gtk_playback import (
    coordinate_playback_start,
    coordinate_playback_stop,
)
from fluxtuner.gui.gtk_search import SearchLifecycle
from fluxtuner.gui.gtk_view_state import ViewState


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

from fluxtuner.gui import gtk_library as library_controller  # noqa: E402
from fluxtuner.gui import gtk_library_panel as library_panel  # noqa: E402


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
    harness = _ripping_shutdown_harness()
    harness._shutdown_controller.confirmation_pending = False
    harness.request_quit = lambda *, on_complete: window.MainWindow.request_quit(
        harness, on_complete=on_complete
    )

    result = window.MainWindow.on_close_request(harness, Mock())

    assert result is True
    harness.close.assert_called_once_with()
    harness.ripping_service.stop.assert_called_once_with()
    harness._stop_usage_timer.assert_called_once_with()
    harness._stop_player_state_timer.assert_called_once_with()
    harness._stop_metadata_polling.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    harness.player.stop.assert_called_once_with()


def test_gtk_close_to_tray_hides_without_stopping_runtime() -> None:
    harness = SimpleNamespace(
        _shutdown_controller=SimpleNamespace(close_authorized=False),
        close_to_tray=True,
        set_visible=Mock(),
        player=Mock(),
        usage_tracker=Mock(),
        _stop_usage_timer=Mock(),
        _stop_player_state_timer=Mock(),
        _stop_metadata_polling=Mock(),
    )

    result = window.MainWindow.on_close_request(harness, Mock())

    assert result is True
    harness.set_visible.assert_called_once_with(False)
    harness._stop_usage_timer.assert_not_called()
    harness._stop_player_state_timer.assert_not_called()
    harness._stop_metadata_polling.assert_not_called()
    harness.usage_tracker.stop.assert_not_called()
    harness.player.stop.assert_not_called()


def test_gtk_close_contains_player_stop_failure() -> None:
    harness = _ripping_shutdown_harness()
    harness._shutdown_controller.confirmation_pending = False
    harness.request_quit = lambda *, on_complete: window.MainWindow.request_quit(
        harness, on_complete=on_complete
    )
    harness.player.stop.side_effect = RuntimeError("already gone")

    result = window.MainWindow.on_close_request(harness, Mock())

    assert result is True
    harness.player.stop.assert_called_once_with()
    harness.close.assert_called_once_with()
    harness.ripping_service.stop.assert_called_once_with()
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


def test_gtk_search_lifecycle_only_accepts_latest_generation() -> None:
    lifecycle = SearchLifecycle()

    first = lifecycle.begin()
    second = lifecycle.begin()

    assert first == 1
    assert second == 2
    assert lifecycle.is_current(first) is False
    assert lifecycle.is_current(second) is True


def test_gtk_stale_search_success_does_not_replace_current_view() -> None:
    current_stations = [{"name": "Current"}]
    stale_stations = [{"name": "Stale"}]
    lifecycle = SearchLifecycle()
    lifecycle.begin()
    lifecycle.begin()
    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=ViewState(active_playlist_tag="focus"),
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
    assert harness._view_state.active_playlist_tag == "focus"
    assert harness.last_search_results is current_stations
    assert harness.stations is current_stations
    harness._render_results.assert_not_called()
    harness._update_playlist_status.assert_not_called()
    harness._set_view_status.assert_not_called()


def test_gtk_current_search_success_projects_results() -> None:
    stations = [{"name": "Current"}]
    lifecycle = SearchLifecycle()
    generation = lifecycle.begin()
    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=ViewState(active_playlist_tag="focus"),
        last_search_results=[],
        stations=[],
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        _set_view_status=Mock(),
    )

    result = window.MainWindow._search_finished(
        harness,
        generation,
        stations,
    )

    assert result is False
    assert harness._view_state.active_playlist_tag is None
    assert harness.last_search_results is stations
    assert harness.stations is stations
    harness._render_results.assert_called_once_with()
    harness._update_playlist_status.assert_called_once_with()
    harness._set_view_status.assert_called_once_with("Search results", 1)


def test_gtk_stale_search_failure_does_not_replace_current_status() -> None:
    lifecycle = SearchLifecycle()
    stale_generation = lifecycle.begin()
    current_generation = lifecycle.begin()
    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        status_label=Mock(),
    )

    result = window.MainWindow._search_failed(
        harness,
        stale_generation,
        "old failure",
    )

    assert result is False
    harness.status_label.set_text.assert_not_called()

    window.MainWindow._search_failed(
        harness,
        current_generation,
        "current failure",
    )

    harness.status_label.set_text.assert_called_once_with("Search failed: current failure")


def test_gtk_search_worker_binds_callbacks_to_lifecycle_generation(monkeypatch) -> None:
    idle_add = Mock()
    monkeypatch.setattr(window.GLib, "idle_add", idle_add, raising=False)

    class ImmediateThread:
        def __init__(self, *, target, daemon):
            assert daemon is True
            self.target = target

        def start(self) -> None:
            self.target()

    monkeypatch.setattr(window.threading, "Thread", ImmediateThread)

    lifecycle = SearchLifecycle()
    for _ in range(7):
        lifecycle.begin()

    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _selected_search_source=lambda: "radio-browser",
        profile_name="default",
        player_capabilities=None,
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

    assert lifecycle.generation == 8
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


def test_gtk_search_lifecycle_invalidate_rejects_in_flight_request() -> None:
    lifecycle = SearchLifecycle()
    generation = lifecycle.begin()

    invalidated_generation = lifecycle.invalidate()

    assert invalidated_generation == generation + 1
    assert lifecycle.is_current(generation) is False


def test_gtk_search_success_restores_search_view() -> None:
    lifecycle = SearchLifecycle()
    generation = lifecycle.begin()
    stations = [{"name": "Current"}]
    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=ViewState(
            current_view="favorites",
            active_playlist_tag="focus",
        ),
        last_search_results=[],
        stations=[],
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        _set_view_status=Mock(),
    )

    result = window.MainWindow._search_finished(
        harness,
        generation,
        stations,
    )

    assert result is False
    assert harness._view_state.current_view == "search"
    assert harness._view_state.active_playlist_tag is None
    assert harness.last_search_results is stations
    assert harness.stations is stations


def test_gtk_show_favorites_invalidates_pending_search(monkeypatch) -> None:
    lifecycle = SearchLifecycle()
    pending_generation = lifecycle.begin()
    favorites = [{"name": "Favorite"}]
    monkeypatch.setattr(library_controller, "load_favorites", Mock(return_value=favorites))

    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=ViewState(
            current_view="search",
            active_playlist_tag="focus",
        ),
        profile_name="default",
        stations=[],
        selected_station={"name": "Selected"},
        _refresh_favorite_cache=Mock(),
        _render_results=Mock(),
        _update_playlist_status=Mock(),
    )

    count = library_panel.LibraryPanel._show_all_favorites(bind_library_harness(harness))

    assert count == 1
    assert lifecycle.is_current(pending_generation) is False
    assert harness._view_state.current_view == "favorites"
    assert harness._view_state.active_playlist_tag is None
    assert harness.stations is favorites
    assert harness.selected_station is None


def test_gtk_show_history_invalidates_pending_search(monkeypatch) -> None:
    lifecycle = SearchLifecycle()
    pending_generation = lifecycle.begin()
    history = [{"name": "Recent"}]
    monkeypatch.setattr(library_controller, "load_history", Mock(return_value=history))

    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=ViewState(
            current_view="search",
            active_playlist_tag="focus",
        ),
        profile_name="default",
        stations=[],
        selected_station={"name": "Selected"},
        _refresh_favorite_cache=Mock(),
        _render_results=Mock(),
        _update_playlist_status=Mock(),
    )

    count = library_panel.LibraryPanel._show_history(bind_library_harness(harness))

    assert count == 1
    assert lifecycle.is_current(pending_generation) is False
    assert harness._view_state.current_view == "history"
    assert harness._view_state.active_playlist_tag is None
    assert harness.stations is history
    assert harness.selected_station is None


def test_gtk_tag_playlist_invalidates_pending_search() -> None:
    lifecycle = SearchLifecycle()
    pending_generation = lifecycle.begin()
    stations = [{"name": "Focus FM"}]
    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=ViewState(
            current_view="search",
            active_playlist_tag=None,
        ),
        stations=[],
        selected_station={"name": "Selected"},
        _playlist_tag_value=Mock(return_value="focus"),
        _all_favorite_playlist_tags=Mock(return_value=[]),
        _favorites_matching_favorite_tag=Mock(return_value=stations),
        _refresh_favorite_cache=Mock(),
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        _set_view_status=Mock(),
        status_label=Mock(),
    )

    library_panel.LibraryPanel.on_show_tag_playlist_clicked(bind_library_harness(harness), Mock())

    assert lifecycle.is_current(pending_generation) is False
    assert harness._view_state.current_view == "tag_playlist"
    assert harness._view_state.active_playlist_tag == "focus"
    assert harness.stations is stations
    assert harness.selected_station is None
    harness._set_view_status.assert_called_once_with(
        "Tag playlist",
        1,
        detail="focus",
    )


def test_gtk_random_tag_invalidates_pending_search(monkeypatch) -> None:
    lifecycle = SearchLifecycle()
    pending_generation = lifecycle.begin()
    stations = [{"name": "Focus FM"}]
    selected = stations[0]

    monkeypatch.setattr(
        library_panel,
        "filter_supported_stations",
        Mock(return_value=stations),
    )

    harness = SimpleNamespace(
        _search_lifecycle=lifecycle,
        _view_state=ViewState(
            current_view="search",
            active_playlist_tag=None,
        ),
        stations=[],
        selected_station=None,
        player_capabilities=object(),
        _playlist_tag_value=Mock(return_value="focus"),
        _all_favorite_playlist_tags=Mock(return_value=[]),
        _favorites_matching_favorite_tag=Mock(return_value=stations),
        _refresh_favorite_cache=Mock(),
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        play_selected_station=Mock(),
        status_label=Mock(),
    )

    monkeypatch.setattr(
        "secrets.choice",
        Mock(return_value=selected),
    )

    library_panel.LibraryPanel.on_random_tag_clicked(bind_library_harness(harness), Mock())

    assert lifecycle.is_current(pending_generation) is False
    assert harness._view_state.current_view == "tag_playlist"
    assert harness._view_state.active_playlist_tag == "focus"
    assert harness.stations is stations
    assert harness.selected_station is selected
    harness._render_results.assert_called_once_with()
    harness._update_playlist_status.assert_called_once_with()
    harness.play_selected_station.assert_called_once_with()


def test_gtk_view_state_transitions_own_view_and_playlist_identity() -> None:
    state = ViewState()

    assert state.current_view == "search"
    assert state.active_playlist_tag is None

    state.show_tag_playlist("focus")
    assert state.current_view == "tag_playlist"
    assert state.active_playlist_tag == "focus"

    state.show_history()
    assert state.current_view == "history"
    assert state.active_playlist_tag is None

    state.show_favorites()
    assert state.current_view == "favorites"
    assert state.active_playlist_tag is None

    state.show_search()
    assert state.current_view == "search"
    assert state.active_playlist_tag is None


def test_gtk_appearance_mode_mapping_is_stable() -> None:
    from fluxtuner.gui.appearance import AppearanceMode

    modes = (
        AppearanceMode.SYSTEM,
        AppearanceMode.DARK,
        AppearanceMode.LIGHT,
    )

    assert [mode.value for mode in modes] == ["system", "dark", "light"]


@pytest.mark.parametrize("profile_name", [None, "focus"])
def test_gtk_ripping_resolves_persistent_profile(
    tmp_path, monkeypatch, profile_name: str | None
) -> None:
    from fluxtuner.core import db
    from fluxtuner.core.profiles import get_or_create_profile

    monkeypatch.setattr(db, "DB_FILE", tmp_path / "profiles.db")
    db.init_db()
    with db.connect() as conn:
        default_id = db.ensure_default_profile(conn)
        focus_id = get_or_create_profile(conn, "Focus")
        conn.commit()

    harness = SimpleNamespace(profile_name=profile_name)
    monkeypatch.setattr(
        window,
        "resolve_effective_profile_name",
        Mock(side_effect=AssertionError("Do not re-read the active profile.")),
    )

    result = window.MainWindow._ripping_profile_context(harness)

    expected = (default_id, "default") if profile_name is None else (focus_id, "Focus")
    assert result == expected
    assert harness.profile_name == profile_name


def test_gtk_ripping_rejects_missing_persistent_profile(tmp_path, monkeypatch) -> None:
    from fluxtuner.core import db
    from fluxtuner.core.profiles import get_profile_by_name
    from fluxtuner.core.ripping import RippingError

    monkeypatch.setattr(db, "DB_FILE", tmp_path / "profiles.db")
    db.init_db()
    harness = SimpleNamespace(profile_name="Gone")

    with pytest.raises(RippingError, match="Ripping profile is unavailable"):
        window.MainWindow._ripping_profile_context(harness)

    with db.connect() as conn:
        assert get_profile_by_name(conn, "Gone") is None


def _ripping_shutdown_harness() -> SimpleNamespace:
    from fluxtuner.core.ripping_service import RippingService
    from fluxtuner.gui.gtk_shutdown import ShutdownController

    service = Mock(spec=RippingService)
    service.wait.return_value = True
    recording_manager = Mock()
    recording_manager.active_session = None
    harness = SimpleNamespace(
        ripping_service=service,
        recording_manager=recording_manager,
        _ripping_controller=Mock(),
        close_to_tray=False,
        close=Mock(),
        player=Mock(),
        usage_tracker=Mock(),
        _stop_usage_timer=Mock(),
        _stop_player_state_timer=Mock(),
        _stop_metadata_polling=Mock(),
        _show_quit_confirmation=Mock(),
        _show_shutdown_warning=Mock(),
        status_label=Mock(),
    )

    def stop_activity():
        harness._ripping_controller.stop_monitoring()
        harness._stop_usage_timer()
        harness._stop_player_state_timer()
        harness._stop_metadata_polling()
        harness.usage_tracker.stop()

    harness._shutdown_controller = ShutdownController(
        recording_manager=recording_manager,
        ripping_service=service,
        stop_activity=stop_activity,
        stop_playback=harness.player.stop,
        prepare_quit=lambda: setattr(harness, "close_to_tray", False),
        show_status=harness.status_label.set_text,
        show_confirmation=lambda **kwargs: harness._show_quit_confirmation(**kwargs),
        show_warning=lambda **kwargs: harness._show_shutdown_warning(**kwargs),
        schedule=Mock(return_value=23),
        remove_source=Mock(),
    )
    recording_stop = Mock()
    recording_stop.requested = False
    recording_stop.error = None
    recording_stop.poll.return_value = True
    harness._shutdown_controller._recording_stop = recording_stop
    return harness


def test_gtk_ripping_close_wait_defers_window_close(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = False
    harness._shutdown_controller.confirmation_pending = False
    harness.ripping_service.wait.side_effect = [False, False, False, True]
    dialogs = []

    harness.request_quit = lambda *, on_complete: window.MainWindow.request_quit(
        harness, on_complete=on_complete
    )
    harness._show_quit_confirmation = Mock(
        side_effect=lambda *, on_confirm, on_cancel: dialogs.append((on_confirm, on_cancel))
    )

    schedule = Mock(return_value=23)
    monkeypatch.setattr(harness._shutdown_controller, "_schedule", schedule, raising=False)

    assert window.MainWindow.on_close_request(harness, Mock()) is True
    assert len(dialogs) == 1

    harness.close.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    schedule.assert_not_called()

    dialogs[0][0]()

    harness.ripping_service.stop.assert_called_once_with()
    harness.close.assert_not_called()
    assert harness._shutdown_controller._timer_id == 23
    schedule.assert_called_once()
    interval, callback = schedule.call_args.args
    assert 0 < interval <= 1000
    assert callback == harness._shutdown_controller.poll

    assert harness._shutdown_controller.poll() is True
    harness.close.assert_not_called()

    assert harness._shutdown_controller.poll() is False
    harness.close.assert_called_once_with()
    assert harness._shutdown_controller._timer_id is None
    assert harness._shutdown_controller._on_complete is None


def test_gtk_ripping_close_wait_repeated_close_uses_one_timer(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = False
    harness._shutdown_controller.confirmation_pending = False
    harness.ripping_service.wait.side_effect = [False, False, True]
    dialogs = []

    harness.request_quit = lambda *, on_complete: window.MainWindow.request_quit(
        harness, on_complete=on_complete
    )
    harness._show_quit_confirmation = Mock(
        side_effect=lambda *, on_confirm, on_cancel: dialogs.append((on_confirm, on_cancel))
    )

    schedule = Mock(return_value=23)
    monkeypatch.setattr(harness._shutdown_controller, "_schedule", schedule, raising=False)

    assert window.MainWindow.on_close_request(harness, Mock()) is True
    assert window.MainWindow.on_close_request(harness, Mock()) is True

    assert len(dialogs) == 1
    harness.ripping_service.stop.assert_not_called()
    schedule.assert_not_called()

    dialogs[0][0]()

    assert harness._shutdown_controller._timer_id == 23
    assert harness._shutdown_controller.poll() is False

    schedule.assert_called_once()
    harness.close.assert_called_once_with()
    harness.player.stop.assert_called_once_with()
    harness.ripping_service.stop.assert_called_once_with()


def test_gtk_ripping_close_wait_tray_hide_keeps_operation_running(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = True
    harness.set_visible = Mock()
    schedule = Mock()
    monkeypatch.setattr(harness._shutdown_controller, "_schedule", schedule, raising=False)

    assert window.MainWindow.on_close_request(harness, Mock()) is True

    harness.set_visible.assert_called_once_with(False)
    harness.ripping_service.stop.assert_not_called()
    harness.ripping_service.wait.assert_not_called()
    harness.player.stop.assert_not_called()
    schedule.assert_not_called()
    assert harness._shutdown_controller.shutting_down is False


@pytest.mark.parametrize("ready_on_close", [False, True])
def test_gtk_ripping_close_priority_preserves_pending_quit(monkeypatch, ready_on_close) -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = False
    harness.ripping_service.wait.side_effect = [False, ready_on_close, True]
    schedule = Mock(return_value=23)
    remove = Mock()
    monkeypatch.setattr(harness._shutdown_controller, "_schedule", schedule, raising=False)
    monkeypatch.setattr(harness._shutdown_controller, "_remove_source", remove, raising=False)
    finish_quit = Mock()

    assert window.MainWindow.shutdown(harness, on_complete=finish_quit) is False

    assert window.MainWindow.on_close_request(harness, Mock()) is True

    if not ready_on_close:
        finish_quit.assert_not_called()
        assert harness._shutdown_controller._on_complete is finish_quit
        assert harness._shutdown_controller.poll() is False
        remove.assert_not_called()
    else:
        remove.assert_called_once_with(23)

    finish_quit.assert_called_once_with()
    harness.close.assert_not_called()
    harness.ripping_service.stop.assert_called_once_with()
    harness.player.stop.assert_called_once_with()
    schedule.assert_called_once()
    assert harness._shutdown_controller._timer_id is None
    assert harness._shutdown_controller._on_complete is None


@pytest.mark.parametrize("action", ["play_station", "start_station_recording"])
def test_gtk_closing_actions_reject_new_runtime_work(monkeypatch, tmp_path, action) -> None:
    harness = Mock()
    harness._shutdown_controller.shutting_down = True
    harness.recording_available = True
    harness.selected_station = {"name": "Other station"}
    selection = harness.selected_station
    station = {
        "name": "Clicked station",
        "url": "https://example.com/clicked",
    }
    harness._station_url.return_value = station["url"]
    harness._station_display_name.return_value = station["name"]
    playback = Mock(
        return_value=SimpleNamespace(
            success=False, station=None, status="Unexpected playback request"
        )
    )
    output_path = Mock(return_value=tmp_path / "unexpected.mp3")
    monkeypatch.setattr(window, "coordinate_playback_start", playback)
    monkeypatch.setattr(window, "recording_output_path", output_path)

    getattr(window.MainWindow, action)(harness, station)

    playback.assert_not_called()
    output_path.assert_not_called()
    harness.recording_manager.start.assert_not_called()
    harness.player.play.assert_not_called()
    harness.status_label.set_text.assert_not_called()
    harness._update_record_button.assert_not_called()
    assert harness.selected_station is selection


def test_saved_playlist_open_invalidates_search_and_resets_selection(monkeypatch) -> None:
    stations = [{"name": "Saved FM", "url": "https://example.com/saved"}]
    lifecycle = SearchLifecycle()
    pending = lifecycle.begin()
    harness = SimpleNamespace(
        _playlist_profile_id=Mock(return_value=7),
        _search_lifecycle=lifecycle,
        _view_state=ViewState(active_playlist_tag="jazz"),
        selected_station={"name": "Other", "url": "https://example.com/other"},
        stations=[],
        _refresh_favorite_cache=Mock(),
        _render_results=Mock(),
        _update_playlist_status=Mock(),
        _refresh_saved_playlists=Mock(),
        _set_view_status=Mock(),
        status_label=Mock(),
    )
    lookup = Mock(return_value={"name": "Morning"})
    contents = Mock(return_value=stations)
    monkeypatch.setattr(library_controller.manual_playlists, "get_playlist", lookup)
    monkeypatch.setattr(library_controller.manual_playlists, "get_playlist_stations", contents)

    library_panel.LibraryPanel._show_saved_playlist(bind_library_harness(harness), "Morning")

    lookup.assert_called_once_with("Morning", profile_id=7)
    contents.assert_called_once_with("Morning", profile_id=7)
    assert not lifecycle.is_current(pending)
    assert harness._view_state.current_view == "playlist"
    assert harness._view_state.active_playlist_name == "Morning"
    assert harness._view_state.active_playlist_tag is None
    assert harness.stations is stations
    assert harness.selected_station is None
    harness._render_results.assert_called_once_with()


def test_missing_saved_playlist_keeps_current_view_and_selection(monkeypatch) -> None:
    selection = {"name": "Selected"}
    state = ViewState()
    harness = SimpleNamespace(
        _playlist_profile_id=Mock(return_value=7),
        _search_lifecycle=SearchLifecycle(),
        _view_state=state,
        selected_station=selection,
        stations=[selection],
        _render_results=Mock(),
        status_label=Mock(),
    )
    monkeypatch.setattr(
        library_controller.manual_playlists, "get_playlist", Mock(return_value=None)
    )

    library_panel.LibraryPanel._show_saved_playlist(bind_library_harness(harness), "Deleted")

    assert state.current_view == "search"
    assert harness.selected_station is selection
    assert harness.stations == [selection]
    harness._render_results.assert_not_called()
    harness.status_label.set_text.assert_called_once_with(
        "Could not open playlist: This playlist no longer exists."
    )


def _playlist_management_dialog(monkeypatch):
    entry = Mock()
    entry.get_text.return_value = " Morning "
    dialog, content, error = Mock(), Mock(), Mock()
    monkeypatch.setattr(
        library_panel,
        "Gtk",
        SimpleNamespace(
            Entry=Mock(return_value=entry),
            ResponseType=SimpleNamespace(ACCEPT=1, CANCEL=0),
        ),
    )
    state = ViewState()
    state.show_playlist("Morning")
    harness = SimpleNamespace(
        _playlist_profile_id=Mock(return_value=7),
        _make_playlist_dialog=Mock(return_value=(dialog, content)),
        _make_value_label=Mock(return_value=error),
        _view_state=state,
        _show_saved_playlist=Mock(),
        _show_all_favorites=Mock(),
        _refresh_saved_playlists=Mock(),
        status_label=Mock(),
    )
    return harness, dialog, entry, error


@pytest.mark.parametrize("operation", ["create", "delete"])
def test_playlist_management_cancel_does_not_write(monkeypatch, operation) -> None:
    harness, dialog, _entry, _error = _playlist_management_dialog(monkeypatch)
    storage = Mock()
    monkeypatch.setattr(library_controller.manual_playlists, f"{operation}_playlist", storage)
    handler = getattr(library_panel.LibraryPanel, f"on_{operation}_playlist_clicked")
    handler(bind_library_harness(harness), Mock())
    respond = dialog.connect.call_args.args[1]

    respond(dialog, 0)

    storage.assert_not_called()
    dialog.destroy.assert_called_once_with()
    harness._show_all_favorites.assert_not_called()
    harness._show_saved_playlist.assert_not_called()


@pytest.mark.parametrize("operation", ["create", "delete"])
def test_playlist_management_rejects_profile_change(monkeypatch, operation) -> None:
    harness, dialog, _entry, error = _playlist_management_dialog(monkeypatch)
    storage = Mock()
    monkeypatch.setattr(library_controller.manual_playlists, f"{operation}_playlist", storage)
    handler = getattr(library_panel.LibraryPanel, f"on_{operation}_playlist_clicked")
    handler(bind_library_harness(harness), Mock())
    respond = dialog.connect.call_args.args[1]
    harness._playlist_profile_id.return_value = 8

    respond(dialog, 1)

    storage.assert_not_called()
    dialog.destroy.assert_not_called()
    error.set_text.assert_called_once_with("The profile changed. Reopen this dialog.")


def test_create_playlist_trims_name_and_opens_new_list(monkeypatch) -> None:
    harness, dialog, _entry, _error = _playlist_management_dialog(monkeypatch)
    storage = Mock(return_value=True)
    monkeypatch.setattr(library_controller.manual_playlists, "create_playlist", storage)
    library_panel.LibraryPanel.on_create_playlist_clicked(bind_library_harness(harness), Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    storage.assert_called_once_with("Morning", profile_id=7)
    dialog.destroy.assert_called_once_with()
    harness._show_saved_playlist.assert_called_once_with("Morning")


@pytest.mark.parametrize("name", ["", "   "])
def test_create_playlist_rejects_blank_name(monkeypatch, name) -> None:
    harness, dialog, entry, error = _playlist_management_dialog(monkeypatch)
    entry.get_text.return_value = name
    storage = Mock()
    monkeypatch.setattr(library_controller.manual_playlists, "create_playlist", storage)
    library_panel.LibraryPanel.on_create_playlist_clicked(bind_library_harness(harness), Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    storage.assert_not_called()
    dialog.destroy.assert_not_called()
    error.set_text.assert_called_once_with("Enter a playlist name.")


def test_duplicate_playlist_keeps_dialog_open(monkeypatch) -> None:
    harness, dialog, _entry, error = _playlist_management_dialog(monkeypatch)
    monkeypatch.setattr(
        library_controller.manual_playlists, "create_playlist", Mock(return_value=False)
    )
    library_panel.LibraryPanel.on_create_playlist_clicked(bind_library_harness(harness), Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    dialog.destroy.assert_not_called()
    harness._show_saved_playlist.assert_not_called()
    error.set_text.assert_called_once_with("A playlist with this name already exists.")


def test_delete_playlist_uses_captured_name_and_profile(monkeypatch) -> None:
    harness, dialog, _entry, _error = _playlist_management_dialog(monkeypatch)
    storage = Mock(return_value=True)
    monkeypatch.setattr(library_controller.manual_playlists, "delete_playlist", storage)
    library_panel.LibraryPanel.on_delete_playlist_clicked(bind_library_harness(harness), Mock())
    respond = dialog.connect.call_args.args[1]

    respond(dialog, 1)

    storage.assert_called_once_with("Morning", profile_id=7)
    dialog.destroy.assert_called_once_with()
    harness._show_all_favorites.assert_called_once_with()
    harness._refresh_saved_playlists.assert_called_once_with()


def test_delete_playlist_storage_error_preserves_view(monkeypatch) -> None:
    harness, dialog, _entry, error = _playlist_management_dialog(monkeypatch)
    monkeypatch.setattr(
        library_controller.manual_playlists,
        "delete_playlist",
        Mock(side_effect=OSError("Storage unavailable")),
    )
    library_panel.LibraryPanel.on_delete_playlist_clicked(bind_library_harness(harness), Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    dialog.destroy.assert_not_called()
    harness._show_all_favorites.assert_not_called()
    assert harness._view_state.active_playlist_name == "Morning"
    error.set_text.assert_called_once_with("Storage unavailable")


def test_application_menu_keeps_appearance_and_routes_quit_to_app_action(monkeypatch) -> None:
    menu_button, popover, box = Mock(), Mock(), Mock()
    buttons = {}

    def make_button(*, label):
        result = Mock()
        buttons[label] = result
        return result

    monkeypatch.setattr(
        window,
        "Gtk",
        SimpleNamespace(
            MenuButton=Mock(return_value=menu_button),
            Popover=Mock(return_value=popover),
            Box=Mock(return_value=box),
            Button=make_button,
            Orientation=SimpleNamespace(VERTICAL=object()),
            Align=SimpleNamespace(END=object(), CENTER=object()),
        ),
    )
    container = Mock()
    harness = SimpleNamespace(
        _build_appearance_controls=Mock(),
        on_about_clicked=Mock(),
        on_add_custom_station_clicked=Mock(),
        on_import_stations_clicked=Mock(),
    )

    harness.on_import_stations_url_clicked = Mock()
    window.MainWindow._build_application_menu(bind_library_menu(harness), container)

    window.Gtk.MenuButton.assert_called_once_with(icon_name="open-menu-symbolic")
    container.append.assert_called_once_with(menu_button)
    menu_button.set_popover.assert_called_once_with(popover)
    popover.set_child.assert_called_once_with(box)
    harness._build_appearance_controls.assert_called_once_with(box)
    buttons["Quit"].set_action_name.assert_called_once_with("app.quit")
    buttons["Add station…"].connect.assert_called_once_with(
        "clicked", harness.on_add_custom_station_clicked
    )
    buttons["About FluxTuner"].connect.assert_called_once_with("clicked", harness.on_about_clicked)
    buttons["Import stations…"].connect.assert_called_once_with(
        "clicked", harness.on_import_stations_clicked
    )


def test_about_dialog_reports_installed_version_and_project(monkeypatch) -> None:
    logo = Mock()
    texture_loader = Mock(return_value=logo)
    monkeypatch.setattr(
        sys.modules["gi.repository"],
        "Gdk",
        SimpleNamespace(Texture=SimpleNamespace(new_from_filename=texture_loader)),
        raising=False,
    )
    from fluxtuner import __version__

    dialog = Mock()
    constructor = Mock(return_value=dialog)
    monkeypatch.setattr(window, "Gtk", SimpleNamespace(AboutDialog=constructor))
    harness = SimpleNamespace()

    window.MainWindow.on_about_clicked(harness, Mock())

    constructor.assert_called_once_with(transient_for=harness, modal=True)
    dialog.set_program_name.assert_called_once_with("FluxTuner")
    dialog.set_version.assert_called_once_with(__version__)
    dialog.set_website.assert_called_once_with("https://github.com/pitill0/fluxtuner")
    dialog.present.assert_called_once_with()

    texture_loader.assert_called_once()
    from pathlib import Path

    logo_path = Path(texture_loader.call_args.args[0])
    assert logo_path.name == "io.github.pitill0.Fluxtuner.png"
    assert logo_path.is_file()
    assert logo_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    dialog.set_logo.assert_called_once_with(logo)


def _custom_station_dialog(monkeypatch):
    from contextlib import nullcontext

    name_entry, url_entry = Mock(), Mock()
    name_entry.get_text.return_value = "Personal radio"
    url_entry.get_text.return_value = "https://radio.example/live"
    dialog, content, error, conn = Mock(), Mock(), Mock(), Mock()
    monkeypatch.setattr(
        library_panel,
        "Gtk",
        SimpleNamespace(
            Entry=Mock(side_effect=[name_entry, url_entry]),
            ResponseType=SimpleNamespace(ACCEPT=1, CANCEL=0),
        ),
    )
    connect = Mock(side_effect=lambda: nullcontext(conn))
    monkeypatch.setattr(library_controller.db, "connect", connect)
    save = Mock(return_value=True)
    monkeypatch.setattr(library_controller, "add_custom_station", save, raising=False)
    harness = SimpleNamespace(
        _playlist_profile_id=Mock(return_value=7),
        _make_playlist_dialog=Mock(return_value=(dialog, content)),
        _make_value_label=Mock(return_value=error),
        application_menu_popover=Mock(),
        _show_all_favorites=Mock(),
        _refresh_saved_playlists=Mock(),
        status_label=Mock(),
    )
    return harness, dialog, error, conn, connect, save


def test_custom_station_dialog_opens_without_writing(monkeypatch):
    harness, dialog, _error, conn, connect, save = _custom_station_dialog(monkeypatch)

    library_panel.LibraryPanel.on_add_custom_station_clicked(bind_library_harness(harness), Mock())

    harness.application_menu_popover.popdown.assert_called_once_with()
    harness._make_playlist_dialog.assert_called_once_with("Add station", "Add")
    dialog.present.assert_called_once_with()
    connect.assert_not_called()
    save.assert_not_called()
    conn.commit.assert_not_called()


def test_custom_station_dialog_cancel_does_not_write(monkeypatch):
    harness, dialog, _error, _conn, connect, save = _custom_station_dialog(monkeypatch)
    library_panel.LibraryPanel.on_add_custom_station_clicked(bind_library_harness(harness), Mock())

    dialog.connect.call_args.args[1](dialog, 0)

    connect.assert_not_called()
    save.assert_not_called()
    dialog.destroy.assert_called_once_with()
    harness._show_all_favorites.assert_not_called()


def test_custom_station_dialog_rejects_profile_change(monkeypatch):
    harness, dialog, error, _conn, connect, save = _custom_station_dialog(monkeypatch)
    library_panel.LibraryPanel.on_add_custom_station_clicked(bind_library_harness(harness), Mock())
    harness._playlist_profile_id.return_value = 8

    dialog.connect.call_args.args[1](dialog, 1)

    connect.assert_not_called()
    save.assert_not_called()
    dialog.destroy.assert_not_called()
    error.set_text.assert_called_once_with("The profile changed. Reopen this dialog.")


def test_custom_station_dialog_rejects_missing_profile_on_open(monkeypatch):
    harness, dialog, _error, _conn, connect, save = _custom_station_dialog(monkeypatch)
    harness._playlist_profile_id.side_effect = ValueError("Profile unavailable")

    library_panel.LibraryPanel.on_add_custom_station_clicked(bind_library_harness(harness), Mock())

    harness._make_playlist_dialog.assert_not_called()
    dialog.present.assert_not_called()
    connect.assert_not_called()
    save.assert_not_called()
    harness.status_label.set_text.assert_called_once_with(
        "Could not add station: Profile unavailable"
    )


@pytest.mark.parametrize(
    "failure",
    [
        ValueError("Enter a valid stream URL."),
        OSError("Storage unavailable"),
    ],
)
def test_custom_station_dialog_keeps_inputs_on_error(monkeypatch, failure):
    harness, dialog, error, conn, _connect, save = _custom_station_dialog(monkeypatch)
    save.side_effect = failure
    library_panel.LibraryPanel.on_add_custom_station_clicked(bind_library_harness(harness), Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    dialog.destroy.assert_not_called()
    conn.commit.assert_not_called()
    harness._show_all_favorites.assert_not_called()
    error.set_text.assert_called_once_with(str(failure))


@pytest.mark.parametrize("added", [True, False])
def test_custom_station_dialog_saves_captured_profile_and_refreshes(monkeypatch, added):
    harness, dialog, _error, conn, _connect, save = _custom_station_dialog(monkeypatch)
    save.return_value = added
    library_panel.LibraryPanel.on_add_custom_station_clicked(bind_library_harness(harness), Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    save.assert_called_once_with(
        conn,
        profile_id=7,
        name="Personal radio",
        url="https://radio.example/live",
        record_manual_provenance=True,
    )
    conn.commit.assert_called_once_with()
    dialog.destroy.assert_called_once_with()
    harness._show_all_favorites.assert_called_once_with()
    harness._refresh_saved_playlists.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with(
        "Station added to favorites." if added else "Station is already in favorites."
    )


def test_gtk_window_x_routes_pending_recording_to_confirmation() -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = False
    harness.recording_manager.active_session = object()
    harness.request_quit = Mock()

    assert window.MainWindow.on_close_request(harness, Mock()) is True

    harness.request_quit.assert_called_once()
    callback = harness.request_quit.call_args.kwargs["on_complete"]
    assert callable(callback)
    harness.recording_manager.stop.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    harness.player.stop.assert_not_called()
    harness.close.assert_not_called()


def test_gtk_window_x_cancel_keeps_recording_then_confirm_stops() -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = False
    harness.recording_manager.active_session = object()
    harness._shutdown_controller.confirmation_pending = False
    callbacks = []

    harness.request_quit = lambda *, on_complete: window.MainWindow.request_quit(
        harness, on_complete=on_complete
    )

    def capture_dialog(*, on_confirm, on_cancel):
        callbacks.append((on_confirm, on_cancel))

    harness._show_quit_confirmation = Mock(side_effect=capture_dialog)

    assert window.MainWindow.on_close_request(harness, Mock()) is True
    assert len(callbacks) == 1
    harness.recording_manager.stop.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    harness.close.assert_not_called()

    callbacks[0][1]()

    assert harness._shutdown_controller.confirmation_pending is False
    harness.recording_manager.stop.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    harness.close.assert_not_called()

    assert window.MainWindow.on_close_request(harness, Mock()) is True
    assert len(callbacks) == 2
    callbacks[1][0]()

    harness._shutdown_controller._recording_stop.request.assert_called_once_with()
    harness.recording_manager.stop.assert_not_called()
    harness.ripping_service.stop.assert_called_once_with()
    harness.close.assert_called_once_with()


def _quit_dialog_harness(monkeypatch):
    """Capture Gtk.Dialog construction and its response callback."""
    responses = SimpleNamespace(
        CANCEL=-6,
        ACCEPT=-3,
        DELETE_EVENT=-4,
    )
    dialog = Mock()
    dialog.get_content_area.return_value = Mock()
    captured = {}

    def connect(signal, callback):
        assert signal == "response"
        captured["respond"] = callback

    dialog.connect.side_effect = connect

    constructor = Mock(return_value=dialog)
    monkeypatch.setattr(window.Gtk, "Dialog", constructor, raising=False)
    monkeypatch.setattr(window.Gtk, "Label", Mock(return_value=Mock()), raising=False)
    monkeypatch.setattr(window.Gtk, "ResponseType", responses, raising=False)

    owner = Mock()
    on_confirm = Mock()
    on_cancel = Mock()

    window.MainWindow._show_quit_confirmation(
        owner,
        on_confirm=on_confirm,
        on_cancel=on_cancel,
    )

    constructor.assert_called_once_with(
        title="Recording in progress",
        transient_for=owner,
        modal=True,
    )
    dialog.add_button.assert_any_call("Cancel", responses.CANCEL)
    dialog.add_button.assert_any_call("Stop recording & Quit", responses.ACCEPT)
    dialog.present.assert_called_once_with()
    assert "respond" in captured
    return dialog, responses, captured["respond"], on_confirm, on_cancel


def test_gtk_quit_dialog_cancel(monkeypatch) -> None:
    dialog, responses, respond, on_confirm, on_cancel = _quit_dialog_harness(monkeypatch)

    respond(dialog, responses.CANCEL)

    dialog.destroy.assert_called_once_with()
    on_cancel.assert_called_once_with()
    on_confirm.assert_not_called()


@pytest.mark.parametrize("response", [-4, -5, -1])
def test_gtk_quit_dialog_close_or_escape_cancels(monkeypatch, response) -> None:
    dialog, _, respond, on_confirm, on_cancel = _quit_dialog_harness(monkeypatch)

    respond(dialog, response)

    dialog.destroy.assert_called_once_with()
    on_cancel.assert_called_once_with()
    on_confirm.assert_not_called()


def test_gtk_quit_dialog_accept(monkeypatch) -> None:
    dialog, responses, respond, on_confirm, on_cancel = _quit_dialog_harness(monkeypatch)

    respond(dialog, responses.ACCEPT)

    dialog.destroy.assert_called_once_with()
    on_confirm.assert_called_once_with()
    on_cancel.assert_not_called()


def test_gtk_quit_dialog_duplicate_response_is_idempotent(monkeypatch) -> None:
    dialog, responses, respond, on_confirm, on_cancel = _quit_dialog_harness(monkeypatch)

    respond(dialog, responses.ACCEPT)
    respond(dialog, responses.CANCEL)

    dialog.destroy.assert_called_once_with()
    on_confirm.assert_called_once_with()
    on_cancel.assert_not_called()


@pytest.mark.parametrize("action", ["start", "stop"])
def test_gtk_ripping_actions_delegate_explicit_target_to_controller(action):
    selected = {"name": "Selected"}
    station = {"name": "Clicked", "url": "https://example.com/clicked"}
    controller = Mock()
    controller.start.return_value = 42
    harness = SimpleNamespace(_ripping_controller=controller, selected_station=selected)

    if action == "start":
        assert window.MainWindow.start_station_ripping(harness, station) == 42
    else:
        window.MainWindow.stop_station_ripping(harness, station)

    getattr(controller, action).assert_called_once_with(station)
    assert harness.selected_station is selected


def test_window_shutdown_activity_adapter_preserves_timer_stop_order():
    events = Mock()
    harness = SimpleNamespace(
        _ripping_controller=SimpleNamespace(stop_monitoring=events.ripping),
        _stop_usage_timer=events.usage_timer,
        _stop_player_state_timer=events.player_timer,
        _stop_metadata_polling=events.metadata,
        usage_tracker=SimpleNamespace(stop=events.usage),
    )

    window.MainWindow._stop_background_activity(harness)

    assert events.mock_calls == [
        call.ripping(),
        call.usage_timer(),
        call.player_timer(),
        call.metadata(),
        call.usage(),
    ]


def test_window_prepare_quit_disables_tray_hiding():
    harness = SimpleNamespace(close_to_tray=True)
    window.MainWindow._prepare_quit(harness)
    assert harness.close_to_tray is False


def test_window_quit_and_shutdown_delegate_to_the_single_owner():
    controller = Mock()
    controller.shutdown.return_value = False
    harness = SimpleNamespace(_shutdown_controller=controller)
    completed = Mock()

    window.MainWindow.request_quit(harness, on_complete=completed)
    assert window.MainWindow.shutdown(harness, on_complete=completed) is False

    controller.request_quit.assert_called_once_with(on_complete=completed)
    controller.shutdown.assert_called_once_with(on_complete=completed)
