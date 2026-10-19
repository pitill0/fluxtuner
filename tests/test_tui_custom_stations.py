from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from textual.app import App
from textual.widgets import Input

from fluxtuner import tui
from fluxtuner.core import custom_stations, db, favorites, profiles


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()
    with db.connect() as conn:
        first = profiles.get_or_create_profile(conn, "First")
        second = profiles.get_or_create_profile(conn, "Second")
        conn.commit()
    return {"first": first, "second": second, "current": first}


def form_app(library):
    screen = tui.CustomStationScreen(
        profile_id=library["first"],
        profile_is_current=lambda: library["current"] == library["first"],
    )

    class FormApp(App):
        def __init__(self):
            super().__init__()
            self.results = []

        def on_mount(self):
            self.push_screen(screen, self.results.append)

    return FormApp(), screen


def saved(profile_id):
    with db.connect() as conn:
        return favorites.list_favorites(conn, profile_id)


def test_custom_station_shortcut_is_available_and_documented():
    assert any(
        binding.key == "ctrl+n" and binding.action == "add_custom_station"
        for binding in tui.FluxTunerTUI.BINDINGS
    )
    assert "Ctrl+N" in tui.SHORTCUT_HELP_TEXT


def test_custom_station_form_opens_without_writing_and_escape_cancels(library):
    async def scenario():
        app, _screen = form_app(library)
        async with app.run_test(size=(80, 30)) as pilot:
            await pilot.pause()
            assert saved(library["first"]) == []
            await pilot.press("escape")
            await pilot.pause()
            assert app.results == [None]
            assert saved(library["first"]) == []

    asyncio.run(scenario())


def test_custom_station_form_saves_to_captured_profile(library):
    async def scenario():
        app, screen = form_app(library)
        async with app.run_test(size=(80, 30)) as pilot:
            screen.query_one("#custom-station-name", Input).value = "Personal radio"
            screen.query_one("#custom-station-url", Input).value = "https://radio.example/live"
            await pilot.click("#custom-station-save")
            await pilot.pause()
            assert app.results == [True]
            stations = saved(library["first"])
            assert len(stations) == 1
            assert favorites.favorite_display_name(stations[0]) == "Personal radio"
            assert stations[0]["url_resolved"] == "https://radio.example/live"
            assert saved(library["second"]) == []

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("name", "url"),
    [
        ("", "https://radio.example/live"),
        ("Personal radio", "file:///tmp/audio.mp3"),
    ],
)
def test_custom_station_form_validation_keeps_inputs(library, name, url):
    async def scenario():
        app, screen = form_app(library)
        async with app.run_test(size=(80, 30)) as pilot:
            screen.query_one("#custom-station-name", Input).value = name
            screen.query_one("#custom-station-url", Input).value = url
            await pilot.click("#custom-station-save")
            await pilot.pause()
            assert app.screen is screen
            assert app.results == []
            assert saved(library["first"]) == []
            assert screen.query_one("#custom-station-name", Input).value == name
            assert screen.query_one("#custom-station-url", Input).value == url

    asyncio.run(scenario())


def test_custom_station_form_rejects_profile_change(library):
    async def scenario():
        app, screen = form_app(library)
        async with app.run_test(size=(80, 30)) as pilot:
            screen.query_one("#custom-station-name", Input).value = "Radio"
            screen.query_one("#custom-station-url", Input).value = "https://radio.example/live"
            library["current"] = library["second"]
            await pilot.click("#custom-station-save")
            await pilot.pause()
            assert app.screen is screen
            assert app.results == []
            assert saved(library["first"]) == []
            assert saved(library["second"]) == []

    asyncio.run(scenario())


def test_custom_station_form_duplicate_preserves_existing_favorite(library):
    with db.connect() as conn:
        custom_stations.add_custom_station(
            conn,
            profile_id=library["first"],
            name="Keep this name",
            url="https://radio.example/live",
        )
        conn.commit()

    async def scenario():
        app, screen = form_app(library)
        async with app.run_test(size=(80, 30)) as pilot:
            screen.query_one("#custom-station-name", Input).value = "Replacement"
            screen.query_one("#custom-station-url", Input).value = "https://radio.example/live"
            await pilot.click("#custom-station-save")
            await pilot.pause()
            assert app.results == [False]
            stations = saved(library["first"])
            assert len(stations) == 1
            assert favorites.favorite_display_name(stations[0]) == "Keep this name"

    asyncio.run(scenario())


@pytest.mark.parametrize("result", [None, True, False])
def test_tui_action_refreshes_favorites_only_after_submission(monkeypatch, result):
    screen = Mock()
    monkeypatch.setattr(tui, "CustomStationScreen", Mock(return_value=screen), raising=False)
    harness = SimpleNamespace(
        cancel_pending_search=Mock(),
        _custom_station_profile_id=Mock(return_value=7),
        push_screen=Mock(),
        show_favorites=AsyncMock(),
        set_status=Mock(),
    )

    tui.FluxTunerTUI.action_add_custom_station(harness)
    harness.cancel_pending_search.assert_called_once_with()
    callback = harness.push_screen.call_args.args[1]
    asyncio.run(callback(result))

    if result is None:
        harness.show_favorites.assert_not_awaited()
    else:
        harness.show_favorites.assert_awaited_once_with()
        harness.set_status.assert_called_with(
            "Station added to favorites." if result else "Station is already in favorites."
        )
