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
from fluxtuner.core.api import search_stations_filtered
from fluxtuner.core.favorites import add_favorite, load_favorites, remove_favorite
from fluxtuner.core.history import add_history, load_history
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
        ("h", "show_history", "History"),
        ("d", "remove_selected", "Delete fav"),
        ("r", "play_random_favorite", "Random"),
        ("space", "toggle_pause", "Pause"),
        ("plus", "volume_up", "Vol+"),
        ("minus", "volume_down", "Vol-"),
        ("m", "toggle_mute", "Mute"),
        ("x", "stop", "Stop"),
        ("t", "show_themes", "Themes"),
        ("p", "preview_theme", "Preview"),
        ("y", "save_theme", "Save theme"),
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
        self._search_task = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Input(placeholder="Search by station name or genre/tag", id="query")
            yield Button("Search", id="search", variant="primary", classes="toolbar-button")
            yield Button("Favs", id="favorites", classes="toolbar-button")
            yield Button("History", id="history", classes="toolbar-button")
            yield Button("Random", id="random", classes="toolbar-button")
            yield Button("Themes", id="themes", classes="toolbar-button")
            yield Button("Stop", id="stop", variant="error", classes="toolbar-button")
        with Horizontal(id="filters"):
            yield Label("Country", classes="filter-label")
            yield Input(placeholder="optional", id="country-filter")
            yield Label("Min kbps", classes="filter-label")
            yield Input(placeholder="0", id="bitrate-filter")
            yield Button("Clear filters", id="clear-filters", classes="toolbar-button")
        with Horizontal(id="content"):
            yield ListView(id="stations")
            with Vertical(id="side-panel"):
                yield Static("Search", id="mode-title")
                yield Static("[b]Now Playing[/b]\nNothing playing yet.", id="now-playing")
                yield Static("No station selected.", id="details")
                yield Button("Play", id="play", variant="success", classes="side-button")
                yield Button("Add fav", id="add-favorite", classes="side-button")
                yield Button("Remove fav", id="remove-favorite", variant="warning", classes="side-button")
        yield Static(
            "Ready. Press '/' to search, 'f' favorites, 'h' history, 't' themes, Space pause, +/- volume.",
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

        # Apply the selected theme programmatically so runtime preview works reliably.
        try:
            apply_theme_runtime(self, self.active_theme)
            self.ensure_now_playing_layout()
        except Exception as exc:  # noqa: BLE001
            self.notify(f"Theme load failed: {exc}", severity="warning", timeout=6)

        self.query_one("#stations", ListView).focus()
        self.update_now_playing()
        self.set_interval(1.5, self.update_now_playing)
        self.update_details(None)

    def on_unmount(self) -> None:
        self.cancel_pending_search()
        self.player.stop()

    def action_focus_search(self) -> None:
        self.query_one("#query", Input).focus()
        self.set_status("Search focused. Type a query and press Enter. Press Escape to return to the main list.")

    def action_focus_station_list(self) -> None:
        self.query_one("#stations", ListView).focus()
        if self.view_mode == "themes":
            self.set_status("Theme list focused. Use ↑/↓ to preview, Enter or p to apply, y to save.")
        elif self.view_mode == "history":
            self.set_status("History focused. Use Enter to play, a to add again to favorites, f for favorites.")
        else:
            self.set_status("Station list focused. Use Enter to play, f favorites, h history, a add, r random.")

    async def action_show_favorites(self) -> None:
        await self.show_favorites()

    async def action_show_themes(self) -> None:
        await self.show_themes()

    async def action_show_history(self) -> None:
        await self.show_history()

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
            self.set_status("Random favorite playback is disabled while browsing themes. Press f, h or search first.")
            return
        self.play_random_favorite()

    def action_stop(self) -> None:
        self.stop_playback()

    def action_toggle_pause(self) -> None:
        try:
            self.player.toggle_pause()
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Pause/resume failed: {exc}")
            return
        self.update_now_playing()
        self.set_status("Toggled pause/resume.")

    def action_toggle_mute(self) -> None:
        try:
            self.player.toggle_mute()
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Mute toggle failed: {exc}")
            return
        self.update_now_playing()
        self.set_status("Toggled mute.")

    def action_volume_up(self) -> None:
        try:
            self.player.volume_up()
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Volume up failed: {exc}")
            return
        self.update_now_playing()
        self.set_status("Volume increased.")

    def action_volume_down(self) -> None:
        try:
            self.player.volume_down()
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Volume down failed: {exc}")
            return
        self.update_now_playing()
        self.set_status("Volume decreased.")

    def action_preview_theme(self) -> None:
        self.preview_selected_theme()

    def action_save_theme(self) -> None:
        self.save_active_theme()

    @on(Input.Submitted, "#query")
    async def search_from_input(self, event: Input.Submitted) -> None:
        self.cancel_pending_search()
        await self.search(event.value)

    @on(Input.Changed, "#query")
    def live_search_from_input(self, event: Input.Changed) -> None:
        self.schedule_live_search(event.value)

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

    @on(Button.Pressed, "#history")
    async def history_from_button(self) -> None:
        await self.show_history()

    @on(Button.Pressed, "#clear-filters")
    def clear_filters_from_button(self) -> None:
        self.query_one("#country-filter", Input).value = ""
        self.query_one("#bitrate-filter", Input).value = ""
        self.set_status("Search filters cleared. Type or press Enter in search to refresh results.")

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

    def cancel_pending_search(self) -> None:
        if self._search_task and not self._search_task.done():
            self._search_task.cancel()
        self._search_task = None

    def schedule_live_search(self, query: str) -> None:
        query = query.strip()
        self.cancel_pending_search()

        if not query:
            self.set_status("Type at least 3 characters to search, or press Enter for an exact short search.")
            return

        if len(query) < 3:
            self.set_status("Keep typing... live search starts at 3 characters.")
            return

        self._search_task = asyncio.create_task(self._debounced_search(query))

    async def _debounced_search(self, query: str) -> None:
        try:
            await asyncio.sleep(0.55)
            current_query = self.query_one("#query", Input).value.strip()
            if current_query == query:
                await self.search(query, live=True)
        except asyncio.CancelledError:
            return

    async def search(self, query: str, live: bool = False) -> None:
        query = query.strip()
        if not query:
            self.set_status("Type a station name or genre/tag first.")
            return

        self.view_mode = "search"
        self._search_task = None
        self.update_mode_title("Search results")
        self.set_status(f"Live searching: {query} ..." if live else f"Searching: {query} ...")
        list_view = self.query_one("#stations", ListView)
        await list_view.clear()
        self.selected_station = None
        self.selected_theme = None
        self.update_details(None)

        try:
            country = self.query_one("#country-filter", Input).value.strip()
            min_bitrate_raw = self.query_one("#bitrate-filter", Input).value.strip()
            min_bitrate = None
            if min_bitrate_raw:
                try:
                    min_bitrate = int(min_bitrate_raw)
                except ValueError:
                    self.set_status("Min kbps must be a number.")
                    return
            stations = await asyncio.to_thread(search_stations_filtered, query, country or None, min_bitrate, 50)
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Search failed: {exc}")
            self.notify(f"Search failed: {exc}", severity="error")
            return

        await self.populate_station_list(stations)
        if not live:
            self.query_one("#stations", ListView).focus()
        filters = []
        country = self.query_one("#country-filter", Input).value.strip()
        min_bitrate_raw = self.query_one("#bitrate-filter", Input).value.strip()
        if country:
            filters.append(f"country={country}")
        if min_bitrate_raw:
            filters.append(f"min={min_bitrate_raw}kbps")
        suffix = f" ({', '.join(filters)})" if filters else ""
        prefix = "Live search" if live else "Found"
        self.set_status(f"{prefix}: {len(stations)} station(s) for: {query}{suffix}")

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

    async def show_history(self) -> None:
        self.view_mode = "history"
        self.update_mode_title("Recently played")
        history = load_history()
        list_view = self.query_one("#stations", ListView)
        await list_view.clear()
        self.selected_station = None
        self.selected_theme = None
        self.update_details(None)
        await self.populate_station_list(history)
        self.query_one("#stations", ListView).focus()
        self.set_status(f"Loaded {len(history)} recently played station(s).")

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
        self.set_status("Theme selector. Highlight previews automatically. Press Enter/p to apply, y to save.")

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
        add_history(self.selected_station)
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

    def apply_theme(self, theme_name: str, save: bool = False, announce: bool = True) -> None:
        if not theme_exists(theme_name):
            self.set_status(f"Theme not found: {theme_name}")
            return

        self.active_theme = theme_name
        self.theme_path = get_theme_path(theme_name)

        try:
            apply_theme_runtime(self, theme_name)
            self.ensure_now_playing_layout()
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Theme apply failed: {exc}")
            self.notify(f"Theme apply failed: {exc}", severity="error")
            return

        if save:
            set_config_value("theme", theme_name)

        if announce:
            suffix = "saved" if save else "previewed"
            self.set_status(f"Theme {suffix}: {theme_name}")

    def update_details(self, station: dict[str, Any] | None) -> None:
        details = self.query_one("#details", Static)
        if not station:
            details.update("[b]Selected Station[/b]\nNo station selected.")
            return

        play_count = station.get("play_count")
        play_count_line = f"\nPlay count: {play_count}" if play_count else ""
        details.update(
            "[b]Selected Station[/b]\n\n"
            "[b]{}[/b]\n\nCountry: {}\nCodec: {}\nBitrate: {} kbps\nLanguage: {}{}\nTags: {}\nHomepage: {}".format(
                station.get("name", "Unknown station"),
                station.get("country", "Unknown"),
                station.get("codec") or "?",
                station.get("bitrate") or "?",
                station.get("language") or "?",
                play_count_line,
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
            "Preview is applied automatically while browsing."
        )

    def ensure_now_playing_layout(self) -> None:
        """Keep the Now Playing panel readable across themes and terminal sizes."""
        try:
            now_playing = self.query_one("#now-playing", Static)
            now_playing.styles.height = 10
            now_playing.styles.min_height = 10
            now_playing.styles.width = "100%"
            now_playing.styles.padding = (1, 2)
            now_playing.styles.content_align = ("left", "top")
            now_playing.styles.text_align = "left"
            now_playing.styles.overflow = "hidden"
            now_playing.styles.text_overflow = "ellipsis"
            # Textual versions differ here; ignore unsupported style names.
            try:
                now_playing.styles.white_space = "normal"
            except Exception:
                pass
        except Exception:
            pass

    def update_now_playing(self) -> None:
        now_playing = self.query_one("#now-playing", Static)
        self.ensure_now_playing_layout()
        if not self.playing_station:
            now_playing.update("[b]Now Playing[/b]\nNothing playing yet.")
            return

        station = self.playing_station
        try:
            state = self.player.get_state()
        except Exception:  # noqa: BLE001
            state = {"playing": self.player.is_playing()}

        is_running = bool(state.get("playing"))
        paused = bool(state.get("paused"))
        muted = bool(state.get("muted"))
        volume = state.get("volume")

        if not is_running:
            status_icon = "■"
            status_label = "Stopped"
        elif paused:
            status_icon = "⏸"
            status_label = "Paused"
        else:
            status_icon = "▶"
            status_label = "Playing"

        mute_label = "muted" if muted else "sound on"
        volume_label = f"{int(round(volume))}%" if isinstance(volume, (int, float)) else "?"
        tags = station.get("tags") or "no tags"

        name = station.get("name", "Unknown station")
        country = station.get("country") or "Unknown country"
        bitrate = station.get("bitrate") or "?"
        codec = station.get("codec") or "?"

        now_playing.update(
            "[b]Now Playing[/b]\n"
            f"{status_icon} [b]{name}[/b]\n"
            f"{country} • {bitrate} kbps • {codec}\n"
            f"Volume: {volume_label} • {status_label} • {mute_label}\n"
            f"Tags: {tags[:95]}"
        )

    def update_mode_title(self, title: str) -> None:
        self.query_one("#mode-title", Static).update(title)

    def set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)


def run_tui(theme: str | None = None) -> None:
    FluxTunerTUI(theme=theme).run()
