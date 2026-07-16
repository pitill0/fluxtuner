from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner import tui


def _metadata_harness(*, mounted: bool = False) -> SimpleNamespace:
    widget = Mock()
    harness = SimpleNamespace(
        playing_station=None,
        current_artist="Old artist",
        current_track="Old track",
        _metadata_task=None,
        _last_metadata_raw="old raw",
        _last_metadata_fetch_at=0.0,
        is_mounted=mounted,
        query_one=Mock(return_value=widget),
        station_url=Mock(return_value="https://radio.example/stream"),
    )
    harness.metadata_widget = widget
    return harness


def test_metadata_poll_does_not_schedule_without_playing_station(monkeypatch) -> None:
    harness = _metadata_harness()
    create_task = Mock()
    monkeypatch.setattr(asyncio, "create_task", create_task)

    tui.FluxTunerTUI._maybe_fetch_metadata(harness)

    create_task.assert_not_called()
    assert harness._last_metadata_fetch_at == 0.0


def test_metadata_poll_respects_fifteen_second_throttle(monkeypatch) -> None:
    harness = _metadata_harness()
    harness.playing_station = {"name": "Flux FM"}
    harness._last_metadata_fetch_at = 100.0
    create_task = Mock()

    monkeypatch.setattr(tui.time, "monotonic", lambda: 114.9)
    monkeypatch.setattr(asyncio, "create_task", create_task)

    tui.FluxTunerTUI._maybe_fetch_metadata(harness)

    create_task.assert_not_called()
    assert harness._last_metadata_fetch_at == 100.0


def test_metadata_poll_does_not_overlap_active_task(monkeypatch) -> None:
    harness = _metadata_harness()
    harness.playing_station = {"name": "Flux FM"}
    harness._metadata_task = SimpleNamespace(done=lambda: False)
    create_task = Mock()

    monkeypatch.setattr(tui.time, "monotonic", lambda: 20.0)
    monkeypatch.setattr(asyncio, "create_task", create_task)

    tui.FluxTunerTUI._maybe_fetch_metadata(harness)

    create_task.assert_not_called()
    assert harness._last_metadata_fetch_at == 0.0


def test_metadata_poll_does_not_schedule_without_station_url(monkeypatch) -> None:
    harness = _metadata_harness()
    harness.playing_station = {"name": "Flux FM"}
    harness.station_url.return_value = None
    create_task = Mock()

    monkeypatch.setattr(tui.time, "monotonic", lambda: 20.0)
    monkeypatch.setattr(asyncio, "create_task", create_task)

    tui.FluxTunerTUI._maybe_fetch_metadata(harness)

    create_task.assert_not_called()
    assert harness._last_metadata_fetch_at == 0.0


def test_successful_playback_resets_metadata_and_allows_immediate_poll(monkeypatch) -> None:
    station = {"name": "Flux FM", "url_resolved": "https://radio.example/stream"}
    result = SimpleNamespace(
        success=True,
        station=station,
        status="Playing Flux FM",
        error_notification=None,
    )
    clear_metadata = Mock()
    harness = SimpleNamespace(
        player=Mock(),
        player_backend_name="mpv",
        profile_name="default",
        station_supported=Mock(),
        station_url=Mock(),
        _start_usage_tracking=Mock(),
        apply_restored_playback_preferences=Mock(),
        persist_player_state=Mock(),
        playing_station={"name": "Old station"},
        last_station={"name": "Old station"},
        _clear_metadata=clear_metadata,
        _last_metadata_fetch_at=99.0,
        update_now_playing=Mock(),
        refresh_active_station_marker=Mock(),
        _refresh_current_station_view_after_marker_change=Mock(),
        update_play_button=Mock(),
        set_status=Mock(),
        notify=Mock(),
    )

    monkeypatch.setattr(tui, "coordinate_playback_start", lambda *_args, **_kwargs: result)

    played = tui.FluxTunerTUI.play_station(harness, station)

    assert played is True
    assert harness.playing_station is station
    assert harness.last_station is station
    clear_metadata.assert_called_once_with()
    assert harness._last_metadata_fetch_at == 0.0


def test_metadata_poll_records_schedule_time_and_stores_task(monkeypatch) -> None:
    harness = _metadata_harness()
    harness.playing_station = {"name": "Flux FM"}
    scheduled_task = Mock()
    create_task = Mock(return_value=scheduled_task)

    async def fake_fetch(_url):
        return None

    harness._fetch_metadata = fake_fetch

    monkeypatch.setattr(tui.time, "monotonic", lambda: 42.0)
    monkeypatch.setattr(asyncio, "create_task", create_task)

    tui.FluxTunerTUI._maybe_fetch_metadata(harness)

    assert harness._last_metadata_fetch_at == 42.0
    assert harness._metadata_task is scheduled_task
    create_task.assert_called_once()
    create_task.call_args.args[0].close()


@pytest.mark.parametrize(
    ("metadata", "expected_artist", "expected_track"),
    [
        ({"artist": "Artist", "title": "Track", "raw": "Artist - Track"}, "Artist", "Track"),
        ({"artist": "", "title": "", "raw": "Raw title"}, "—", "Raw title"),
        ({"artist": None, "title": None, "raw": ""}, "—", "—"),
    ],
)
def test_metadata_fetch_projects_artist_and_track_fallbacks(
    monkeypatch,
    metadata,
    expected_artist: str,
    expected_track: str,
) -> None:
    harness = _metadata_harness(mounted=True)
    harness._last_metadata_raw = None

    async def run_inline(function, *args):
        return function(*args)

    monkeypatch.setattr(asyncio, "to_thread", run_inline)
    monkeypatch.setattr(tui, "fetch_stream_metadata", lambda _url: metadata)

    asyncio.run(tui.FluxTunerTUI._fetch_metadata(harness, "https://radio.example/stream"))

    assert harness.current_artist == expected_artist
    assert harness.current_track == expected_track
    assert harness._last_metadata_raw == (metadata.get("raw") or "")
    harness.metadata_widget.update.assert_called_once_with(
        f"[b]Metadata[/b]\nArtist: {expected_artist}\nTrack: {expected_track}"
    )


def test_empty_metadata_does_not_change_projection(monkeypatch) -> None:
    harness = _metadata_harness(mounted=True)

    async def run_inline(function, *args):
        return function(*args)

    monkeypatch.setattr(asyncio, "to_thread", run_inline)
    monkeypatch.setattr(tui, "fetch_stream_metadata", lambda _url: None)

    asyncio.run(tui.FluxTunerTUI._fetch_metadata(harness, "https://radio.example/stream"))

    assert harness.current_artist == "Old artist"
    assert harness.current_track == "Old track"
    assert harness._last_metadata_raw == "old raw"
    harness.metadata_widget.update.assert_not_called()


def test_duplicate_raw_metadata_does_not_reproject(monkeypatch) -> None:
    harness = _metadata_harness(mounted=True)
    harness._last_metadata_raw = "Same metadata"

    async def run_inline(function, *args):
        return function(*args)

    monkeypatch.setattr(asyncio, "to_thread", run_inline)
    monkeypatch.setattr(
        tui,
        "fetch_stream_metadata",
        lambda _url: {
            "artist": "New artist",
            "title": "New track",
            "raw": "Same metadata",
        },
    )

    asyncio.run(tui.FluxTunerTUI._fetch_metadata(harness, "https://radio.example/stream"))

    assert harness.current_artist == "Old artist"
    assert harness.current_track == "Old track"
    harness.metadata_widget.update.assert_not_called()


def test_clear_metadata_resets_projection_and_widget() -> None:
    harness = _metadata_harness(mounted=True)

    tui.FluxTunerTUI._clear_metadata(harness)

    assert harness.current_artist == "—"
    assert harness.current_track == "—"
    assert harness._last_metadata_raw is None
    harness.metadata_widget.update.assert_called_once_with("[b]Metadata[/b]\nArtist: —\nTrack: —")


def test_unmount_cancels_active_metadata_task() -> None:
    task = Mock()
    task.done.return_value = False
    harness = SimpleNamespace(
        _metadata_task=task,
        usage_tracker=Mock(),
        player=Mock(),
        cancel_pending_search=Mock(),
    )

    tui.FluxTunerTUI.on_unmount(harness)

    harness.cancel_pending_search.assert_called_once_with()
    task.cancel.assert_called_once_with()
    harness.usage_tracker.stop.assert_called_once_with()
    harness.player.stop.assert_called_once_with()
