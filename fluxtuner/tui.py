from __future__ import annotations

import asyncio
import random
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from fluxtuner.core.api import search_stations_by_text
from fluxtuner.core.favorites import add_favorite, load_favorites, remove_favorite
from fluxtuner.core.player import MpvController, PlayerError, ensure_mpv_available


class StationListItem(ListItem):
    """List item that stores the station represented by the row."""

    def __init__(self, station: dict[str, Any]) -> None:
        self.station = station
        title = station.get("name", "Unknown station")
        country = station.get("country", "Unknown")
        codec = station.get("codec") or "?"
        bitrate = station.get("bitrate") or "?"
        tags = station.get("tags") or "no tags"
        super().__init__(Label(f"{title}  •  {country}  •  {codec} {bitrate}kbps  •  {tags[:70]}"))


class FluxTunerTUI(App[None]):
    """Textual application for FluxTuner."""

    CSS = """
    Screen {
        layout: vertical;
    }

    #toolbar {
        height: 3;
        padding: 0 1;
    }

    #query {
        width: 1fr;
    }

    #content {
        height: 1fr;
    }

    #stations {
        width: 2fr;
        border: solid $primary;
    }

    #side-panel {
        width: 1fr;
        min-width: 34;
        border: solid $secondary;
        padding: 1;
    }

    #details {
        height: 1fr;
        margin-bottom: 1;
    }

    #status {
        height: 3;
        padding: 0 1;
    }

    Button {
        margin-left: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "focus_search", "Search"),
        ("enter", "play_selected", "Play"),
        ("a", "add_selected", "Add favorite"),
        ("f", "show_favorites", "Favorites"),
        ("r", "play_random_favorite", "Random"),
        ("x", "stop", "Stop"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.player = MpvController()
        self.selected_station: dict[str, Any] | None = None
        self.view_mode = "search"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Input(placeholder="Search by station name or genre/tag", id="query")
            yield Button("Search", id="search", variant="primary")
            yield Button("Favorites", id="favorites")
            yield Button("Random", id="random")
            yield Button("Stop", id="stop", variant="error")
        with Horizontal(id="content"):
            yield ListView(id="stations")
            with Vertical(id="side-panel"):
                yield Static("No station selected.", id="details")
                yield Button("Play selected", id="play", variant="success")
                yield Button("Add to favorites", id="add-favorite")
                yield Button("Remove favorite", id="remove-favorite", variant="warning")
        yield Static("Ready. Press 's' to search, 'f' for favorites, 'r' for random favorite.", id="status")
        yield Footer()

    def on_mount(self) -> None:
        try:
            ensure_mpv_available()
        except PlayerError as exc:
            self.notify(str(exc), severity="error", timeout=8)
            self.exit(return_code=1)
            return

        self.query_one("#query", Input).focus()

    def on_unmount(self) -> None:
        self.player.stop()

    def action_focus_search(self) -> None:
        self.query_one("#query", Input).focus()

    async def action_show_favorites(self) -> None:
        await self.show_favorites()

    def action_play_selected(self) -> None:
        self.play_selected_station()

    def action_add_selected(self) -> None:
        self.add_selected_to_favorites()

    def action_play_random_favorite(self) -> None:
        self.play_random_favorite()

    def action_stop(self) -> None:
        self.stop_playback()

    @on(Input.Submitted, "#query")
    async def search_from_input(self, event: Input.Submitted) -> None:
        await self.search(event.value)

    @on(Button.Pressed, "#search")
    async def search_from_button(self) -> None:
        query = self.query_one("#query", Input).value
        await self.search(query)

    @on(Button.Pressed, "#favorites")
    async def favorites_from_button(self) -> None:
        await self.show_favorites()

    @on(Button.Pressed, "#random")
    def random_from_button(self) -> None:
        self.play_random_favorite()

    @on(Button.Pressed, "#stop")
    def stop_from_button(self) -> None:
        self.stop_playback()

    @on(Button.Pressed, "#play")
    def play_from_button(self) -> None:
        self.play_selected_station()

    @on(Button.Pressed, "#add-favorite")
    def add_favorite_from_button(self) -> None:
        self.add_selected_to_favorites()

    @on(Button.Pressed, "#remove-favorite")
    async def remove_favorite_from_button(self) -> None:
        if not self.selected_station:
            self.set_status("No station selected.")
            return
        remove_favorite(self.selected_station["url"])
        self.set_status(f"Removed favorite: {self.selected_station['name']}")
        if self.view_mode == "favorites":
            await self.show_favorites()

    @on(ListView.Highlighted, "#stations")
    def station_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, StationListItem):
            self.selected_station = item.station
            self.update_details(item.station)

    @on(ListView.Selected, "#stations")
    def station_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, StationListItem):
            self.selected_station = item.station
            self.update_details(item.station)
            self.play_selected_station()

    async def search(self, query: str) -> None:
        query = query.strip()
        if not query:
            self.set_status("Type a station name or genre/tag first.")
            return

        self.view_mode = "search"
        self.set_status(f"Searching: {query} ...")
        list_view = self.query_one("#stations", ListView)
        await list_view.clear()
        self.selected_station = None
        self.update_details(None)

        try:
            stations = await asyncio.to_thread(search_stations_by_text, query, 50)
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Search failed: {exc}")
            self.notify(f"Search failed: {exc}", severity="error")
            return

        await self.populate_station_list(stations)
        self.set_status(f"Found {len(stations)} station(s) for: {query}")

    async def show_favorites(self) -> None:
        self.view_mode = "favorites"
        favorites = load_favorites()
        list_view = self.query_one("#stations", ListView)
        await list_view.clear()
        self.selected_station = None
        self.update_details(None)
        await self.populate_station_list(favorites)
        self.set_status(f"Loaded {len(favorites)} favorite station(s).")

    async def populate_station_list(self, stations: list[dict[str, Any]]) -> None:
        list_view = self.query_one("#stations", ListView)
        if not stations:
            await list_view.append(ListItem(Label("No stations available.")))
            return

        for station in stations:
            await list_view.append(StationListItem(station))

        list_view.index = 0
        first = list_view.children[0]
        if isinstance(first, StationListItem):
            self.selected_station = first.station
            self.update_details(first.station)

    def play_selected_station(self) -> None:
        if not self.selected_station:
            self.set_status("No station selected.")
            return

        url = self.selected_station.get("url")
        if not url:
            self.set_status("Selected station has no playable URL.")
            return

        try:
            self.player.play(url)
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Playback failed: {exc}")
            self.notify(f"Playback failed: {exc}", severity="error")
            return

        self.set_status(f"Playing: {self.selected_station['name']}")

    def stop_playback(self) -> None:
        self.player.stop()
        self.set_status("Playback stopped.")

    def add_selected_to_favorites(self) -> None:
        if not self.selected_station:
            self.set_status("No station selected.")
            return
        add_favorite(self.selected_station)
        self.set_status(f"Saved favorite: {self.selected_station['name']}")

    def play_random_favorite(self) -> None:
        favorites = load_favorites()
        if not favorites:
            self.set_status("No favorites yet.")
            return
        self.selected_station = random.choice(favorites)
        self.update_details(self.selected_station)
        self.play_selected_station()

    def update_details(self, station: dict[str, Any] | None) -> None:
        details = self.query_one("#details", Static)
        if not station:
            details.update("No station selected.")
            return

        details.update(
            "[b]{}[/b]\n\nCountry: {}\nCodec: {}\nBitrate: {} kbps\nLanguage: {}\nTags: {}\nHomepage: {}".format(
                station.get("name", "Unknown station"),
                station.get("country", "Unknown"),
                station.get("codec") or "?",
                station.get("bitrate") or "?",
                station.get("language") or "?",
                station.get("tags") or "?",
                station.get("homepage") or "?",
            )
        )

    def set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)


def run_tui() -> None:
    FluxTunerTUI().run()
