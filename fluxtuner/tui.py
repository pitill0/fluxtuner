from __future__ import annotations

import asyncio
import random
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, Input, Label, ListItem, ListView, Static

from fluxtuner.config import set_config_value
from fluxtuner.core.api import search_stations_by_text
from fluxtuner.core.favorites import add_favorite, load_favorites, remove_favorite
from fluxtuner.core.player import MpvController, PlayerError, ensure_mpv_available
from fluxtuner.theme_runtime import apply_theme_runtime
from fluxtuner.themes import DEFAULT_THEME, get_theme_path, list_themes, theme_exists


class StationListItem(ListItem):
    """List item that stores the station represented by the row."""

    def __init__(self, station: dict[str, Any]) -> None:
        self.station = station
        title = station.get("name", "Unknown station")
        country = station.get("country", "Unknown")
        codec = station.get("codec") or "?"
        bitrate = station.get("bitrate") or "?"
        tags = station.get("tags") or "no tags"
        row = f"{title}  •  {country}  •  {codec} {bitrate}kbps  •  {tags[:80]}"
        super().__init__(Label(row))


class ThemeListItem(ListItem):
    """List item that stores the theme represented by the row."""

    def __init__(self, theme_name: str, active_theme: str) -> None:
        self.theme_name = theme_name
        marker = "●" if theme_name == active_theme else "○"
        super().__init__(Label(f"{marker} {theme_name}"))


class FluxTunerTUI(App[None]):
    """Textual application for FluxTuner."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("/", "focus_search", "Search"),
        ("escape", "focus_station_list", "Results"),
        ("enter", "activate_selected", "Play/apply"),
        ("a", "add_selected", "Add"),
        ("f", "show_favorites", "Favorites"),
        ("d", "remove_selected", "Delete fav"),
        ("r", "play_random_favorite", "Random"),
        ("x", "stop", "Stop"),
        ("t", "show_themes", "Themes"),
        ("p", "preview_theme", "Preview"),
        ("y", "save_theme", "Save theme"),
        ("ctrl+r", "reload_theme", "Reload CSS"),
    ]

    def __init__(self, theme: str | None = None) -> None:
        self.active_theme = theme or DEFAULT_THEME
        self.theme_path = get_theme_path(self.active_theme)
        super().__init__(css_path=str(self.theme_path))
        self.player = MpvController()
        self.selected_station: dict[str, Any] | None = None
        self.selected_theme: str | None = None
        self.playing_station: dict[str, Any] | None = None
        self.view_mode = "search"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Input(placeholder="Search by station name or genre/tag", id="query")
            yield Button("Search", id="search", variant="primary")
            yield Button("Favorites", id="favorites")
            yield Button("Random", id="random")
            yield Button("Themes", id="themes")
            yield Button("Stop", id="stop", variant="error")
        with Horizontal(id="content"):
            yield ListView(id="stations")
            with Vertical(id="side-panel"):
                yield Static("Search", id="mode-title")
                yield Static("[b]Now Playing[/b]\nNothing playing yet.", id="now-playing")
                yield Static("No station selected.", id="details")
                yield Button("Play selected", id="play", variant="success")
                yield Button("Add to favorites", id="add-favorite")
                yield Button("Remove favorite", id="remove-favorite", variant="warning")
        yield Static(
            "Ready. Press '/' to search, 'f' for favorites, 't' for themes, 'r' for random favorite.",
            id="status",
        )
        yield Footer()

    def on_mount(self) -> None:
        try:
            ensure_mpv_available()
        except PlayerError as exc:
            self.notify(str(exc), severity="error", timeout=8)
            self.exit(return_code=1)
            return

        # Apply the selected theme programmatically as well as through startup CSS.
        # This makes theme switching and Ctrl+R reload work in normal app runs,
        # not only under Textual's development CSS watcher.
        try:
            apply_theme_runtime(self, self.active_theme)
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Theme load failed: {exc}", severity="warning", timeout=6)

        self.query_one("#stations", ListView).focus()
        self.update_now_playing()
        self.update_details(None)

    def on_unmount(self) -> None:
        self.player.stop()

    def action_focus_search(self) -> None:
        self.query_one("#query", Input).focus()
        self.set_status("Search focused. Type a query and press Enter. Press Escape to return to the main list.")

    def action_focus_station_list(self) -> None:
        self.query_one("#stations", ListView).focus()
        if self.view_mode == "themes":
            self.set_status("Theme list focused. Use ↑/↓ to preview, Enter or p to apply, y to save, Ctrl+R to reload CSS.")
        else:
            self.set_status("Station list focused. Use Enter to play, f for favorites, a to add, r for random.")

    async def action_show_favorites(self) -> None:
        await self.show_favorites()

    async def action_show_themes(self) -> None:
        await self.show_themes()

    def action_activate_selected(self) -> None:
        if self.view_mode == "themes":
            self.preview_selected_theme()
            return
        self.play_selected_station()

    def action_add_selected(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Use 'p' or Enter to preview/apply a theme, or 'y' to save it as default.")
            return
        self.add_selected_to_favorites()

    async def action_remove_selected(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Theme files are not deleted from FluxTuner. Remove .tcss files manually if needed.")
            return
        await self.remove_selected_from_favorites()

    def action_play_random_favorite(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Random favorite playback is disabled while browsing themes. Press 'f' or search first.")
            return
        self.play_random_favorite()

    def action_stop(self) -> None:
        self.stop_playback()

    def action_preview_theme(self) -> None:
        self.preview_selected_theme()

    def action_save_theme(self) -> None:
        self.save_active_theme()

    def action_reload_theme(self) -> None:
        self.reload_active_theme()

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

    @on(Button.Pressed, "#themes")
    async def themes_from_button(self) -> None:
        await self.show_themes()

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
        await self.remove_selected_from_favorites()

    @on(ListView.Highlighted, "#stations")
    def item_highlighted(self, event: ListView.Highlighted) -> None:
        item = event.item
        if isinstance(item, StationListItem):
            self.selected_station = item.station
            self.selected_theme = None
            self.update_details(item.station)
        elif isinstance(item, ThemeListItem):
            self.selected_theme = item.theme_name
            self.selected_station = None
            self.update_theme_details(item.theme_name)
            self.apply_theme(item.theme_name, save=False, announce=False)

    @on(ListView.Selected, "#stations")
    def item_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, StationListItem):
            self.selected_station = item.station
            self.selected_theme = None
            self.update_details(item.station)
            self.play_selected_station()
        elif isinstance(item, ThemeListItem):
            self.selected_theme = item.theme_name
            self.preview_selected_theme()

    async def search(self, query: str) -> None:
        query = query.strip()
        if not query:
            self.set_status("Type a station name or genre/tag first.")
            return

        self.view_mode = "search"
        self.update_mode_title("Search results")
        self.set_status(f"Searching: {query} ...")
        list_view = self.query_one("#stations", ListView)
        await list_view.clear()
        self.selected_station = None
        self.selected_theme = None
        self.update_details(None)

        try:
            stations = await asyncio.to_thread(search_stations_by_text, query, 50)
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Search failed: {exc}")
            self.notify(f"Search failed: {exc}", severity="error")
            return

        await self.populate_station_list(stations)
        self.query_one("#stations", ListView).focus()
        self.set_status(f"Found {len(stations)} station(s) for: {query}")

    async def show_favorites(self) -> None:
        self.view_mode = "favorites"
        self.update_mode_title("Favorites")
        favorites = sorted(load_favorites(), key=lambda item: item.get("name", "").lower())
        list_view = self.query_one("#stations", ListView)
        await list_view.clear()
        self.selected_station = None
        self.selected_theme = None
        self.update_details(None)
        await self.populate_station_list(favorites)
        self.query_one("#stations", ListView).focus()
        self.set_status(f"Loaded {len(favorites)} favorite station(s).")

    async def show_themes(self) -> None:
        self.view_mode = "themes"
        self.update_mode_title("Themes")
        list_view = self.query_one("#stations", ListView)
        await list_view.clear()
        self.selected_station = None
        themes = list_themes()

        for theme_name in themes:
            await list_view.append(ThemeListItem(theme_name, self.active_theme))

        list_view.index = 0
        if themes:
            self.selected_theme = themes[0]
            self.update_theme_details(themes[0])
        else:
            self.selected_theme = None
            self.query_one("#details", Static).update("[b]Themes[/b]\nNo themes found.")

        list_view.focus()
        self.set_status("Theme selector. Highlight previews automatically. Press Enter/p to apply, y to save, Ctrl+R to reload CSS.")

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
        if self.view_mode == "themes":
            self.preview_selected_theme()
            return

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

        self.playing_station = self.selected_station
        self.update_now_playing()
        self.set_status(f"Playing: {self.selected_station['name']}")

    def stop_playback(self) -> None:
        self.player.stop()
        self.playing_station = None
        self.update_now_playing()
        self.set_status("Playback stopped.")

    def add_selected_to_favorites(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Themes mode: use Enter/p to apply, y to save as default.")
            return
        if not self.selected_station:
            self.set_status("No station selected.")
            return
        add_favorite(self.selected_station)
        self.set_status(f"Saved favorite: {self.selected_station['name']}")

    async def remove_selected_from_favorites(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Themes cannot be removed from the app UI.")
            return
        if not self.selected_station:
            self.set_status("No station selected.")
            return

        remove_favorite(self.selected_station["url"])
        self.set_status(f"Removed favorite: {self.selected_station['name']}")

        if self.view_mode == "favorites":
            await self.show_favorites()

    def play_random_favorite(self) -> None:
        favorites = load_favorites()
        if not favorites:
            self.set_status("No favorites yet.")
            return
        self.selected_station = random.choice(favorites)
        self.selected_theme = None
        self.update_details(self.selected_station)
        self.play_selected_station()

    def preview_selected_theme(self) -> None:
        if not self.selected_theme:
            self.set_status("No theme selected.")
            return
        self.apply_theme(self.selected_theme, save=False, announce=True)

    def save_active_theme(self) -> None:
        set_config_value("theme", self.active_theme)
        self.set_status(f"Saved default theme: {self.active_theme}")
        self.notify(f"Saved default theme: {self.active_theme}", severity="information")

    def reload_active_theme(self) -> None:
        self.apply_theme(self.active_theme, save=False, announce=True, force_reload=True)

    def apply_theme(self, theme_name: str, save: bool = False, announce: bool = True, force_reload: bool = False) -> None:
        if not theme_exists(theme_name):
            self.set_status(f"Theme not found: {theme_name}")
            return

        self.active_theme = theme_name
        self.theme_path = get_theme_path(theme_name)

        try:
            apply_theme_runtime(self, theme_name)
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Theme reload failed: {exc}")
            self.notify(f"Theme reload failed: {exc}", severity="error")
            return

        if save:
            set_config_value("theme", theme_name)

        if announce:
            suffix = "saved" if save else "previewed"
            if force_reload:
                suffix = "reloaded"
            self.set_status(f"Theme {suffix}: {theme_name}")

    def update_details(self, station: dict[str, Any] | None) -> None:
        details = self.query_one("#details", Static)
        if not station:
            details.update("[b]Selected Station[/b]\nNo station selected.")
            return

        details.update(
            "[b]Selected Station[/b]\n\n"
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

    def update_theme_details(self, theme_name: str) -> None:
        path = get_theme_path(theme_name)
        status = "active" if theme_name == self.active_theme else "available"
        self.query_one("#details", Static).update(
            "[b]Theme Preview[/b]\n\n"
            f"[b]{theme_name}[/b]\nStatus: {status}\nFile: {Path(path).name}\n\n"
            "Highlight previews automatically.\n"
            "Enter / p: apply preview\n"
            "y: save as default\n"
            "Ctrl+R: reload current theme file"
        )

    def update_now_playing(self) -> None:
        now_playing = self.query_one("#now-playing", Static)
        if not self.playing_station or not self.player.is_playing():
            now_playing.update("[b]Now Playing[/b]\nNothing playing yet.")
            return

        station = self.playing_station
        now_playing.update(
            "[b]Now Playing[/b]\n"
            "▶ {}\n"
            "{} • {} kbps • {}".format(
                station.get("name", "Unknown station"),
                station.get("country", "Unknown"),
                station.get("bitrate") or "?",
                station.get("codec") or "?",
            )
        )

    def update_mode_title(self, title: str) -> None:
        self.query_one("#mode-title", Static).update(title)

    def set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)


def run_tui(theme: str | None = None) -> None:
    FluxTunerTUI(theme=theme).run()
