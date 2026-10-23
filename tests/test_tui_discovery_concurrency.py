"""Concurrency regressions for TUI discovery-source searches."""

import asyncio
from types import MethodType, SimpleNamespace
from unittest.mock import AsyncMock, Mock

from fluxtuner import tui


def make_app(source="radio-browser"):
    values = {
        "#query": SimpleNamespace(value="rock"),
        "#country-filter": SimpleNamespace(value=""),
        "#bitrate-filter": SimpleNamespace(value=""),
        "#source-filter": SimpleNamespace(value=source),
        "#stations": SimpleNamespace(clear=Mock(), focus=Mock()),
    }
    playing = {"name": "Already playing"}
    app = SimpleNamespace(
        view_mode="search",
        _search_task=None,
        _search_generation=0,
        profile_name="default",
        player_capabilities=None,
        player_backend_name="mpv",
        playing_station=playing,
        player=SimpleNamespace(stop=Mock()),
        restore_active_theme_if_previewing=Mock(),
        update_mode_title=Mock(),
        update_details=Mock(),
        set_status=Mock(),
        notify=Mock(),
        populate_station_list=AsyncMock(),
        selected_station={"name": "Old result"},
        selected_theme=None,
        selected_tag=None,
        selected_playlist=None,
        active_playlist_name=None,
        search_service=SimpleNamespace(search=Mock()),
        query_one=Mock(side_effect=lambda selector, *_args: values[selector]),
    )
    for name in (
        "cancel_pending_search",
        "_set_view_mode",
        "_selected_discovery_source",
        "_clear_view_selection",
        "_clear_station_view_selection",
    ):
        setattr(app, name, MethodType(getattr(tui.FluxTunerTUI, name), app))
    return app, values


def result(name):
    return SimpleNamespace(stations=[{"name": name}], unsupported_count=0)


def test_later_search_wins_even_when_previous_finishes_last(monkeypatch):
    async def scenario():
        app, _widgets = make_app()
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def fake_to_thread(_function, request, **_kwargs):
            if request.query == "old":
                first_started.set()
                await release_first.wait()
                return result("Old radio")
            return result("New radio")

        monkeypatch.setattr(tui.asyncio, "to_thread", fake_to_thread)

        old_task = asyncio.create_task(tui.FluxTunerTUI.search(app, "old"))
        await first_started.wait()
        new_task = asyncio.create_task(tui.FluxTunerTUI.search(app, "new"))
        await new_task
        release_first.set()
        await old_task
        await asyncio.sleep(0)

        assert app.populate_station_list.await_count == 1
        app.populate_station_list.assert_awaited_once_with([{"name": "New radio"}])
        assert app.view_mode == "search"
        assert app.playing_station == {"name": "Already playing"}
        app.player.stop.assert_not_called()

    asyncio.run(scenario())


def test_stale_search_failure_does_not_replace_newer_status(monkeypatch):
    async def scenario():
        app, _widgets = make_app()
        first_started = asyncio.Event()
        release_first = asyncio.Event()

        async def fake_to_thread(_function, request, **_kwargs):
            if request.query == "old":
                first_started.set()
                await release_first.wait()
                raise RuntimeError("Old backend failure")
            return result("New radio")

        monkeypatch.setattr(tui.asyncio, "to_thread", fake_to_thread)

        old_task = asyncio.create_task(tui.FluxTunerTUI.search(app, "old"))
        await first_started.wait()
        new_task = asyncio.create_task(tui.FluxTunerTUI.search(app, "new"))
        await new_task
        last_status = app.set_status.call_args
        release_first.set()
        await old_task

        assert app.set_status.call_args == last_status
        app.notify.assert_not_called()
        app.populate_station_list.assert_awaited_once_with([{"name": "New radio"}])

    asyncio.run(scenario())


def test_source_change_invalidates_search_without_cancelling_event_task(monkeypatch):
    async def scenario():
        app, widgets = make_app()
        started = asyncio.Event()
        release = asyncio.Event()

        async def fake_to_thread(_function, _request, **_kwargs):
            started.set()
            await release.wait()
            return result("Obsolete radio")

        monkeypatch.setattr(tui.asyncio, "to_thread", fake_to_thread)

        task = asyncio.create_task(tui.FluxTunerTUI.search(app, "rock"))
        await started.wait()

        generation = app._search_generation
        widgets["#source-filter"].value = "local"
        tui.FluxTunerTUI.discovery_source_changed(app, SimpleNamespace())

        assert app._search_generation > generation
        assert task.cancelling() == 0
        assert app.view_mode == "search"
        assert app.selected_station is None

        release.set()
        await task

        app.populate_station_list.assert_not_awaited()
        app.player.stop.assert_not_called()
        assert app.playing_station == {"name": "Already playing"}

    asyncio.run(scenario())


def test_navigation_invalidates_search_without_cancelling_event_task(monkeypatch):
    async def scenario():
        app, _widgets = make_app()
        started = asyncio.Event()
        release = asyncio.Event()

        async def fake_to_thread(_function, _request, **_kwargs):
            started.set()
            await release.wait()
            return result("Obsolete radio")

        monkeypatch.setattr(tui.asyncio, "to_thread", fake_to_thread)

        task = asyncio.create_task(tui.FluxTunerTUI.search(app, "rock"))
        await started.wait()

        generation = app._search_generation
        app._set_view_mode("favorites")

        assert app._search_generation > generation
        assert task.cancelling() == 0

        release.set()
        await task

        assert app.view_mode == "favorites"
        app.populate_station_list.assert_not_awaited()
        assert app.playing_station == {"name": "Already playing"}
        app.player.stop.assert_not_called()

    asyncio.run(scenario())
