"""Real Textual event coverage for discovery-source selection."""

import asyncio
from pathlib import Path

from textual.app import App
from textual.widgets import Select

from fluxtuner.tui import FluxTunerTUI


class DiscoveryEventProbe(App[None]):
    CSS = FluxTunerTUI.CSS
    discovery_source_changed = FluxTunerTUI.discovery_source_changed

    def __init__(self):
        css_path = Path(__file__).resolve().parents[1] / "fluxtuner/themes/default.tcss"
        super().__init__(css_path=str(css_path))
        self._search_generation = 0
        self._search_task = None
        self.view_mode = "favorites"
        self.selected_station = {"name": "Previous result"}
        self.playing_station = {"name": "Playing station"}
        self.cleared = 0
        self.messages = []

    def compose(self):
        yield from FluxTunerTUI.compose(self)

    def cancel_pending_search(self):
        self._search_generation += 1
        self._search_task = None

    def _set_view_mode(self, mode):
        self.view_mode = mode

    def _clear_station_view_selection(self):
        self.selected_station = None
        self.cleared += 1

    def update_mode_title(self, title):
        self.messages.append(("title", title))

    def set_status(self, message):
        self.messages.append(("status", message))


def test_real_textual_select_events_invalidate_without_stopping_playback():
    async def scenario():
        app = DiscoveryEventProbe()

        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            selector = app.query_one("#source-filter", Select)
            assert selector.value == "radio-browser"

            for source in ("local", "all", "radio-browser"):
                app.selected_station = {"name": "Previous result"}
                previous_generation = app._search_generation
                previous_cleared = app.cleared

                selector.value = source
                await pilot.pause()

                assert selector.value == source
                assert app._search_generation > previous_generation
                assert app.cleared > previous_cleared
                assert app.selected_station is None
                assert app.view_mode == "search"
                assert app.playing_station == {"name": "Playing station"}

            assert any(
                kind == "status" and "Discovery source changed" in message
                for kind, message in app.messages
            )

    asyncio.run(scenario())
