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
    harness._quit_confirmation_pending = False
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
    harness._quit_confirmation_pending = False
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
    monkeypatch.setattr(window, "load_favorites", Mock(return_value=favorites))

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

    count = window.MainWindow._show_all_favorites(harness)

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
    monkeypatch.setattr(window, "load_history", Mock(return_value=history))

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

    count = window.MainWindow._show_history(harness)

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

    window.MainWindow.on_show_tag_playlist_clicked(harness, Mock())

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
        window,
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

    window.MainWindow.on_random_tag_clicked(harness, Mock())

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


def _ripping_probe_harness() -> SimpleNamespace:
    from fluxtuner.core.ripping import RippingAvailability

    return SimpleNamespace(
        ripping_backend=Mock(),
        ripping_availability=RippingAvailability(False, "Checking availability."),
        _ripping_probe_worker=None,
        _ripping_shutting_down=False,
        _ripping_availability_finished=Mock(),
        selected_station={"name": "Selected station"},
        status_label=Mock(),
    )


def test_gtk_ripping_window_schedules_availability_probe(monkeypatch) -> None:
    harness = _ripping_probe_harness()
    worker = object()
    probe = Mock(return_value=worker)
    dispatcher = Mock()
    monkeypatch.setattr(window, "start_ripping_availability_probe", probe, raising=False)
    monkeypatch.setattr(window.GLib, "idle_add", dispatcher, raising=False)

    window.MainWindow._start_ripping_availability_probe(harness)

    probe.assert_called_once_with(
        check_availability=harness.ripping_backend.availability,
        dispatch=dispatcher,
        on_result=harness._ripping_availability_finished,
    )
    harness.ripping_backend.availability.assert_not_called()
    assert harness._ripping_probe_worker is worker
    harness.status_label.set_text.assert_not_called()


@pytest.mark.parametrize("available", [True, False])
@pytest.mark.parametrize("closing", [True, False])
def test_gtk_ripping_window_accepts_availability_only_while_open(
    available: bool, closing: bool
) -> None:
    from fluxtuner.core.ripping import RippingAvailability

    harness = _ripping_probe_harness()
    harness._ripping_shutting_down = closing
    previous = harness.ripping_availability
    selection = harness.selected_station
    result = RippingAvailability(available, "" if available else "Missing Brynse.")

    window.MainWindow._ripping_availability_finished(harness, result)

    assert harness.ripping_availability is (previous if closing else result)
    assert harness.selected_station is selection
    harness.status_label.set_text.assert_not_called()


def test_gtk_ripping_window_contains_probe_scheduling_failure(monkeypatch) -> None:
    harness = _ripping_probe_harness()
    probe = Mock(side_effect=RuntimeError("worker unavailable"))
    monkeypatch.setattr(window, "start_ripping_availability_probe", probe, raising=False)
    monkeypatch.setattr(window.GLib, "idle_add", Mock(), raising=False)

    window.MainWindow._start_ripping_availability_probe(harness)

    assert harness._ripping_probe_worker is None
    assert harness.ripping_availability.available is False
    assert harness.ripping_availability.reason == (
        "Could not schedule ripping availability check: worker unavailable"
    )
    harness.status_label.set_text.assert_not_called()


def test_gtk_ripping_shutdown_rejects_future_probe_results() -> None:
    harness = _ripping_shutdown_harness()

    window.MainWindow.shutdown(harness)

    assert harness._ripping_shutting_down is True


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


def _ripping_start_harness() -> SimpleNamespace:
    from fluxtuner.core.ripping import RippingAvailability
    from fluxtuner.core.ripping_service import RippingService

    service = Mock(spec=RippingService)
    service.start.return_value = 42
    return SimpleNamespace(
        ripping_service=service,
        ripping_availability=RippingAvailability(True),
        _ripping_shutting_down=False,
        _ripping_profile_context=Mock(return_value=(7, "Focus")),
        _ensure_ripping_state_timer=Mock(),
        selected_station={"name": "Other station", "url": "https://example.com/other"},
        status_label=Mock(),
    )


def test_gtk_ripping_window_starts_clicked_station(tmp_path, monkeypatch) -> None:
    from uuid import UUID

    harness = _ripping_start_harness()
    selection = harness.selected_station
    clicked = {
        "name": "Clicked station",
        "url": "https://example.com/original",
        "url_resolved": "https://example.com/clicked",
    }
    run_id = UUID("12345678-1234-5678-1234-567812345678")
    new_uuid = Mock(return_value=run_id)
    monkeypatch.setattr(window, "DATA_DIR", tmp_path, raising=False)
    monkeypatch.setattr(window, "uuid4", new_uuid, raising=False)

    job_id = window.MainWindow.start_station_ripping(harness, clicked)

    assert job_id == 42
    harness._ripping_profile_context.assert_called_once_with()
    new_uuid.assert_called_once_with()
    harness.ripping_service.start.assert_called_once()
    request = harness.ripping_service.start.call_args.args[0]
    assert request.source_url == "https://example.com/clicked"
    assert request.profile_id == 7
    assert request.profile_name == "Focus"
    assert request.output_directory == tmp_path / "rips" / "profile-7" / run_id.hex
    assert harness.selected_station is selection
    harness.status_label.set_text.assert_called_once_with("Starting ripping: Clicked station")
    harness._ensure_ripping_state_timer.assert_called_once_with()


@pytest.mark.parametrize("closing", [False, True])
def test_gtk_ripping_window_start_rejects_before_profile_lookup(monkeypatch, closing: bool) -> None:
    from fluxtuner.core.ripping import RippingAvailability

    harness = _ripping_start_harness()
    harness._ripping_shutting_down = closing
    harness.ripping_availability = RippingAvailability(False, "Missing Brynse.")
    new_uuid = Mock()
    monkeypatch.setattr(window, "uuid4", new_uuid, raising=False)

    job_id = window.MainWindow.start_station_ripping(
        harness, {"name": "Clicked station", "url": "https://example.com/clicked"}
    )

    assert job_id is None
    harness._ripping_profile_context.assert_not_called()
    harness.ripping_service.start.assert_not_called()
    harness._ensure_ripping_state_timer.assert_not_called()
    new_uuid.assert_not_called()
    if closing:
        harness.status_label.set_text.assert_not_called()
    else:
        harness.status_label.set_text.assert_called_once_with(
            "Ripping unavailable: Missing Brynse."
        )


def test_gtk_ripping_window_start_contains_profile_failure(monkeypatch) -> None:
    from fluxtuner.core.ripping import RippingError

    harness = _ripping_start_harness()
    harness._ripping_profile_context.side_effect = RippingError("Ripping profile is unavailable.")
    new_uuid = Mock()
    monkeypatch.setattr(window, "uuid4", new_uuid, raising=False)

    job_id = window.MainWindow.start_station_ripping(
        harness, {"name": "Clicked station", "url": "https://example.com/clicked"}
    )

    assert job_id is None
    harness.ripping_service.start.assert_not_called()
    harness._ensure_ripping_state_timer.assert_not_called()
    new_uuid.assert_not_called()
    harness.status_label.set_text.assert_called_once_with(
        "Could not start ripping: Ripping profile is unavailable."
    )


def _ripping_state_harness(tmp_path, *, state="running") -> SimpleNamespace:
    from fluxtuner.core.ripping import RippingRequest
    from fluxtuner.core.ripping_service import RippingService, RippingSnapshot

    request = RippingRequest(
        station_name="Clicked station",
        source_url="https://example.com/clicked",
        output_directory=tmp_path / "tracks",
    )
    service = Mock(spec=RippingService)
    service.wait.return_value = False
    service.snapshot.return_value = RippingSnapshot(job_id=1, request=request, state=state)
    return SimpleNamespace(
        ripping_service=service,
        _ripping_shutting_down=False,
        _ripping_state_timer_id=17,
        _ripping_last_status=None,
        selected_station={"name": "Other station"},
        status_label=Mock(),
    )


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("starting", "Starting ripping: Clicked station"),
        ("running", "Ripping tracks: Clicked station"),
        ("stopping", "Stopping ripping: Clicked station"),
    ],
)
def test_gtk_ripping_state_refresh_projects_active_states(tmp_path, state, expected) -> None:
    harness = _ripping_state_harness(tmp_path, state=state)
    selection = harness.selected_station

    keep_polling = window.MainWindow._refresh_ripping_state(harness)

    assert keep_polling is True
    assert harness._ripping_state_timer_id == 17
    harness.ripping_service.wait.assert_called_once_with(timeout=0)
    harness.status_label.set_text.assert_called_once_with(expected)
    assert harness.selected_station is selection


def test_gtk_ripping_state_refresh_waits_for_workers_after_terminal_state(tmp_path) -> None:
    harness = _ripping_state_harness(tmp_path, state="completed")
    harness.ripping_service.wait.side_effect = [False, True]

    assert window.MainWindow._refresh_ripping_state(harness) is True
    assert harness._ripping_state_timer_id == 17
    assert window.MainWindow._refresh_ripping_state(harness) is False
    assert harness._ripping_state_timer_id is None
    harness.status_label.set_text.assert_called_once_with(
        "Ripping completed: Clicked station (0 tracks saved)"
    )
    assert harness.ripping_service.wait.call_args_list == [call(timeout=0), call(timeout=0)]


def test_gtk_ripping_state_refresh_deduplicates_within_each_job(tmp_path) -> None:
    from dataclasses import replace

    harness = _ripping_state_harness(tmp_path)

    assert window.MainWindow._refresh_ripping_state(harness) is True
    harness.status_label.set_text.reset_mock()
    assert window.MainWindow._refresh_ripping_state(harness) is True
    harness.status_label.set_text.assert_not_called()

    previous = harness.ripping_service.snapshot.return_value
    harness.ripping_service.snapshot.return_value = replace(previous, job_id=2)

    assert window.MainWindow._refresh_ripping_state(harness) is True
    harness.status_label.set_text.assert_called_once_with("Ripping tracks: Clicked station")


def test_gtk_ripping_state_refresh_reports_late_outputs_after_failure(tmp_path) -> None:
    from dataclasses import replace

    from fluxtuner.core.ripping import RippedTrack, RippingResult

    harness = _ripping_state_harness(tmp_path, state="failed")
    snapshot = harness.ripping_service.snapshot.return_value
    snapshot = replace(snapshot, error=RuntimeError("stop failed"))
    harness.ripping_service.snapshot.return_value = snapshot

    assert window.MainWindow._refresh_ripping_state(harness) is True
    harness.status_label.set_text.assert_called_once_with(
        "Ripping failed: Clicked station: stop failed"
    )
    harness.status_label.set_text.reset_mock()

    result = RippingResult(
        request=snapshot.request,
        codec="mp3",
        metaint=16000,
        stopped=True,
        tracks=(RippedTrack("Saved", snapshot.request.output_directory / "saved.mp3"),),
    )
    harness.ripping_service.snapshot.return_value = replace(snapshot, result=result)

    assert window.MainWindow._refresh_ripping_state(harness) is True
    harness.status_label.set_text.assert_called_once_with(
        "Ripping failed: Clicked station: stop failed (1 track saved)"
        f" → {snapshot.request.output_directory}"
    )


def test_gtk_ripping_state_refresh_reads_snapshot_after_readiness_check(tmp_path) -> None:
    from dataclasses import replace

    harness = _ripping_state_harness(tmp_path, state="starting")
    initial = harness.ripping_service.snapshot.return_value

    def finish_during_check(*, timeout):
        assert timeout == 0
        harness.ripping_service.snapshot.return_value = replace(initial, state="stopped")
        return True

    harness.ripping_service.wait.side_effect = finish_during_check

    assert window.MainWindow._refresh_ripping_state(harness) is False
    assert harness._ripping_state_timer_id is None
    harness.status_label.set_text.assert_called_once_with(
        "Ripping stopped: Clicked station (0 tracks saved)"
    )


def test_gtk_ripping_state_refresh_discards_updates_during_shutdown(tmp_path) -> None:
    harness = _ripping_state_harness(tmp_path)
    harness._ripping_shutting_down = True

    assert window.MainWindow._refresh_ripping_state(harness) is False
    assert harness._ripping_state_timer_id is None
    harness.ripping_service.wait.assert_not_called()
    harness.ripping_service.snapshot.assert_not_called()
    harness.status_label.set_text.assert_not_called()


def test_gtk_ripping_state_refresh_without_job_finishes_silently(tmp_path) -> None:
    harness = _ripping_state_harness(tmp_path)
    harness.ripping_service.wait.return_value = True
    harness.ripping_service.snapshot.return_value = None

    assert window.MainWindow._refresh_ripping_state(harness) is False
    assert harness._ripping_state_timer_id is None
    harness.status_label.set_text.assert_not_called()


def test_gtk_ripping_state_timer_schedules_once(monkeypatch) -> None:
    harness = SimpleNamespace(
        _ripping_shutting_down=False,
        _ripping_state_timer_id=None,
        _refresh_ripping_state=Mock(),
    )
    schedule = Mock(return_value=23)
    monkeypatch.setattr(window.GLib, "timeout_add", schedule, raising=False)

    window.MainWindow._ensure_ripping_state_timer(harness)
    window.MainWindow._ensure_ripping_state_timer(harness)

    assert harness._ripping_state_timer_id == 23
    schedule.assert_called_once()
    interval, callback = schedule.call_args.args
    assert 0 < interval <= 1000
    assert callback is harness._refresh_ripping_state
    harness._refresh_ripping_state.assert_not_called()


@pytest.mark.parametrize(
    ("closing", "timer_id"),
    [(True, None), (False, 17)],
)
def test_gtk_ripping_state_timer_rejects_shutdown_or_duplicate(
    monkeypatch, closing, timer_id
) -> None:
    harness = SimpleNamespace(
        _ripping_shutting_down=closing,
        _ripping_state_timer_id=timer_id,
        _refresh_ripping_state=Mock(),
    )
    schedule = Mock()
    monkeypatch.setattr(window.GLib, "timeout_add", schedule, raising=False)

    window.MainWindow._ensure_ripping_state_timer(harness)

    assert harness._ripping_state_timer_id == timer_id
    schedule.assert_not_called()
    harness._refresh_ripping_state.assert_not_called()


def test_gtk_ripping_window_start_failure_does_not_schedule_timer(tmp_path, monkeypatch) -> None:
    harness = _ripping_start_harness()
    harness.ripping_service.start.side_effect = RuntimeError("Another job is active.")
    selection = harness.selected_station
    monkeypatch.setattr(window, "DATA_DIR", tmp_path)

    job_id = window.MainWindow.start_station_ripping(
        harness,
        {"name": "Clicked station", "url": "https://example.com/clicked"},
    )

    assert job_id is None
    harness._ensure_ripping_state_timer.assert_not_called()
    assert harness.selected_station is selection
    harness.status_label.set_text.assert_called_once_with(
        "Could not start ripping: Another job is active."
    )


def _ripping_stop_harness(tmp_path) -> SimpleNamespace:
    from fluxtuner.core.ripping import RippingRequest
    from fluxtuner.core.ripping_service import RippingSnapshot

    harness = _ripping_start_harness()
    harness.ripping_service.snapshot.return_value = RippingSnapshot(
        job_id=42,
        request=RippingRequest(
            station_name="Running station",
            source_url="https://example.com/clicked",
            output_directory=tmp_path / "tracks",
            profile_id=7,
            profile_name="Focus",
        ),
        state="running",
    )
    return harness


@pytest.mark.parametrize("available", [True, False])
def test_gtk_ripping_window_stop_uses_clicked_station(tmp_path, available) -> None:
    from fluxtuner.core.ripping import RippingAvailability

    harness = _ripping_stop_harness(tmp_path)
    harness.ripping_availability = RippingAvailability(available)
    selection = harness.selected_station

    window.MainWindow.stop_station_ripping(
        harness,
        {
            "name": "Clicked station",
            "url": "https://example.com/original",
            "url_resolved": "https://example.com/clicked",
        },
    )

    harness._ripping_profile_context.assert_called_once_with()
    harness.ripping_service.stop.assert_called_once_with()
    harness.ripping_service.wait.assert_not_called()
    harness._ensure_ripping_state_timer.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with("Stopping ripping: Running station")
    assert harness.selected_station is selection


@pytest.mark.parametrize("case", ["other_station", "other_profile", "completed", "no_job"])
def test_gtk_ripping_window_stop_rejects_unrelated_job(tmp_path, case) -> None:
    from dataclasses import replace

    harness = _ripping_stop_harness(tmp_path)
    station = {"name": "Clicked station", "url": "https://example.com/clicked"}
    if case == "other_station":
        station["url"] = "https://example.com/other"
    elif case == "other_profile":
        harness._ripping_profile_context.return_value = (8, "Other profile")
    elif case == "completed":
        snapshot = harness.ripping_service.snapshot.return_value
        harness.ripping_service.snapshot.return_value = replace(snapshot, state="completed")
    else:
        harness.ripping_service.snapshot.return_value = None
    selection = harness.selected_station

    window.MainWindow.stop_station_ripping(harness, station)

    harness.ripping_service.stop.assert_not_called()
    harness.ripping_service.wait.assert_not_called()
    harness._ensure_ripping_state_timer.assert_not_called()
    harness.status_label.set_text.assert_not_called()
    assert harness.selected_station is selection


def test_gtk_ripping_window_stop_contains_profile_failure(tmp_path) -> None:
    from fluxtuner.core.ripping import RippingError

    harness = _ripping_stop_harness(tmp_path)
    harness._ripping_profile_context.side_effect = RippingError("Ripping profile is unavailable.")

    window.MainWindow.stop_station_ripping(
        harness, {"name": "Clicked station", "url": "https://example.com/clicked"}
    )

    harness.ripping_service.stop.assert_not_called()
    harness._ensure_ripping_state_timer.assert_not_called()
    harness.status_label.set_text.assert_called_once_with(
        "Could not stop ripping: Ripping profile is unavailable."
    )


def test_gtk_ripping_window_stop_during_shutdown_is_ignored(tmp_path) -> None:
    harness = _ripping_stop_harness(tmp_path)
    harness._ripping_shutting_down = True

    window.MainWindow.stop_station_ripping(
        harness, {"name": "Clicked station", "url": "https://example.com/clicked"}
    )

    harness._ripping_profile_context.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    harness._ensure_ripping_state_timer.assert_not_called()
    harness.status_label.set_text.assert_not_called()


def test_gtk_ripping_window_stop_reports_failure_and_keeps_tracking(tmp_path) -> None:
    from fluxtuner.core.ripping import RippingError

    harness = _ripping_stop_harness(tmp_path)
    harness.ripping_service.stop.side_effect = RippingError("Stop worker unavailable.")

    window.MainWindow.stop_station_ripping(
        harness, {"name": "Clicked station", "url": "https://example.com/clicked"}
    )

    harness.ripping_service.stop.assert_called_once_with()
    harness.ripping_service.wait.assert_not_called()
    harness._ensure_ripping_state_timer.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with(
        "Could not stop ripping: Stop worker unavailable."
    )


def _ripping_shutdown_harness() -> SimpleNamespace:
    from fluxtuner.core.ripping_service import RippingService
    from fluxtuner.gui.gtk_ripping import RippingShutdown

    service = Mock(spec=RippingService)
    service.wait.return_value = True
    recording_manager = Mock()
    recording_manager.active_session = None
    recording_shutdown = Mock()
    recording_shutdown.requested = False
    recording_shutdown.error = None
    recording_shutdown.poll.return_value = True
    return SimpleNamespace(
        _recording_shutdown=recording_shutdown,
        _shutdown_deadline=None,
        _shutdown_warning_open=False,
        _shutdown_close_authorized=False,
        ripping_service=service,
        _ripping_shutdown=RippingShutdown(service=service),
        _ripping_shutting_down=False,
        _ripping_state_timer_id=None,
        _shutdown_timer_id=None,
        _shutdown_on_complete=None,
        close=Mock(),
        _poll_shutdown=Mock(),
        recording_manager=recording_manager,
        player=Mock(),
        usage_tracker=Mock(),
        _stop_usage_timer=Mock(),
        _stop_player_state_timer=Mock(),
        _stop_metadata_polling=Mock(),
        status_label=Mock(),
    )


def test_gtk_ripping_window_shutdown_reports_pending_workers() -> None:
    harness = _ripping_shutdown_harness()
    harness.ripping_service.wait.return_value = False

    ready = window.MainWindow.shutdown(harness)

    assert ready is False
    assert harness._ripping_shutting_down is True
    harness.ripping_service.stop.assert_called_once_with()
    harness.ripping_service.wait.assert_called_once_with(timeout=0)
    harness.player.stop.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()


def test_gtk_ripping_window_shutdown_repeats_only_completion_check() -> None:
    harness = _ripping_shutdown_harness()
    harness.ripping_service.wait.side_effect = [False, True]
    harness.recording_manager.active_session = object()

    assert window.MainWindow.shutdown(harness) is False
    assert window.MainWindow.shutdown(harness) is True

    harness.ripping_service.stop.assert_called_once_with()
    assert harness.ripping_service.wait.call_args_list == [call(timeout=0), call(timeout=0)]
    harness._stop_usage_timer.assert_called_once_with()
    harness._stop_player_state_timer.assert_called_once_with()
    harness._stop_metadata_polling.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    harness._recording_shutdown.request.assert_called_once_with()
    harness.recording_manager.stop.assert_not_called()
    harness.player.stop.assert_called_once_with()


def test_gtk_ripping_window_shutdown_removes_state_timer(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness._ripping_state_timer_id = 17
    harness.ripping_service.wait.return_value = False
    remove = Mock()
    monkeypatch.setattr(window.GLib, "source_remove", remove, raising=False)

    assert window.MainWindow.shutdown(harness) is False
    assert window.MainWindow.shutdown(harness) is False

    remove.assert_called_once_with(17)
    assert harness._ripping_state_timer_id is None


def test_gtk_ripping_window_shutdown_contains_and_reports_stop_failure() -> None:
    from fluxtuner.core.ripping import RippingError

    harness = _ripping_shutdown_harness()
    error = RippingError("Stop worker unavailable.")
    harness.ripping_service.stop.side_effect = error
    harness.ripping_service.wait.side_effect = [False, True]

    assert window.MainWindow.shutdown(harness) is False
    # A Brynse stop failure must not authorize automatic exit.
    assert window.MainWindow.shutdown(harness) is False

    assert harness._ripping_shutdown.error is error
    harness.ripping_service.stop.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with(
        "Could not stop ripping: Stop worker unavailable."
    )
    harness.player.stop.assert_called_once_with()


def test_gtk_ripping_window_shutdown_without_workers_is_ready() -> None:
    harness = _ripping_shutdown_harness()

    assert window.MainWindow.shutdown(harness) is True

    harness.ripping_service.stop.assert_called_once_with()
    harness.ripping_service.wait.assert_called_once_with(timeout=0)
    harness.status_label.set_text.assert_not_called()


def test_gtk_ripping_close_wait_defers_window_close(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = False
    harness._quit_confirmation_pending = False
    harness.ripping_service.wait.side_effect = [False, False, False, True]
    dialogs = []

    harness.request_quit = lambda *, on_complete: window.MainWindow.request_quit(
        harness, on_complete=on_complete
    )
    harness._show_quit_confirmation = Mock(
        side_effect=lambda *, on_confirm, on_cancel: dialogs.append((on_confirm, on_cancel))
    )

    schedule = Mock(return_value=23)
    monkeypatch.setattr(window.GLib, "timeout_add", schedule, raising=False)

    assert window.MainWindow.on_close_request(harness, Mock()) is True
    assert len(dialogs) == 1

    harness.close.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    schedule.assert_not_called()

    dialogs[0][0]()

    harness.ripping_service.stop.assert_called_once_with()
    harness.close.assert_not_called()
    assert harness._shutdown_timer_id == 23
    schedule.assert_called_once()
    interval, callback = schedule.call_args.args
    assert 0 < interval <= 1000
    assert callback is harness._poll_shutdown

    assert window.MainWindow._poll_shutdown(harness) is True
    harness.close.assert_not_called()

    assert window.MainWindow._poll_shutdown(harness) is False
    harness.close.assert_called_once_with()
    assert harness._shutdown_timer_id is None
    assert harness._shutdown_on_complete is None


def test_gtk_ripping_close_wait_repeated_close_uses_one_timer(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = False
    harness._quit_confirmation_pending = False
    harness.ripping_service.wait.side_effect = [False, False, True]
    dialogs = []

    harness.request_quit = lambda *, on_complete: window.MainWindow.request_quit(
        harness, on_complete=on_complete
    )
    harness._show_quit_confirmation = Mock(
        side_effect=lambda *, on_confirm, on_cancel: dialogs.append((on_confirm, on_cancel))
    )

    schedule = Mock(return_value=23)
    monkeypatch.setattr(window.GLib, "timeout_add", schedule, raising=False)

    assert window.MainWindow.on_close_request(harness, Mock()) is True
    assert window.MainWindow.on_close_request(harness, Mock()) is True

    assert len(dialogs) == 1
    harness.ripping_service.stop.assert_not_called()
    schedule.assert_not_called()

    dialogs[0][0]()

    assert harness._shutdown_timer_id == 23
    assert window.MainWindow._poll_shutdown(harness) is False

    schedule.assert_called_once()
    harness.close.assert_called_once_with()
    harness.player.stop.assert_called_once_with()
    harness.ripping_service.stop.assert_called_once_with()


def test_gtk_ripping_close_wait_latest_completion_replaces_pending_callback(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.ripping_service.wait.side_effect = [False, False, True]
    schedule = Mock(return_value=23)
    monkeypatch.setattr(window.GLib, "timeout_add", schedule, raising=False)
    first = Mock()
    latest = Mock()

    assert window.MainWindow.shutdown(harness, on_complete=first) is False
    assert window.MainWindow.shutdown(harness, on_complete=latest) is False
    first.assert_not_called()
    latest.assert_not_called()

    assert window.MainWindow._poll_shutdown(harness) is False

    # Preserve the first pending completion (Quit priority).
    first.assert_called_once_with()
    latest.assert_not_called()
    schedule.assert_called_once()


def test_gtk_ripping_close_wait_ready_needs_no_timer_or_callback(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    schedule = Mock()
    monkeypatch.setattr(window.GLib, "timeout_add", schedule, raising=False)
    completed = Mock()

    assert window.MainWindow.shutdown(harness, on_complete=completed) is True

    schedule.assert_not_called()
    completed.assert_not_called()
    assert harness._shutdown_timer_id is None


def test_gtk_ripping_close_wait_ready_cancels_pending_timer(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.ripping_service.wait.side_effect = [False, True]
    schedule = Mock(return_value=23)
    remove = Mock()
    monkeypatch.setattr(window.GLib, "timeout_add", schedule, raising=False)
    monkeypatch.setattr(window.GLib, "source_remove", remove, raising=False)
    completed = Mock()

    assert window.MainWindow.shutdown(harness, on_complete=completed) is False
    assert window.MainWindow.shutdown(harness, on_complete=completed) is True

    remove.assert_called_once_with(23)
    assert harness._shutdown_timer_id is None
    assert harness._shutdown_on_complete is None
    completed.assert_not_called()

    assert window.MainWindow._poll_shutdown(harness) is False
    assert harness.ripping_service.wait.call_count == 2
    completed.assert_not_called()


def test_gtk_ripping_close_wait_tray_hide_keeps_operation_running(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = True
    harness.set_visible = Mock()
    schedule = Mock()
    monkeypatch.setattr(window.GLib, "timeout_add", schedule, raising=False)

    assert window.MainWindow.on_close_request(harness, Mock()) is True

    harness.set_visible.assert_called_once_with(False)
    harness.ripping_service.stop.assert_not_called()
    harness.ripping_service.wait.assert_not_called()
    harness.player.stop.assert_not_called()
    schedule.assert_not_called()
    assert harness._ripping_shutting_down is False


@pytest.mark.parametrize("ready_on_close", [False, True])
def test_gtk_ripping_close_priority_preserves_pending_quit(monkeypatch, ready_on_close) -> None:
    harness = _ripping_shutdown_harness()
    harness.close_to_tray = False
    harness.ripping_service.wait.side_effect = [False, ready_on_close, True]
    schedule = Mock(return_value=23)
    remove = Mock()
    monkeypatch.setattr(window.GLib, "timeout_add", schedule, raising=False)
    monkeypatch.setattr(window.GLib, "source_remove", remove, raising=False)
    finish_quit = Mock()

    assert window.MainWindow.shutdown(harness, on_complete=finish_quit) is False

    assert window.MainWindow.on_close_request(harness, Mock()) is True

    if not ready_on_close:
        finish_quit.assert_not_called()
        assert harness._shutdown_on_complete is finish_quit
        assert window.MainWindow._poll_shutdown(harness) is False
        remove.assert_not_called()
    else:
        remove.assert_called_once_with(23)

    finish_quit.assert_called_once_with()
    harness.close.assert_not_called()
    harness.ripping_service.stop.assert_called_once_with()
    harness.player.stop.assert_called_once_with()
    schedule.assert_called_once()
    assert harness._shutdown_timer_id is None
    assert harness._shutdown_on_complete is None


@pytest.mark.parametrize("action", ["play_station", "start_station_recording"])
def test_gtk_closing_actions_reject_new_runtime_work(monkeypatch, tmp_path, action) -> None:
    harness = Mock()
    harness._ripping_shutting_down = True
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
    monkeypatch.setattr(window.manual_playlists, "get_playlist", lookup)
    monkeypatch.setattr(window.manual_playlists, "get_playlist_stations", contents)

    window.MainWindow._show_saved_playlist(harness, "Morning")

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
    monkeypatch.setattr(window.manual_playlists, "get_playlist", Mock(return_value=None))

    window.MainWindow._show_saved_playlist(harness, "Deleted")

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
        window,
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
    monkeypatch.setattr(window.manual_playlists, f"{operation}_playlist", storage)
    handler = getattr(window.MainWindow, f"on_{operation}_playlist_clicked")
    handler(harness, Mock())
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
    monkeypatch.setattr(window.manual_playlists, f"{operation}_playlist", storage)
    handler = getattr(window.MainWindow, f"on_{operation}_playlist_clicked")
    handler(harness, Mock())
    respond = dialog.connect.call_args.args[1]
    harness._playlist_profile_id.return_value = 8

    respond(dialog, 1)

    storage.assert_not_called()
    dialog.destroy.assert_not_called()
    error.set_text.assert_called_once_with("The profile changed. Reopen this dialog.")


def test_create_playlist_trims_name_and_opens_new_list(monkeypatch) -> None:
    harness, dialog, _entry, _error = _playlist_management_dialog(monkeypatch)
    storage = Mock(return_value=True)
    monkeypatch.setattr(window.manual_playlists, "create_playlist", storage)
    window.MainWindow.on_create_playlist_clicked(harness, Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    storage.assert_called_once_with("Morning", profile_id=7)
    dialog.destroy.assert_called_once_with()
    harness._show_saved_playlist.assert_called_once_with("Morning")


@pytest.mark.parametrize("name", ["", "   "])
def test_create_playlist_rejects_blank_name(monkeypatch, name) -> None:
    harness, dialog, entry, error = _playlist_management_dialog(monkeypatch)
    entry.get_text.return_value = name
    storage = Mock()
    monkeypatch.setattr(window.manual_playlists, "create_playlist", storage)
    window.MainWindow.on_create_playlist_clicked(harness, Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    storage.assert_not_called()
    dialog.destroy.assert_not_called()
    error.set_text.assert_called_once_with("Enter a playlist name.")


def test_duplicate_playlist_keeps_dialog_open(monkeypatch) -> None:
    harness, dialog, _entry, error = _playlist_management_dialog(monkeypatch)
    monkeypatch.setattr(window.manual_playlists, "create_playlist", Mock(return_value=False))
    window.MainWindow.on_create_playlist_clicked(harness, Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    dialog.destroy.assert_not_called()
    harness._show_saved_playlist.assert_not_called()
    error.set_text.assert_called_once_with("A playlist with this name already exists.")


def test_delete_playlist_uses_captured_name_and_profile(monkeypatch) -> None:
    harness, dialog, _entry, _error = _playlist_management_dialog(monkeypatch)
    storage = Mock(return_value=True)
    monkeypatch.setattr(window.manual_playlists, "delete_playlist", storage)
    window.MainWindow.on_delete_playlist_clicked(harness, Mock())
    respond = dialog.connect.call_args.args[1]

    respond(dialog, 1)

    storage.assert_called_once_with("Morning", profile_id=7)
    dialog.destroy.assert_called_once_with()
    harness._show_all_favorites.assert_called_once_with()
    harness._refresh_saved_playlists.assert_called_once_with()


def test_delete_playlist_storage_error_preserves_view(monkeypatch) -> None:
    harness, dialog, _entry, error = _playlist_management_dialog(monkeypatch)
    monkeypatch.setattr(
        window.manual_playlists,
        "delete_playlist",
        Mock(side_effect=OSError("Storage unavailable")),
    )
    window.MainWindow.on_delete_playlist_clicked(harness, Mock())

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

    window.MainWindow._build_application_menu(harness, container)

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
        window,
        "Gtk",
        SimpleNamespace(
            Entry=Mock(side_effect=[name_entry, url_entry]),
            ResponseType=SimpleNamespace(ACCEPT=1, CANCEL=0),
        ),
    )
    connect = Mock(side_effect=lambda: nullcontext(conn))
    monkeypatch.setattr(window.db, "connect", connect)
    save = Mock(return_value=True)
    monkeypatch.setattr(window, "add_custom_station", save, raising=False)
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

    window.MainWindow.on_add_custom_station_clicked(harness, Mock())

    harness.application_menu_popover.popdown.assert_called_once_with()
    harness._make_playlist_dialog.assert_called_once_with("Add station", "Add")
    dialog.present.assert_called_once_with()
    connect.assert_not_called()
    save.assert_not_called()
    conn.commit.assert_not_called()


def test_custom_station_dialog_cancel_does_not_write(monkeypatch):
    harness, dialog, _error, _conn, connect, save = _custom_station_dialog(monkeypatch)
    window.MainWindow.on_add_custom_station_clicked(harness, Mock())

    dialog.connect.call_args.args[1](dialog, 0)

    connect.assert_not_called()
    save.assert_not_called()
    dialog.destroy.assert_called_once_with()
    harness._show_all_favorites.assert_not_called()


def test_custom_station_dialog_rejects_profile_change(monkeypatch):
    harness, dialog, error, _conn, connect, save = _custom_station_dialog(monkeypatch)
    window.MainWindow.on_add_custom_station_clicked(harness, Mock())
    harness._playlist_profile_id.return_value = 8

    dialog.connect.call_args.args[1](dialog, 1)

    connect.assert_not_called()
    save.assert_not_called()
    dialog.destroy.assert_not_called()
    error.set_text.assert_called_once_with("The profile changed. Reopen this dialog.")


def test_custom_station_dialog_rejects_missing_profile_on_open(monkeypatch):
    harness, dialog, _error, _conn, connect, save = _custom_station_dialog(monkeypatch)
    harness._playlist_profile_id.side_effect = ValueError("Profile unavailable")

    window.MainWindow.on_add_custom_station_clicked(harness, Mock())

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
    window.MainWindow.on_add_custom_station_clicked(harness, Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    dialog.destroy.assert_not_called()
    conn.commit.assert_not_called()
    harness._show_all_favorites.assert_not_called()
    error.set_text.assert_called_once_with(str(failure))


@pytest.mark.parametrize("added", [True, False])
def test_custom_station_dialog_saves_captured_profile_and_refreshes(monkeypatch, added):
    harness, dialog, _error, conn, _connect, save = _custom_station_dialog(monkeypatch)
    save.return_value = added
    window.MainWindow.on_add_custom_station_clicked(harness, Mock())

    dialog.connect.call_args.args[1](dialog, 1)

    save.assert_called_once_with(
        conn,
        profile_id=7,
        name="Personal radio",
        url="https://radio.example/live",
    )
    conn.commit.assert_called_once_with()
    dialog.destroy.assert_called_once_with()
    harness._show_all_favorites.assert_called_once_with()
    harness._refresh_saved_playlists.assert_called_once_with()
    harness.status_label.set_text.assert_called_once_with(
        "Station added to favorites." if added else "Station is already in favorites."
    )


def test_gtk_quit_request_without_recordings_starts_shutdown(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness._quit_confirmation_pending = False
    harness._show_quit_confirmation = Mock()
    completed = Mock()

    from fluxtuner.gui.gtk_ripping import shutdown_has_pending_recordings

    assert (
        shutdown_has_pending_recordings(
            recording_manager=harness.recording_manager,
            ripping_service=harness.ripping_service,
        )
        is False
    )

    window.MainWindow.request_quit(harness, on_complete=completed)

    harness._show_quit_confirmation.assert_not_called()
    harness.ripping_service.stop.assert_called_once_with()
    completed.assert_called_once_with()


def test_gtk_quit_request_requires_confirmation(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.recording_manager.active_session = object()
    harness._quit_confirmation_pending = False
    harness._show_quit_confirmation = Mock()
    completed = Mock()

    window.MainWindow.request_quit(harness, on_complete=completed)

    harness._show_quit_confirmation.assert_called_once()
    harness.recording_manager.stop.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    harness.player.stop.assert_not_called()
    completed.assert_not_called()


def test_gtk_quit_confirmation_cancel_or_accept(monkeypatch) -> None:
    harness = _ripping_shutdown_harness()
    harness.recording_manager.active_session = object()
    harness._quit_confirmation_pending = False
    callbacks = []
    completed = Mock()

    def capture_dialog(*, on_confirm, on_cancel):
        callbacks.append((on_confirm, on_cancel))

    harness._show_quit_confirmation = Mock(side_effect=capture_dialog)

    window.MainWindow.request_quit(harness, on_complete=completed)
    window.MainWindow.request_quit(harness, on_complete=completed)

    assert len(callbacks) == 1
    harness.ripping_service.stop.assert_not_called()
    harness.recording_manager.stop.assert_not_called()

    callbacks[0][1]()

    harness.ripping_service.stop.assert_not_called()
    harness.recording_manager.stop.assert_not_called()
    completed.assert_not_called()

    window.MainWindow.request_quit(harness, on_complete=completed)
    assert len(callbacks) == 2

    callbacks[1][0]()

    harness.ripping_service.stop.assert_called_once_with()
    harness._recording_shutdown.request.assert_called_once_with()
    harness.recording_manager.stop.assert_not_called()
    completed.assert_called_once_with()


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
    harness._quit_confirmation_pending = False
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

    assert harness._quit_confirmation_pending is False
    harness.recording_manager.stop.assert_not_called()
    harness.ripping_service.stop.assert_not_called()
    harness.close.assert_not_called()

    assert window.MainWindow.on_close_request(harness, Mock()) is True
    assert len(callbacks) == 2
    callbacks[1][0]()

    harness._recording_shutdown.request.assert_called_once_with()
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


def _shutdown_coordinator_harness():
    harness = _ripping_shutdown_harness()
    harness._recording_shutdown = Mock()
    harness._recording_shutdown.requested = False
    harness._recording_shutdown.poll.return_value = True
    harness._recording_shutdown.error = None
    harness._shutdown_deadline = None
    harness._shutdown_warning_open = False
    return harness


def test_gtk_shutdown_combined_worker_pending_does_not_complete(monkeypatch) -> None:
    harness = _shutdown_coordinator_harness()
    harness.recording_manager.active_session = object()
    harness._recording_shutdown.requested = True
    harness._recording_shutdown.poll.return_value = False
    completed = Mock()
    monkeypatch.setattr(window.GLib, "timeout_add", Mock(return_value=29), raising=False)

    assert window.MainWindow.shutdown(harness, on_complete=completed) is False
    harness._recording_shutdown.request.assert_called_once_with()
    harness.recording_manager.stop.assert_not_called()
    completed.assert_not_called()
    assert harness._shutdown_timer_id == 29


def test_gtk_shutdown_combined_worker_finishes_then_completes(monkeypatch) -> None:
    harness = _shutdown_coordinator_harness()
    harness._ripping_shutting_down = True
    harness._shutdown_on_complete = Mock()
    harness._shutdown_timer_id = 29
    harness._shutdown_deadline = 100.0
    harness._recording_shutdown.requested = True
    harness._recording_shutdown.poll.side_effect = [False, True]
    harness._ripping_shutdown.poll = Mock(return_value=True)
    monkeypatch.setattr(window, "monotonic", lambda: 10.0)

    assert window.MainWindow._poll_shutdown(harness) is True
    callback = harness._shutdown_on_complete
    callback.assert_not_called()
    assert window.MainWindow._poll_shutdown(harness) is False
    callback.assert_called_once_with()


def test_gtk_shutdown_deadline_offers_wait_or_force(monkeypatch) -> None:
    harness = _shutdown_coordinator_harness()
    harness._ripping_shutting_down = True
    harness._shutdown_on_complete = Mock()
    finish = harness._shutdown_on_complete
    harness._shutdown_deadline = 10.0
    harness._shutdown_timer_id = 29
    harness._ripping_shutdown.poll = Mock(return_value=False)
    harness._show_shutdown_warning = Mock()
    clock = [11.0, 11.0, 20.0]
    monkeypatch.setattr(window, "monotonic", lambda: clock.pop(0))

    assert window.MainWindow._poll_shutdown(harness) is True
    harness._show_shutdown_warning.assert_called_once()
    callbacks = harness._show_shutdown_warning.call_args.kwargs
    finish.assert_not_called()
    assert window.MainWindow._poll_shutdown(harness) is True
    harness._show_shutdown_warning.assert_called_once()

    callbacks["on_wait"]()
    assert harness._shutdown_warning_open is False
    assert harness._shutdown_deadline == 23.0
    finish.assert_not_called()
    assert window.MainWindow._poll_shutdown(harness) is True
    assert harness._show_shutdown_warning.call_count == 1


def test_gtk_shutdown_failure_requires_explicit_decision(monkeypatch) -> None:
    harness = _shutdown_coordinator_harness()
    harness._ripping_shutting_down = True
    harness._shutdown_on_complete = Mock()
    finish = harness._shutdown_on_complete
    harness._shutdown_timer_id = 29
    harness._shutdown_deadline = 100.0
    harness._ripping_shutdown.poll = Mock(return_value=True)
    harness._recording_shutdown.error = RuntimeError("disk failure")
    harness._show_shutdown_warning = Mock()
    monkeypatch.setattr(window, "monotonic", lambda: 110.0)

    assert window.MainWindow._poll_shutdown(harness) is True
    assert harness._show_shutdown_warning.call_args.kwargs["has_error"] is True
    finish.assert_not_called()
    harness._show_shutdown_warning.call_args.kwargs["on_force"]()
    finish.assert_called_once_with()
