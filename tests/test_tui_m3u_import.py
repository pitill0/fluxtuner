from __future__ import annotations

import asyncio
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from textual.app import App
from textual.widgets import Button, Input, Select, TextArea

from fluxtuner import tui
from fluxtuner import tui_m3u_import as importer
from fluxtuner.core import custom_stations, db, favorites, profiles
from fluxtuner.core.m3u_import import MAX_FILE_BYTES, M3UImportResult


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()
    with db.connect() as conn:
        first = profiles.get_or_create_profile(conn, "First")
        second = profiles.get_or_create_profile(conn, "Second")
        conn.commit()
    path = tmp_path / "Collection.m3u8"
    path.write_text(
        "#EXTM3U\n"
        "#EXTINF:-1,Rádio personal\nhttps://radio.example/live\n"
        "#EXTINF:-1,Other\nhttps://other.example/live\n"
        "#EXTINF:-1,Duplicate\nhttps://radio.example/live\n"
        "file:///tmp/no-importar.mp3\n",
        encoding="utf-8-sig",
    )
    return {"first": first, "second": second, "current": first, "path": path}


def snapshot():
    with db.connect() as conn:
        return tuple(
            tuple(tuple(row) for row in conn.execute(f"SELECT * FROM {table}"))
            for table in ("stations", "favorites", "playlists", "playlist_stations")
        )


def form_app(library):
    screen = importer.M3UImportScreen(
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


async def preview(app, screen, pilot, library):
    screen.query_one("#m3u-path", Input).value = str(library["path"])
    await pilot.pause()
    screen.preview_file()
    await app.workers.wait_for_complete()
    await pilot.pause()


async def save(app, screen, pilot):
    screen.save_import()
    await app.workers.wait_for_complete()
    await pilot.pause()


def test_import_shortcut_is_available_and_documented():
    assert any(
        binding.key == "ctrl+o" and binding.action == "import_stations"
        for binding in tui.FluxTunerTUI.BINDINGS
    )
    assert "Ctrl+O" in tui.SHORTCUT_HELP_TEXT


@pytest.mark.parametrize("with_preview", [False, True])
def test_escape_cancels_without_library_writes(library, with_preview):
    async def scenario():
        before = snapshot()
        app, screen = form_app(library)
        async with app.run_test(size=(100, 44)) as pilot:
            if with_preview:
                await preview(app, screen, pilot, library)
                assert not screen.query_one("#m3u-save", Button).disabled
            await pilot.press("escape")
            await pilot.pause()
            assert app.results == [None]
            assert snapshot() == before

    asyncio.run(scenario())


def test_preview_uses_plain_text_and_does_not_save(library):
    async def scenario():
        before = snapshot()
        app, screen = form_app(library)
        async with app.run_test(size=(100, 44)) as pilot:
            await preview(app, screen, pilot, library)
            text = screen.query_one("#m3u-preview", TextArea).text
            assert "Rádio personal" in text
            assert "https://radio.example/live" in text
            assert snapshot() == before
            assert app.results == []

    asyncio.run(scenario())


def test_import_creates_playlist_in_captured_profile(library):
    async def scenario():
        app, screen = form_app(library)
        async with app.run_test(size=(100, 44)) as pilot:
            await preview(app, screen, pilot, library)
            screen.query_one("#m3u-name", Input).value = "Imported"
            await save(app, screen, pilot)
            assert len(app.results) == 1
            assert app.results[0].name == "Imported"
            assert app.results[0].result.added_favorites == 2
            assert app.results[0].result.added_to_playlist == 2
        with db.connect() as conn:
            assert len(favorites.list_favorites(conn, library["first"])) == 2
            assert favorites.list_favorites(conn, library["second"]) == []
            assert db.list_playlists(conn, profile_id=library["second"]) == []
            playlist = db.get_playlist_record(conn, "Imported", profile_id=library["first"])
            assert len(playlist["station_keys"]) == 2

    asyncio.run(scenario())


def test_existing_playlist_and_reimport_preserve_personal_metadata(library):
    with db.connect() as conn:
        custom_stations.add_custom_station(
            conn,
            profile_id=library["first"],
            name="Directory name",
            url="https://radio.example/live",
        )
        favorites.update_favorite_record(
            conn,
            "https://radio.example/live",
            custom_name="My name",
            favorite_tags=["Keep"],
            profile_id=library["first"],
        )
        db.create_playlist_record(conn, "Morning", profile_id=library["first"])
        db.create_playlist_record(conn, "Hidden", profile_id=library["second"])
        conn.commit()

    async def scenario():
        for expected_added in (2, 0):
            app, screen = form_app(library)
            async with app.run_test(size=(100, 44)) as pilot:
                await preview(app, screen, pilot, library)
                assert screen._names == ("Morning",)
                screen.query_one("#m3u-destination", Select).value = "0"
                await pilot.pause()
                await save(app, screen, pilot)
                assert app.results[0].result.added_to_playlist == expected_added
        with db.connect() as conn:
            stations = favorites.list_favorites(conn, library["first"])
            station = next(s for s in stations if s["url_resolved"] == "https://radio.example/live")
            assert station["custom_name"] == "My name"
            assert station["favorite_tags"] == ["Keep"]
            assert len(stations) == 2

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["profile-change", "deleted-playlist", "name-conflict"])
def test_destination_failures_write_nothing_and_keep_dialog_open(library, failure):
    with db.connect() as conn:
        db.create_playlist_record(conn, "Morning", profile_id=library["first"])
        conn.commit()

    async def scenario():
        app, screen = form_app(library)
        async with app.run_test(size=(100, 44)) as pilot:
            await preview(app, screen, pilot, library)
            if failure == "profile-change":
                library["current"] = library["second"]
            elif failure == "deleted-playlist":
                screen.query_one("#m3u-destination", Select).value = "0"
                with db.connect() as conn:
                    db.delete_playlist_record(conn, "Morning", profile_id=library["first"])
                    conn.commit()
            else:
                screen.query_one("#m3u-name", Input).value = "MORNING"
            await pilot.pause()
            before = snapshot()
            await save(app, screen, pilot)
            assert app.screen is screen
            assert app.results == []
            assert snapshot() == before
            assert not screen.query_one("#m3u-save", Button).disabled

    asyncio.run(scenario())


@pytest.mark.parametrize("invalid", ["hls", "empty", "oversized", "missing"])
def test_invalid_files_cannot_enable_import(library, invalid):
    path = library["path"]
    if invalid == "hls":
        path.write_text("#EXTM3U\n#EXT-X-TARGETDURATION:10\nsegment.ts\n")
    elif invalid == "empty":
        path.write_bytes(b"")
    elif invalid == "oversized":
        path.write_bytes(b"x" * (MAX_FILE_BYTES + 1))
    else:
        path.unlink()

    async def scenario():
        before = snapshot()
        app, screen = form_app(library)
        async with app.run_test(size=(100, 44)) as pilot:
            await preview(app, screen, pilot, library)
            assert screen.query_one("#m3u-save", Button).disabled
            assert app.screen is screen
            assert snapshot() == before

    asyncio.run(scenario())


def test_editing_file_path_invalidates_previous_preview(library):
    async def scenario():
        app, screen = form_app(library)
        async with app.run_test(size=(100, 44)) as pilot:
            await preview(app, screen, pilot, library)
            screen.query_one("#m3u-path", Input).value += ".different"
            await pilot.pause()
            assert screen.query_one("#m3u-save", Button).disabled
            before = snapshot()
            screen.save_import()
            assert snapshot() == before
            assert app.results == []

    asyncio.run(scenario())


def test_escape_remains_responsive_while_file_is_reading(library, monkeypatch):
    started = threading.Event()
    release = threading.Event()
    original = importer.load_m3u_file

    def delayed(path):
        started.set()
        assert release.wait(5), "The test did not release the reader"
        return original(path)

    monkeypatch.setattr(importer, "load_m3u_file", delayed)

    async def scenario():
        before = snapshot()
        app, screen = form_app(library)
        try:
            async with app.run_test(size=(80, 24)) as pilot:
                screen.query_one("#m3u-path", Input).value = str(library["path"])
                await pilot.pause()
                screen.preview_file()
                assert await asyncio.to_thread(started.wait, 2)
                await pilot.press("escape")
                await pilot.pause()
                assert app.results == [None]
                assert snapshot() == before
                release.set()
        finally:
            release.set()

    asyncio.run(scenario())


@pytest.mark.parametrize("confirmed", [False, True])
def test_application_opens_destination_only_after_confirmation(monkeypatch, confirmed):
    monkeypatch.setattr(tui, "M3UImportScreen", Mock(), raising=False)
    harness = SimpleNamespace(
        screen=None,
        cancel_pending_search=Mock(),
        _custom_station_profile_id=Mock(return_value=7),
        push_screen=Mock(),
        show_persistent_playlist_stations=AsyncMock(),
        set_status=Mock(),
    )
    tui.FluxTunerTUI.action_import_stations(harness)
    harness.cancel_pending_search.assert_called_once_with()
    callback = harness.push_screen.call_args.args[1]
    outcome = (
        importer.M3UImportOutcome("Imported", M3UImportResult(2, 0, 2, 0)) if confirmed else None
    )
    asyncio.run(callback(outcome))
    if confirmed:
        harness.show_persistent_playlist_stations.assert_awaited_once_with("Imported")
    else:
        harness.show_persistent_playlist_stations.assert_not_awaited()
