from __future__ import annotations

import asyncio
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from fluxtuner import tui


def _selection_harness(*, view_mode: str = "search") -> SimpleNamespace:
    harness = SimpleNamespace(
        view_mode=view_mode,
        selected_station={"name": "Old station"},
        selected_theme="old-theme",
        selected_tag="old-tag",
        selected_playlist="Old playlist",
        active_playlist_name="Old playlist",
        favorite_tag_filter="old-filter",
        profile_name="default",
        active_theme="default",
        table_items={},
        table_key_counter=0,
        restore_active_theme_if_previewing=Mock(),
        update_mode_title=Mock(),
        update_details=Mock(),
        update_theme_details=Mock(),
        update_playlist_details=Mock(),
        update_persistent_playlist_details=Mock(),
        update_play_button=Mock(),
        preview_theme=Mock(),
        set_status=Mock(),
        notify=Mock(),
        populate_station_list=AsyncMock(),
        reset_playlist_table=Mock(),
        next_table_key=Mock(),
        add_table_payload=Mock(),
        selected_payload_from_event=Mock(),
    )
    for method_name in (
        "_clear_view_selection",
        "_set_view_mode",
        "_clear_station_view_selection",
        "_enter_playlists_view",
        "_enter_playlist_stations_view",
        "_clear_playlist_station_selection",
        "_enter_themes_view",
        "_clear_theme_selection",
        "_select_station",
        "_select_theme",
        "_select_playlist",
        "_select_tag",
    ):
        method = getattr(tui.FluxTunerTUI, method_name)
        setattr(harness, method_name, MethodType(method, harness))
    return harness


def _table() -> Mock:
    table = Mock()
    table.add_row = Mock()
    table.move_cursor = Mock()
    table.focus = Mock()
    table.clear = Mock()
    return table


@pytest.mark.parametrize(
    ("method_name", "expected_mode"),
    [
        ("show_favorites", "favorites"),
        ("show_history", "history"),
    ],
)
def test_station_list_views_clear_incompatible_selection(
    monkeypatch,
    method_name: str,
    expected_mode: str,
) -> None:
    harness = _selection_harness(view_mode="playlist_stations")
    table = _table()
    harness.query_one = Mock(return_value=table)

    monkeypatch.setattr(tui, "load_favorites", lambda **_kwargs: [])
    monkeypatch.setattr(tui, "all_favorite_tags", lambda **_kwargs: [])
    monkeypatch.setattr(tui, "load_history", lambda **_kwargs: [])

    method = getattr(tui.FluxTunerTUI, method_name)
    asyncio.run(method(harness))

    assert harness.view_mode == expected_mode
    assert harness.selected_station is None
    assert harness.selected_theme is None
    assert harness.selected_tag is None
    assert harness.selected_playlist is None
    assert harness.active_playlist_name is None
    harness.update_details.assert_called_once_with(None)


def test_favorites_view_stores_requested_tag_filter(monkeypatch) -> None:
    harness = _selection_harness()
    table = _table()
    harness.query_one = Mock(return_value=table)

    monkeypatch.setattr(tui, "filter_favorites_by_tag", lambda *_args, **_kwargs: [])

    asyncio.run(tui.FluxTunerTUI.show_favorites(harness, tag_filter="ambient"))

    assert harness.view_mode == "favorites"
    assert harness.favorite_tag_filter == "ambient"
    harness.update_mode_title.assert_called_once_with("Favorites · tag: ambient")


def test_playlists_view_clears_station_context_and_selects_persistent_playlist(
    monkeypatch,
) -> None:
    harness = _selection_harness(view_mode="playlist_stations")
    table = _table()
    harness.reset_playlist_table.return_value = table
    harness.next_table_key.return_value = "playlist-1"

    def add_payload(key, kind, payload):
        harness.table_items[key] = (kind, payload)

    harness.add_table_payload.side_effect = add_payload

    monkeypatch.setattr(tui, "playlist_counts", lambda **_kwargs: [("Road trip", 3)])
    monkeypatch.setattr(tui, "get_tag_counts", lambda **_kwargs: [])

    asyncio.run(tui.FluxTunerTUI.show_playlists(harness))

    assert harness.view_mode == "playlists"
    assert harness.active_playlist_name is None
    assert harness.selected_station is None
    assert harness.selected_theme is None
    assert harness.selected_tag is None
    assert harness.selected_playlist == "Road trip"
    harness.update_persistent_playlist_details.assert_called_once_with("Road trip", 3)


def test_playlists_view_selects_dynamic_tag_exclusively(monkeypatch) -> None:
    harness = _selection_harness()
    table = _table()
    harness.reset_playlist_table.return_value = table
    harness.next_table_key.return_value = "tag-1"

    def add_payload(key, kind, payload):
        harness.table_items[key] = (kind, payload)

    harness.add_table_payload.side_effect = add_payload

    monkeypatch.setattr(tui, "playlist_counts", lambda **_kwargs: [])
    monkeypatch.setattr(tui, "get_tag_counts", lambda **_kwargs: [("jazz", 4)])

    asyncio.run(tui.FluxTunerTUI.show_playlists(harness))

    assert harness.selected_tag == "jazz"
    assert harness.selected_playlist is None
    assert harness.selected_station is None
    assert harness.selected_theme is None
    harness.update_playlist_details.assert_called_once_with("jazz", 4)


def test_themes_view_clears_station_and_tag_context(monkeypatch) -> None:
    harness = _selection_harness()
    table = _table()
    harness.reset_playlist_table.return_value = table
    harness.next_table_key.return_value = "theme-1"

    def add_payload(key, kind, payload):
        harness.table_items[key] = (kind, payload)

    harness.add_table_payload.side_effect = add_payload

    monkeypatch.setattr(tui, "list_themes", lambda: ["default"])
    monkeypatch.setattr(tui, "get_theme_path", lambda name: f"/themes/{name}.tcss")

    asyncio.run(tui.FluxTunerTUI.show_themes(harness))

    assert harness.view_mode == "themes"
    assert harness.selected_station is None
    assert harness.selected_tag is None
    assert harness.selected_theme == "default"
    harness.update_theme_details.assert_called_once_with("default")


@pytest.mark.parametrize(
    ("kind", "payload"),
    [
        ("theme", "midnight"),
        ("playlist", {"name": "Focus", "count": 2}),
        ("tag", {"tag": "ambient", "count": 5}),
    ],
)
def test_row_highlight_keeps_only_payload_compatible_selection(kind, payload) -> None:
    harness = _selection_harness()
    harness.selected_payload_from_event.return_value = (kind, payload)

    tui.FluxTunerTUI.item_highlighted(harness, SimpleNamespace(row_key="row"))

    if kind == "theme":
        assert harness.selected_theme == "midnight"
        assert harness.selected_station is None
        assert harness.selected_tag is None
        assert harness.selected_playlist is None
    elif kind == "playlist":
        assert harness.selected_playlist == "Focus"
        assert harness.selected_station is None
        assert harness.selected_theme is None
        assert harness.selected_tag is None
    else:
        assert harness.selected_tag == "ambient"
        assert harness.selected_station is None
        assert harness.selected_theme is None
        assert harness.selected_playlist is None


def test_station_highlight_clears_playlist_outside_playlist_station_view() -> None:
    station = {"name": "Flux FM"}
    harness = _selection_harness(view_mode="favorites")
    harness.selected_payload_from_event.return_value = ("station", station)

    tui.FluxTunerTUI.item_highlighted(harness, SimpleNamespace(row_key="row"))

    assert harness.selected_station is station
    assert harness.selected_theme is None
    assert harness.selected_tag is None
    assert harness.selected_playlist is None


def test_station_highlight_preserves_parent_playlist_in_playlist_station_view() -> None:
    station = {"name": "Flux FM"}
    harness = _selection_harness(view_mode="playlist_stations")
    harness.selected_playlist = "Road trip"
    harness.selected_payload_from_event.return_value = ("station", station)

    tui.FluxTunerTUI.item_highlighted(harness, SimpleNamespace(row_key="row"))

    assert harness.selected_station is station
    assert harness.selected_playlist == "Road trip"
    assert harness.selected_theme is None
    assert harness.selected_tag is None


def test_search_view_clears_incompatible_selection(monkeypatch) -> None:
    harness = _selection_harness(view_mode="playlist_stations")
    query_input = SimpleNamespace(value="Flux")
    country_input = SimpleNamespace(value="")
    bitrate_input = SimpleNamespace(value="")
    table = _table()

    widgets = {
        "#query": query_input,
        "#country-filter": country_input,
        "#bitrate-filter": bitrate_input,
        "#stations": table,
    }
    harness.query_one = Mock(side_effect=lambda selector, *_args: widgets[selector])
    harness.player_backend_name = "mpv"
    harness._search_task = Mock()
    harness.search_service = Mock()
    harness.search_service.search.return_value = SimpleNamespace(
        stations=[],
        unsupported_count=0,
    )

    async def run_inline(function, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", run_inline)

    asyncio.run(tui.FluxTunerTUI.search(harness, "Flux"))

    assert harness.view_mode == "search"
    assert harness._search_task is None
    assert harness.selected_station is None
    assert harness.selected_theme is None
    assert harness.selected_tag is None
    assert harness.selected_playlist is None
    assert harness.active_playlist_name is None
    harness.update_details.assert_called_once_with(None)
    harness.populate_station_list.assert_awaited_once_with([])
