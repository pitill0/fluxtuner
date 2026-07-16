from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner import tui
from fluxtuner.tui_playback import coordinate_playback_start, coordinate_playback_stop


def _station() -> dict[str, object]:
    return {
        "name": "Flux FM",
        "url_resolved": "https://radio.example/stream",
    }


def _playback_harness(*, player: Mock | None = None) -> SimpleNamespace:
    player = player or Mock()
    player.is_playing.return_value = True
    return SimpleNamespace(
        player=player,
        player_backend_name="mpv",
        profile_name="default",
        usage_tracker=Mock(),
        playing_station=None,
        last_station=None,
        station_supported=Mock(return_value=True),
        station_url=Mock(side_effect=lambda station: str(station.get("url_resolved", ""))),
        _start_usage_tracking=Mock(),
        apply_restored_playback_preferences=Mock(),
        persist_player_state=Mock(),
    )


def _start(harness: SimpleNamespace, station: dict[str, object], add_history: Mock):
    return coordinate_playback_start(
        station,
        player=harness.player,
        player_backend_name=harness.player_backend_name,
        profile_name=harness.profile_name,
        station_supported=harness.station_supported,
        station_url=harness.station_url,
        start_usage_tracking=harness._start_usage_tracking,
        add_history_entry=add_history,
        apply_restored_preferences=harness.apply_restored_playback_preferences,
        persist_playback_state=harness.persist_player_state,
    )


def test_tui_playback_coordinator_commits_successful_playback_once() -> None:
    station = _station()
    harness = _playback_harness()
    add_history = Mock()

    result = _start(harness, station, add_history)

    assert result.success is True
    assert result.station is station
    assert result.status == "Playing: Flux FM"
    assert result.error_notification is None
    harness.station_supported.assert_called_once_with(station)
    harness.station_url.assert_called_once_with(station)
    harness.player.play.assert_called_once_with("https://radio.example/stream")
    harness._start_usage_tracking.assert_called_once_with(station)
    add_history.assert_called_once_with(station, profile_name="default")
    harness.apply_restored_playback_preferences.assert_called_once_with()
    harness.persist_player_state.assert_called_once_with(last_station=station)


def test_tui_playback_coordinator_rejects_unsupported_station(monkeypatch) -> None:
    station = _station()
    harness = _playback_harness()
    harness.station_supported.return_value = False
    add_history = Mock()
    monkeypatch.setattr(
        "fluxtuner.tui_playback.unsupported_station_message",
        lambda *_args: "Unsupported.",
    )

    result = _start(harness, station, add_history)

    assert result.success is False
    assert result.status == "Unsupported."
    harness.station_url.assert_not_called()
    harness.player.play.assert_not_called()
    add_history.assert_not_called()


def test_tui_playback_coordinator_rejects_missing_url() -> None:
    station = {"name": "No URL"}
    harness = _playback_harness()
    harness.station_url.return_value = ""
    add_history = Mock()

    result = _start(harness, station, add_history)

    assert result.success is False
    assert result.status == "Selected station has no playable URL."
    harness.player.play.assert_not_called()
    add_history.assert_not_called()


def test_tui_playback_coordinator_failure_does_not_commit_side_effects() -> None:
    station = _station()
    player = Mock()
    player.play.side_effect = RuntimeError("backend unavailable")
    harness = _playback_harness(player=player)
    add_history = Mock()

    result = _start(harness, station, add_history)

    assert result.success is False
    assert result.status == "Playback failed: backend unavailable"
    assert result.error_notification == "Playback failed: backend unavailable"
    add_history.assert_not_called()
    harness._start_usage_tracking.assert_not_called()
    harness.persist_player_state.assert_not_called()


def test_tui_playback_coordinator_stops_player_and_tracking() -> None:
    harness = _playback_harness()

    result = coordinate_playback_stop(
        player=harness.player,
        usage_tracker=harness.usage_tracker,
    )

    harness.player.stop.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    assert result.status == "Playback stopped."


def test_tui_playback_coordinator_tolerates_tracker_stop_failure() -> None:
    harness = _playback_harness()
    harness.usage_tracker.stop.side_effect = RuntimeError("tracker stopped")

    result = coordinate_playback_stop(
        player=harness.player,
        usage_tracker=harness.usage_tracker,
    )

    harness.player.stop.assert_called_once_with()
    assert result.status == "Playback stopped."


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
        _metadata_request_id=0,
        cancel_pending_search=Mock(),
        usage_tracker=Mock(),
        player=Mock(),
    )
    harness._cancel_metadata_request = lambda: tui.FluxTunerTUI._cancel_metadata_request(harness)

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
        _metadata_request_id=0,
        cancel_pending_search=Mock(),
        usage_tracker=Mock(),
        player=Mock(),
    )
    harness._cancel_metadata_request = lambda: tui.FluxTunerTUI._cancel_metadata_request(harness)

    tui.FluxTunerTUI.on_unmount(harness)

    metadata_task.cancel.assert_not_called()
    harness.player.stop.assert_called_once_with()
