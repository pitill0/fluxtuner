from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner import tui


def _station() -> dict[str, object]:
    return {
        "name": "Flux FM",
        "url_resolved": "https://radio.example/stream",
    }


def _playback_harness(*, player: Mock | None = None) -> SimpleNamespace:
    player = player or Mock()
    player.is_playing.return_value = True

    harness = SimpleNamespace(
        player=player,
        player_backend_name="mpv",
        profile_name="default",
        usage_tracker=Mock(),
        playing_station=None,
        last_station=None,
        _last_metadata_fetch_at=42.0,
        station_supported=Mock(return_value=True),
        station_url=Mock(side_effect=lambda station: str(station.get("url_resolved", ""))),
        _clear_metadata=Mock(),
        _start_usage_tracking=Mock(),
        apply_restored_playback_preferences=Mock(),
        persist_player_state=Mock(),
        update_now_playing=Mock(),
        refresh_active_station_marker=Mock(),
        _refresh_current_station_view_after_marker_change=Mock(),
        update_play_button=Mock(),
        set_status=Mock(),
        notify=Mock(),
    )
    return harness


def test_tui_play_station_commits_successful_playback_once(monkeypatch) -> None:
    station = _station()
    harness = _playback_harness()
    add_history = Mock()
    monkeypatch.setattr(tui, "add_history", add_history)

    result = tui.FluxTunerTUI.play_station(harness, station)

    assert result is True
    harness.station_supported.assert_called_once_with(station)
    harness.station_url.assert_called_once_with(station)
    harness.player.play.assert_called_once_with("https://radio.example/stream")
    assert harness.playing_station is station
    assert harness.last_station is station
    harness._clear_metadata.assert_called_once_with()
    assert harness._last_metadata_fetch_at == 0.0
    harness._start_usage_tracking.assert_called_once_with(station)
    add_history.assert_called_once_with(station, profile_name="default")
    harness.apply_restored_playback_preferences.assert_called_once_with()
    harness.persist_player_state.assert_called_once_with(last_station=station)
    harness.update_now_playing.assert_called_once_with()
    harness.refresh_active_station_marker.assert_called_once_with()
    harness._refresh_current_station_view_after_marker_change.assert_called_once_with()
    harness.update_play_button.assert_called_once_with()
    harness.set_status.assert_called_once_with("Playing: Flux FM")
    harness.notify.assert_not_called()


def test_tui_play_station_rejects_unsupported_station_before_player(monkeypatch) -> None:
    station = _station()
    harness = _playback_harness()
    harness.station_supported.return_value = False
    add_history = Mock()
    monkeypatch.setattr(tui, "add_history", add_history)
    monkeypatch.setattr(tui, "unsupported_station_message", lambda *_args: "Unsupported.")

    result = tui.FluxTunerTUI.play_station(harness, station)

    assert result is False
    harness.station_url.assert_not_called()
    harness.player.play.assert_not_called()
    add_history.assert_not_called()
    assert harness.playing_station is None
    assert harness.last_station is None
    harness.set_status.assert_called_once_with("Unsupported.")


def test_tui_play_station_rejects_missing_url_before_player(monkeypatch) -> None:
    station = {"name": "No URL"}
    harness = _playback_harness()
    harness.station_url.return_value = ""
    add_history = Mock()
    monkeypatch.setattr(tui, "add_history", add_history)

    result = tui.FluxTunerTUI.play_station(harness, station)

    assert result is False
    harness.player.play.assert_not_called()
    add_history.assert_not_called()
    assert harness.playing_station is None
    assert harness.last_station is None
    harness.set_status.assert_called_once_with("Selected station has no playable URL.")


def test_tui_play_station_failure_does_not_commit_state_or_history(monkeypatch) -> None:
    station = _station()
    player = Mock()
    player.play.side_effect = RuntimeError("backend unavailable")
    harness = _playback_harness(player=player)
    add_history = Mock()
    monkeypatch.setattr(tui, "add_history", add_history)

    result = tui.FluxTunerTUI.play_station(harness, station)

    assert result is False
    add_history.assert_not_called()
    assert harness.playing_station is None
    assert harness.last_station is None
    harness._start_usage_tracking.assert_not_called()
    harness.persist_player_state.assert_not_called()
    harness.set_status.assert_called_once_with("Playback failed: backend unavailable")
    harness.notify.assert_called_once_with(
        "Playback failed: backend unavailable",
        severity="error",
    )


def test_tui_stop_playback_stops_tracking_and_projects_idle_state() -> None:
    harness = _playback_harness()
    harness.playing_station = _station()

    tui.FluxTunerTUI.stop_playback(harness)

    harness.player.stop.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    assert harness.playing_station is None
    harness.update_now_playing.assert_called_once_with()
    harness.refresh_active_station_marker.assert_called_once_with()
    harness._refresh_current_station_view_after_marker_change.assert_called_once_with()
    harness.update_play_button.assert_called_once_with()
    harness.set_status.assert_called_once_with("Playback stopped.")


def test_tui_stop_playback_tolerates_usage_tracker_failure() -> None:
    harness = _playback_harness()
    harness.usage_tracker.stop.side_effect = RuntimeError("tracker stopped")

    tui.FluxTunerTUI.stop_playback(harness)

    harness.player.stop.assert_called_once_with()
    assert harness.playing_station is None
    harness.set_status.assert_called_once_with("Playback stopped.")


@pytest.mark.parametrize(
    ("view_mode", "expected"),
    [
        ("themes", "theme"),
        ("playlists", "playlist"),
        ("search", "station"),
        ("favorites", "station"),
    ],
)
def test_tui_activate_selected_routes_by_view_mode(view_mode: str, expected: str) -> None:
    harness = SimpleNamespace(
        view_mode=view_mode,
        apply_selected_theme=Mock(),
        smart_play_selected_playlist_or_tag=Mock(),
        play_selected_station=Mock(),
    )

    tui.FluxTunerTUI.action_activate_selected(harness)

    calls = {
        "theme": harness.apply_selected_theme.call_count,
        "playlist": harness.smart_play_selected_playlist_or_tag.call_count,
        "station": harness.play_selected_station.call_count,
    }
    assert calls[expected] == 1
    assert sum(calls.values()) == 1


def test_tui_unmount_cancels_tasks_and_stops_runtime_dependencies() -> None:
    metadata_task = Mock()
    metadata_task.done.return_value = False
    harness = SimpleNamespace(
        _metadata_task=metadata_task,
        cancel_pending_search=Mock(),
        usage_tracker=Mock(),
        player=Mock(),
    )

    tui.FluxTunerTUI.on_unmount(harness)

    harness.cancel_pending_search.assert_called_once_with()
    metadata_task.done.assert_called_once_with()
    metadata_task.cancel.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    harness.player.stop.assert_called_once_with()


def test_tui_unmount_does_not_cancel_completed_metadata_task() -> None:
    metadata_task = Mock()
    metadata_task.done.return_value = True
    harness = SimpleNamespace(
        _metadata_task=metadata_task,
        cancel_pending_search=Mock(),
        usage_tracker=Mock(),
        player=Mock(),
    )

    tui.FluxTunerTUI.on_unmount(harness)

    metadata_task.cancel.assert_not_called()
    harness.player.stop.assert_called_once_with()
