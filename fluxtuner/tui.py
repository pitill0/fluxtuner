from __future__ import annotations

import asyncio
import random
import textwrap
from pathlib import Path
from typing import Any

from textual import on
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static

from fluxtuner.config import get_playback_state, save_playback_state, set_config_value
from fluxtuner.core.api import search_stations_filtered
from fluxtuner.core.favorites import (
    add_favorite,
    all_favorite_tags,
    favorite_display_name,
    filter_favorites_by_tag,
    load_favorites,
    remove_favorite,
    station_key,
    update_favorite,
)
from fluxtuner.core.history import add_history, load_history
from fluxtuner.core.manual_playlists import (
    add_station_to_playlist,
    create_playlist,
    delete_playlist,
    get_playlist_stations,
    playlist_counts,
    random_from_playlist,
    remove_station_from_playlist,
    summarize_playlist,
)
from fluxtuner.core.playlists import get_by_tag, get_tag_counts, random_by_tag
from fluxtuner.players import create_player
from fluxtuner.players.mpv import PlayerError, ensure_mpv_available
from fluxtuner.theme_runtime import apply_theme_runtime
from fluxtuner.themes import DEFAULT_THEME, get_theme_path, list_themes, theme_exists


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
        ("l", "play_last_station", "Last"),
        ("d", "remove_selected", "Delete fav"),
        ("e", "edit_favorite_name", "Rename fav"),
        ("g", "edit_favorite_tags", "Tags"),
        ("u", "filter_favorites_by_tag", "Filter tag"),
        ("b", "add_to_playlist", "Add playlist"),
        ("n", "new_playlist", "New playlist"),
        ("r", "play_random_favorite", "Random"),
        ("space", "toggle_pause", "Pause"),
        ("plus", "volume_up", "Vol+"),
        ("minus", "volume_down", "Vol-"),
        ("m", "toggle_mute", "Mute"),
        ("x", "stop", "Stop"),
        ("t", "show_themes", "Themes"),
        ("p", "show_playlists", "Playlists"),
        ("y", "save_theme", "Save theme"),
    ]

    def __init__(self, theme: str | None = None, player_name: str = "mpv") -> None:
        self.active_theme = theme or DEFAULT_THEME
        self.theme_path = get_theme_path(self.active_theme)
        super().__init__(css_path=str(self.theme_path))
        self.player = create_player(player_name)
        self.selected_station: dict[str, Any] | None = None
        self.selected_theme: str | None = None
        self.previewed_theme: str | None = None
        self.selected_tag: str | None = None
        self.selected_playlist: str | None = None
        self.active_playlist_name: str | None = None
        self.playing_station: dict[str, Any] | None = None
        self.last_station: dict[str, Any] | None = None
        self.restored_volume: int | float | None = None
        self.restored_muted: bool | None = None
        self.view_mode = "search"
        self._search_task = None
        self.pending_input_action: str | None = None
        self.favorite_tag_filter: str | None = None
        self.table_items: dict[str, tuple[str, Any]] = {}
        self.table_key_counter = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="toolbar"):
            yield Input(placeholder="Search by station name or genre/tag", id="query")
            yield Button("Search", id="search", classes="toolbar-button primary-button")
            yield Button("Favs", id="favorites", classes="toolbar-button")
            yield Button("History", id="history", classes="toolbar-button")
            yield Button("Random", id="random", classes="toolbar-button")
            yield Button("Playlists", id="playlists", classes="toolbar-button")
            yield Button("Themes", id="themes", classes="toolbar-button")
            yield Button("Stop", id="stop", classes="toolbar-button danger-button")
        with Horizontal(id="filters"):
            yield Label("Country", classes="filter-label")
            yield Input(placeholder="optional", id="country-filter")
            yield Label("Min kbps", classes="filter-label")
            yield Input(placeholder="0", id="bitrate-filter")
            yield Button("Clear filters", id="clear-filters", classes="toolbar-button secondary-button")
        with Horizontal(id="content"):
            yield DataTable(id="stations", cursor_type="row", zebra_stripes=True)
            with Vertical(id="side-panel"):
                yield Static("Search", id="mode-title")
                yield Static("[b]Now Playing[/b]\nNothing playing yet.", id="now-playing")
                yield Static("No station selected.", id="details")
                yield Button("Play", id="play", classes="side-button success-button")
                yield Button("Add fav", id="add-favorite", classes="side-button primary-button")
                yield Button("Remove fav", id="remove-favorite", classes="side-button warning-button")
                yield Button("Rename fav", id="rename-favorite", classes="side-button secondary-button")
                yield Button("Edit tags", id="edit-tags", classes="side-button secondary-button")
        yield Static(
            "Ready. Press '/' search, 'f' favorites, 'h' history, 'p' playlists, 'b' add to playlist, 't' themes, Space pause, +/- volume.",
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

        self.restore_playback_state()
        self.query_one("#stations", DataTable).focus()
        self.update_now_playing()
        self.set_interval(1.5, self.update_now_playing)
        if self.last_station:
            self.update_details(self.last_station)
            self.set_status(f"Restored last station: {favorite_display_name(self.last_station)}. Press l to play it.")
        else:
            self.update_details(None)

    def on_unmount(self) -> None:
        self.cancel_pending_search()
        self.player.stop()

    def action_focus_search(self) -> None:
        self.query_one("#query", Input).focus()
        self.set_status("Search focused. Type a query and press Enter. Press Escape to return to the main list.")

    def action_focus_station_list(self) -> None:
        self.query_one("#stations", DataTable).focus()
        if self.view_mode == "themes":
            self.set_status("Theme list focused. Use ↑/↓ to preview, Enter to apply, y to save.")
        elif self.view_mode == "history":
            self.set_status("History focused. Use Enter to play, a to add again to favorites, f for favorites.")
        elif self.view_mode == "playlists":
            self.set_status("Playlists focused. Enter/r smart plays, f opens playlist stations, n creates, d deletes persistent playlists.")
        elif self.view_mode == "playlist_stations":
            self.set_status("Playlist stations focused. Enter plays, d removes from this persistent playlist, b adds selected to another playlist.")
        else:
            self.set_status("Station list focused. Use Enter to play, f favorites, h history, p playlists, a add, r random.")

    async def action_show_favorites(self) -> None:
        if self.view_mode == "playlists" and self.selected_playlist:
            await self.show_persistent_playlist_stations(self.selected_playlist)
            return
        if self.view_mode == "playlists" and self.selected_tag:
            await self.show_favorites(tag_filter=self.selected_tag)
            return
        await self.show_favorites()

    async def action_show_themes(self) -> None:
        await self.show_themes()

    async def action_show_history(self) -> None:
        await self.show_history()

    async def action_show_playlists(self) -> None:
        await self.show_playlists()

    def action_activate_selected(self) -> None:
        if self.view_mode == "themes":
            self.apply_selected_theme()
            return
        if self.view_mode == "playlists":
            self.smart_play_selected_playlist_or_tag()
            return
        self.play_selected_station()

    def action_add_selected(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Use ↑/↓ to preview temporarily, Enter to apply, or y to save the active theme as default.")
            return
        if self.view_mode == "playlists":
            self.set_status("Playlist mode: press Enter/r to smart play, f to view stations, n to create a playlist.")
            return
        self.add_selected_to_favorites()

    async def action_remove_selected(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Theme files are not deleted from FluxTuner. Remove .tcss files manually if needed.")
            return
        if self.view_mode == "playlists":
            await self.delete_selected_persistent_playlist()
            return
        if self.view_mode == "playlist_stations":
            await self.remove_selected_from_active_playlist()
            return
        await self.remove_selected_from_favorites()

    def action_edit_favorite_name(self) -> None:
        self.prepare_favorite_name_edit()

    def action_edit_favorite_tags(self) -> None:
        self.prepare_favorite_tags_edit()

    def action_filter_favorites_by_tag(self) -> None:
        self.prepare_favorites_tag_filter()

    def action_add_to_playlist(self) -> None:
        self.prepare_add_to_playlist()

    def action_new_playlist(self) -> None:
        self.prepare_new_playlist()

    def action_play_last_station(self) -> None:
        self.play_last_station()

    def action_play_random_favorite(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Random favorite playback is disabled while browsing themes. Press f, h or search first.")
            return
        if self.view_mode == "playlists":
            self.smart_play_selected_playlist_or_tag()
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
        self.persist_player_state()
        self.set_status("Toggled mute.")

    def action_volume_up(self) -> None:
        try:
            self.player.volume_up()
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Volume up failed: {exc}")
            return
        self.update_now_playing()
        self.persist_player_state()
        self.set_status("Volume increased.")

    def action_volume_down(self) -> None:
        try:
            self.player.volume_down()
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Volume down failed: {exc}")
            return
        self.update_now_playing()
        self.persist_player_state()
        self.set_status("Volume decreased.")

    def action_preview_theme(self) -> None:
        self.preview_selected_theme()

    def action_save_theme(self) -> None:
        self.save_active_theme()

    @on(Input.Submitted, "#query")
    async def search_from_input(self, event: Input.Submitted) -> None:
        self.cancel_pending_search()
        if self.pending_input_action:
            await self.handle_pending_input(event.value)
            return
        await self.search(event.value)

    @on(Input.Changed, "#query")
    def live_search_from_input(self, event: Input.Changed) -> None:
        if self.pending_input_action:
            return
        self.schedule_live_search(event.value)

    @on(Button.Pressed, "#search")
    async def search_from_button(self) -> None:
        query = self.query_one("#query", Input).value
        self.cancel_pending_search()
        if self.pending_input_action:
            await self.handle_pending_input(query)
            return
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

    @on(Button.Pressed, "#playlists")
    async def playlists_from_button(self) -> None:
        await self.show_playlists()

    @on(Button.Pressed, "#clear-filters")
    def clear_filters_from_button(self) -> None:
        self.query_one("#country-filter", Input).value = ""
        self.query_one("#bitrate-filter", Input).value = ""
        self.favorite_tag_filter = None
        self.set_status("Filters cleared. Type or press Enter in search to refresh results.")

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

    @on(Button.Pressed, "#rename-favorite")
    def rename_favorite_from_button(self) -> None:
        self.prepare_favorite_name_edit()

    @on(Button.Pressed, "#edit-tags")
    def edit_tags_from_button(self) -> None:
        self.prepare_favorite_tags_edit()

    @on(DataTable.RowHighlighted, "#stations")
    def item_highlighted(self, event: DataTable.RowHighlighted) -> None:
        payload = self.selected_payload_from_event(event)
        if not payload:
            return
        kind, item_payload = payload
        if kind == "station":
            self.selected_station = item_payload
            self.selected_theme = None
            self.selected_tag = None
            self.selected_playlist = None if self.view_mode != "playlist_stations" else self.selected_playlist
            self.update_details(item_payload)
        elif kind == "theme":
            self.selected_theme = item_payload
            self.selected_station = None
            self.selected_tag = None
            self.selected_playlist = None
            self.update_theme_details(item_payload)
            self.preview_theme(item_payload, announce=False)
        elif kind == "playlist":
            self.selected_playlist = item_payload["name"]
            self.selected_tag = None
            self.selected_station = None
            self.selected_theme = None
            self.update_persistent_playlist_details(item_payload["name"], item_payload["count"])
        elif kind == "tag":
            self.selected_tag = item_payload["tag"]
            self.selected_playlist = None
            self.selected_station = None
            self.selected_theme = None
            self.update_playlist_details(item_payload["tag"], item_payload["count"])

    @on(DataTable.RowSelected, "#stations")
    def item_selected(self, event: DataTable.RowSelected) -> None:
        payload = self.selected_payload_from_event(event)
        if not payload:
            return
        kind, item_payload = payload
        if kind == "station":
            self.selected_station = item_payload
            self.selected_theme = None
            self.update_details(item_payload)
            self.play_selected_station()
        elif kind == "theme":
            self.selected_theme = item_payload
            self.apply_selected_theme()
        elif kind == "playlist":
            self.selected_playlist = item_payload["name"]
            self.smart_play_selected_playlist_or_tag()
        elif kind == "tag":
            self.selected_tag = item_payload["tag"]
            self.smart_play_selected_playlist_or_tag()

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
        self.restore_active_theme_if_previewing()
        query = query.strip()
        if not query:
            self.set_status("Type a station name or genre/tag first.")
            return

        self.view_mode = "search"
        self._search_task = None
        self.update_mode_title("Search results")
        self.set_status(f"Live searching: {query} ..." if live else f"Searching: {query} ...")
        list_view = self.query_one("#stations", DataTable)
        list_view.clear(columns=True)
        self.selected_station = None
        self.selected_theme = None
        self.selected_tag = None
        self.selected_playlist = None
        self.active_playlist_name = None
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
            self.query_one("#stations", DataTable).focus()
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

    async def show_favorites(self, tag_filter: str | None = None) -> None:
        self.restore_active_theme_if_previewing()
        self.view_mode = "favorites"
        self.favorite_tag_filter = tag_filter
        title = "Favorites" if not tag_filter else f"Favorites · tag: {tag_filter}"
        self.update_mode_title(title)
        favorites = filter_favorites_by_tag(tag_filter) if tag_filter else load_favorites()
        favorites = sorted(favorites, key=lambda item: favorite_display_name(item).lower())
        list_view = self.query_one("#stations", DataTable)
        list_view.clear(columns=True)
        self.selected_station = None
        self.selected_theme = None
        self.selected_tag = None
        self.selected_playlist = None
        self.active_playlist_name = None
        self.update_details(None)
        await self.populate_station_list(favorites)
        self.query_one("#stations", DataTable).focus()
        if tag_filter:
            self.set_status(f"Loaded {len(favorites)} favorite station(s) tagged '{tag_filter}'.")
        else:
            tags = all_favorite_tags()
            suffix = f" Tags: {', '.join(tags[:8])}" if tags else " Add tags with g."
            self.set_status(f"Loaded {len(favorites)} favorite station(s).{suffix}")

    async def show_history(self) -> None:
        self.restore_active_theme_if_previewing()
        self.view_mode = "history"
        self.update_mode_title("Recently played")
        history = load_history()
        list_view = self.query_one("#stations", DataTable)
        list_view.clear(columns=True)
        self.selected_station = None
        self.selected_theme = None
        self.selected_tag = None
        self.selected_playlist = None
        self.active_playlist_name = None
        self.update_details(None)
        await self.populate_station_list(history)
        self.query_one("#stations", DataTable).focus()
        self.set_status(f"Loaded {len(history)} recently played station(s).")

    async def show_playlists(self) -> None:
        self.restore_active_theme_if_previewing()
        self.view_mode = "playlists"
        self.active_playlist_name = None
        self.update_mode_title("Playlists")
        manual_counts = playlist_counts()
        tag_counts = get_tag_counts()
        table = self.reset_playlist_table()
        self.selected_station = None
        self.selected_theme = None
        self.selected_tag = None
        self.selected_playlist = None

        if not manual_counts and not tag_counts:
            table.add_row("Info", "No playlists yet", "0", "Create persistent playlists with n, or add tags to favorites with g.", key="empty-playlists")
            self.query_one("#details", Static).update(
                "[b]Playlists[/b]\n\n"
                "Create persistent playlists with [b]n[/b], or add tags to favorites with [b]g[/b] to get dynamic playlists."
            )
            table.focus()
            self.set_status("No playlists yet. Press n to create one, or tag favorites with g.")
            return

        first_actionable_key: str | None = None
        for name, count in manual_counts:
            key = self.next_table_key("playlist")
            self.add_table_payload(key, "playlist", {"name": name, "count": count})
            table.add_row("Persistent", name, str(count), "Manual playlist saved in your library", key=key)
            first_actionable_key = first_actionable_key or key

        for tag, count in tag_counts:
            key = self.next_table_key("tag")
            self.add_table_payload(key, "tag", {"tag": tag, "count": count})
            table.add_row("Dynamic", f"#{tag}", str(count), "Generated automatically from favorite tags", key=key)
            first_actionable_key = first_actionable_key or key

        if first_actionable_key:
            table.move_cursor(row=0)
            kind, payload = self.table_items[first_actionable_key]
            if kind == "playlist":
                self.selected_playlist = payload["name"]
                self.update_persistent_playlist_details(payload["name"], payload["count"])
            elif kind == "tag":
                self.selected_tag = payload["tag"]
                self.update_playlist_details(payload["tag"], payload["count"])

        table.focus()
        self.set_status("Playlists loaded. Enter/r smart plays, f opens stations, n creates, d deletes persistent playlists.")

    async def show_themes(self) -> None:
        self.view_mode = "themes"
        self.update_mode_title("Themes")
        table = self.reset_playlist_table()
        self.selected_station = None
        self.selected_tag = None
        themes = list_themes()

        for theme_name in themes:
            key = self.next_table_key("theme")
            self.add_table_payload(key, "theme", theme_name)
            status = "active" if theme_name == self.active_theme else "available"
            table.add_row("Theme", theme_name, status, f"{Path(get_theme_path(theme_name)).name}", key=key)

        if themes:
            table.move_cursor(row=0)
            self.selected_theme = themes[0]
            self.update_theme_details(themes[0])
        else:
            self.selected_theme = None
            self.query_one("#details", Static).update("[b]Themes[/b]\nNo themes found.")

        table.focus()
        self.set_status("Theme selector. Highlight previews temporarily. Press Enter to apply, y to save active theme.")

    async def populate_station_list(self, stations: list[dict[str, Any]]) -> None:
        table = self.reset_station_table()
        if not stations:
            table.add_row("", "No stations available", "", "", "", "", "", "", key="empty-stations")
            return

        for station in stations:
            self.add_station_table_row(table, station)

        table.move_cursor(row=0)
        first_key = next(iter(self.table_items), None)
        if first_key:
            kind, payload = self.table_items[first_key]
            if kind == "station":
                self.selected_station = payload
                self.update_details(payload)


    def reset_station_table(self) -> DataTable:
        """Reset the main table for station-like rows."""
        table = self.query_one("#stations", DataTable)
        table.clear(columns=True)
        self.table_items.clear()
        self.table_key_counter = 0
        table.add_columns("", "Name", "ID", "Country", "Genre / tags", "Codec", "kbps", "Custom tags")
        return table

    def reset_playlist_table(self) -> DataTable:
        """Reset the main table for playlist/theme rows."""
        table = self.query_one("#stations", DataTable)
        table.clear(columns=True)
        self.table_items.clear()
        self.table_key_counter = 0
        table.add_columns("Type", "Name", "Count / Status", "Description")
        return table

    def next_table_key(self, prefix: str) -> str:
        self.table_key_counter += 1
        return f"{prefix}-{self.table_key_counter}"

    def add_table_payload(self, key: str, kind: str, payload: Any) -> None:
        self.table_items[str(key)] = (kind, payload)

    def row_key_to_string(self, row_key: Any) -> str:
        value = getattr(row_key, "value", row_key)
        return str(value)

    def selected_payload_from_event(self, event: Any) -> tuple[str, Any] | None:
        key = self.row_key_to_string(getattr(event, "row_key", ""))
        return self.table_items.get(key)

    def station_short_id(self, station: dict[str, Any]) -> str:
        raw = station.get("stationuuid") or station.get("changeuuid") or self.station_url(station) or ""
        return str(raw)[:8] if raw else "-"

    def station_genre_tags(self, station: dict[str, Any], max_length: int = 42) -> str:
        tags = station.get("tags") or ""
        if isinstance(tags, list):
            tags = ", ".join(str(tag) for tag in tags)
        return self._ellipsize(str(tags) if tags else "-", max_length)

    def station_custom_tags(self, station: dict[str, Any], max_length: int = 28) -> str:
        tags = station.get("favorite_tags") or station.get("tags_custom") or []
        if isinstance(tags, str):
            value = tags
        else:
            value = ", ".join(str(tag) for tag in tags)
        return self._ellipsize(value if value else "-", max_length)

    def add_station_table_row(self, table: DataTable, station: dict[str, Any]) -> None:
        key = self.next_table_key("station")
        self.add_table_payload(key, "station", station)
        marker = "▶" if self.station_url(station) == self.current_station_url() else ""
        name = self._ellipsize(favorite_display_name(station), 52)
        table.add_row(
            marker,
            name,
            self.station_short_id(station),
            self._ellipsize(station.get("country") or "-", 18),
            self.station_genre_tags(station),
            str(station.get("codec") or "-"),
            str(station.get("bitrate") or "-"),
            self.station_custom_tags(station),
            key=key,
        )

    def refresh_active_station_marker(self) -> None:
        """Refresh the active marker without rebuilding the whole view.

        DataTable cells are intentionally updated best-effort because older
        Textual versions differ slightly in their cell update API.
        """
        try:
            table = self.query_one("#stations", DataTable)
            current_url = self.current_station_url()
            for key, (kind, payload) in self.table_items.items():
                if kind != "station":
                    continue
                marker = "▶" if self.station_url(payload) == current_url else ""
                try:
                    table.update_cell(key, "", marker)
                except Exception:  # noqa: BLE001
                    return
        except Exception:  # noqa: BLE001
            return

    def play_selected_station(self) -> None:
        if self.view_mode == "themes":
            self.apply_selected_theme()
            return
        if self.view_mode == "playlists":
            self.smart_play_selected_playlist_or_tag()
            return

        if not self.selected_station:
            self.set_status("No station selected.")
            return

        self.play_station(self.selected_station)

    def play_station(self, station: dict[str, Any]) -> bool:
        url = self.station_url(station)
        if not url:
            self.set_status("Selected station has no playable URL.")
            return False

        try:
            self.player.play(url)
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Playback failed: {exc}")
            self.notify(f"Playback failed: {exc}", severity="error")
            return False

        self.playing_station = station
        self.last_station = station
        add_history(station)
        self.apply_restored_playback_preferences()
        self.persist_player_state(last_station=station)
        self.update_now_playing()
        self.refresh_active_station_marker()
        self.set_status(f"Playing: {favorite_display_name(station)}")
        return True

    def stop_playback(self) -> None:
        self.player.stop()
        self.playing_station = None
        self.update_now_playing()
        self.refresh_active_station_marker()
        self.set_status("Playback stopped.")

    def add_selected_to_favorites(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Themes mode: use Enter to apply, y to save as default.")
            return
        if not self.selected_station:
            self.set_status("No station selected.")
            return
        saved = add_favorite(self.selected_station)
        name = favorite_display_name(self.selected_station)
        self.set_status(f"Saved favorite: {name}" if saved else f"Already in favorites: {name}")

    async def remove_selected_from_favorites(self) -> None:
        if self.view_mode == "themes":
            self.set_status("Themes cannot be removed from the app UI.")
            return
        if not self.selected_station:
            self.set_status("No station selected.")
            return

        key = self.station_url(self.selected_station)
        if not key:
            self.set_status("Selected station has no favorite key.")
            return

        removed = remove_favorite(key)
        name = favorite_display_name(self.selected_station)
        self.set_status(f"Removed favorite: {name}" if removed else f"Favorite not found: {name}")

        if self.view_mode == "favorites":
            await self.show_favorites(tag_filter=self.favorite_tag_filter)

    async def delete_selected_persistent_playlist(self) -> None:
        if not self.selected_playlist:
            self.set_status("Select a persistent playlist to delete. Dynamic tag playlists are managed by favorite tags.")
            return
        name = self.selected_playlist
        deleted = delete_playlist(name)
        await self.show_playlists()
        self.set_status(f"Deleted playlist: {name}" if deleted else f"Playlist not found: {name}")

    async def remove_selected_from_active_playlist(self) -> None:
        if not self.active_playlist_name:
            self.set_status("No active persistent playlist.")
            return
        if not self.selected_station:
            self.set_status("No station selected.")
            return
        removed = remove_station_from_playlist(self.active_playlist_name, self.selected_station)
        name = favorite_display_name(self.selected_station)
        playlist = self.active_playlist_name
        await self.show_persistent_playlist_stations(playlist)
        self.set_status(f"Removed {name} from playlist: {playlist}" if removed else f"Station not found in playlist: {playlist}")

    def play_last_station(self) -> None:
        if not self.last_station:
            self.set_status("No last station saved yet.")
            return
        self.selected_station = self.last_station
        self.selected_theme = None
        self.update_details(self.selected_station)
        self.play_selected_station()

    def play_random_favorite(self) -> None:
        favorites = load_favorites()
        if not favorites:
            self.set_status("No favorites yet.")
            return
        self.selected_station = random.choice(favorites)
        self.selected_theme = None
        self.selected_tag = None
        self.update_details(self.selected_station)
        self.play_selected_station()

    def smart_play_selected_playlist_or_tag(self) -> None:
        if self.selected_playlist:
            station = random_from_playlist(self.selected_playlist)
            if not station:
                self.set_status(f"Persistent playlist '{self.selected_playlist}' has no available favorite stations.")
                return
            self.selected_station = station
            self.selected_theme = None
            self.update_details(station)
            if self.play_station(station):
                self.set_status(f"Smart Play {self.selected_playlist}: {favorite_display_name(station)}")
            return

        if self.selected_tag:
            station = random_by_tag(self.selected_tag)
            if not station:
                self.set_status(f"No favorite stations tagged '{self.selected_tag}'.")
                return
            self.selected_station = station
            self.selected_theme = None
            self.update_details(station)
            if self.play_station(station):
                self.set_status(f"Smart Play #{self.selected_tag}: {favorite_display_name(station)}")
            return

        self.set_status("No playlist selected.")

    async def show_selected_playlist_favorites(self) -> None:
        if self.selected_playlist:
            await self.show_persistent_playlist_stations(self.selected_playlist)
            return
        if self.selected_tag:
            await self.show_favorites(tag_filter=self.selected_tag)
            return
        self.set_status("No playlist selected.")

    async def show_persistent_playlist_stations(self, playlist_name: str) -> None:
        self.view_mode = "playlist_stations"
        self.active_playlist_name = playlist_name
        self.update_mode_title(f"Playlist · {playlist_name}")
        stations = get_playlist_stations(playlist_name)
        self.selected_station = None
        self.selected_theme = None
        self.selected_tag = None
        self.selected_playlist = playlist_name
        self.update_details(None)
        await self.populate_station_list(stations)
        self.query_one("#stations", DataTable).focus()
        self.set_status(f"Loaded {len(stations)} station(s) in playlist '{playlist_name}'. Press d to remove selected from this playlist.")

    def preview_selected_theme(self) -> None:
        if not self.selected_theme:
            self.set_status("No theme selected.")
            return
        self.preview_theme(self.selected_theme, announce=True)

    def apply_selected_theme(self) -> None:
        if not self.selected_theme:
            self.set_status("No theme selected.")
            return
        self.apply_theme(self.selected_theme, save=False, announce=True)

    def save_active_theme(self) -> None:
        set_config_value("theme", self.active_theme)
        self.previewed_theme = None
        self.set_status(f"Saved default theme: {self.active_theme}")
        self.notify(f"Saved default theme: {self.active_theme}", severity="information")

    def preview_theme(self, theme_name: str, announce: bool = True) -> None:
        if not theme_exists(theme_name):
            self.set_status(f"Theme not found: {theme_name}")
            return

        try:
            apply_theme_runtime(self, theme_name)
            self.ensure_now_playing_layout()
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Theme preview failed: {exc}")
            self.notify(f"Theme preview failed: {exc}", severity="error")
            return

        self.previewed_theme = theme_name
        if announce:
            self.set_status(f"Theme preview: {theme_name}. Press Enter to apply or y to save the active theme.")

    def restore_active_theme_if_previewing(self) -> None:
        if not self.previewed_theme or self.previewed_theme == self.active_theme:
            self.previewed_theme = None
            return
        try:
            apply_theme_runtime(self, self.active_theme)
            self.ensure_now_playing_layout()
        except Exception:
            return
        self.previewed_theme = None

    def apply_theme(self, theme_name: str, save: bool = False, announce: bool = True) -> None:
        if not theme_exists(theme_name):
            self.set_status(f"Theme not found: {theme_name}")
            return

        try:
            apply_theme_runtime(self, theme_name)
            self.ensure_now_playing_layout()
        except Exception as exc:  # noqa: BLE001
            self.set_status(f"Theme apply failed: {exc}")
            self.notify(f"Theme apply failed: {exc}", severity="error")
            return

        self.active_theme = theme_name
        self.theme_path = get_theme_path(theme_name)
        self.previewed_theme = None

        if save:
            set_config_value("theme", theme_name)

        self.update_theme_details(theme_name)

        if announce:
            suffix = "saved" if save else "applied"
            self.set_status(f"Theme {suffix}: {theme_name}")

    def update_details(self, station: dict[str, Any] | None) -> None:
        details = self.query_one("#details", Static)
        if not station:
            details.update("[b]Selected Station[/b]\nNo station selected.")
            return

        play_count = station.get("play_count")
        play_count_line = f"\nPlay count: {play_count}" if play_count else ""
        favorite_tags = station.get("favorite_tags") or []
        favorite_tags_line = f"\nFavorite tags: {', '.join(favorite_tags)}" if favorite_tags else ""
        original_name_line = ""
        if station.get("custom_name"):
            original_name_line = f"\nOriginal name: {station.get('name', 'Unknown station')}"
        details.update(
            "[b]Selected Station[/b]\n\n"
            "[b]{}[/b]{}{}\n\nCountry: {}\nCodec: {}\nBitrate: {} kbps\nLanguage: {}{}\nRadio tags: {}\nHomepage: {}".format(
                favorite_display_name(station),
                original_name_line,
                favorite_tags_line,
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
        if theme_name == self.active_theme:
            status = "active"
        elif theme_name == self.previewed_theme:
            status = "preview"
        else:
            status = "available"
        self.query_one("#details", Static).update(
            "[b]Theme Preview[/b]\n\n"
            f"[b]{theme_name}[/b]\nStatus: {status}\nFile: {Path(path).name}\n\n"
            "Highlight previews temporarily.\n"
            "Enter: apply selected theme.\n"
            "y: save active theme as default.\n"
            "Leaving the theme selector restores the last applied theme if you only previewed."
        )


    def update_playlist_details(self, tag: str, count: int) -> None:
        stations = get_by_tag(tag)
        names = [favorite_display_name(item) for item in stations[:6]]
        preview = "\n".join(f"• {name}" for name in names) if names else "No stations."
        extra = "" if len(stations) <= 6 else f"\n… and {len(stations) - 6} more"
        self.query_one("#details", Static).update(
            "[b]Dynamic Playlist[/b]\n\n"
            f"[b]#{tag}[/b]\n"
            f"Stations: {count}\n\n"
            "Enter / r: smart play random station\n"
            "f: show matching favorites\n\n"
            f"{preview}{extra}"
        )


    def update_persistent_playlist_details(self, playlist_name: str, count: int) -> None:
        preview = summarize_playlist(playlist_name)
        self.query_one("#details", Static).update(
            "[b]Persistent Playlist[/b]\n\n"
            f"[b]{playlist_name}[/b]\n"
            f"Stations: {count}\n\n"
            "Enter / r: smart play random station\n"
            "f: show playlist stations\n"
            "d: delete this playlist\n"
            "b: add selected station to a playlist from other views\n\n"
            f"{preview}"
        )


    def ensure_favorite_selected(self) -> bool:
        if self.view_mode != "favorites":
            self.set_status("Open favorites first with f to edit favorite metadata.")
            return False
        if not self.selected_station:
            self.set_status("No favorite selected.")
            return False
        if not self.station_url(self.selected_station):
            self.set_status("Selected favorite has no stable URL key.")
            return False
        return True

    def prepare_favorite_name_edit(self) -> None:
        if not self.ensure_favorite_selected():
            return
        query = self.query_one("#query", Input)
        query.value = favorite_display_name(self.selected_station or {})
        query.focus()
        self.pending_input_action = "rename_favorite"
        self.set_status("Rename favorite: edit the search field and press Enter. Leave empty to clear custom name.")

    def prepare_favorite_tags_edit(self) -> None:
        if not self.ensure_favorite_selected():
            return
        query = self.query_one("#query", Input)
        tags = self.selected_station.get("favorite_tags", []) if self.selected_station else []
        query.value = ", ".join(tags)
        query.focus()
        self.pending_input_action = "edit_favorite_tags"
        self.set_status("Edit favorite tags: comma-separated values, then press Enter. Leave empty to clear tags.")

    def prepare_favorites_tag_filter(self) -> None:
        self.view_mode = "favorites"
        query = self.query_one("#query", Input)
        query.value = self.favorite_tag_filter or ""
        query.focus()
        self.pending_input_action = "filter_favorites_by_tag"
        tags = all_favorite_tags()
        suffix = f" Existing tags: {', '.join(tags)}" if tags else " No favorite tags yet."
        self.set_status(f"Filter favorites by tag: type a tag and press Enter. Empty clears filter.{suffix}")

    def prepare_new_playlist(self) -> None:
        query = self.query_one("#query", Input)
        query.value = ""
        query.focus()
        self.pending_input_action = "create_playlist"
        self.set_status("Create playlist: type a playlist name and press Enter.")

    def prepare_add_to_playlist(self) -> None:
        if self.view_mode in {"themes", "playlists"}:
            self.set_status("Select a station first, then press b to add it to a playlist.")
            return
        if not self.selected_station:
            self.set_status("No station selected to add to a playlist.")
            return
        query = self.query_one("#query", Input)
        query.value = ""
        query.focus()
        self.pending_input_action = "add_to_playlist"
        names = [name for name, _count in playlist_counts()]
        suffix = f" Existing: {', '.join(names[:8])}" if names else " Type a new name to create one."
        self.set_status(f"Add selected station to playlist: type playlist name and press Enter.{suffix}")

    async def handle_pending_input(self, value: str) -> None:
        action = self.pending_input_action
        self.pending_input_action = None
        value = value.strip()

        if action == "filter_favorites_by_tag":
            await self.show_favorites(tag_filter=value or None)
            return

        if action == "create_playlist":
            if not value:
                self.set_status("Playlist creation cancelled: empty name.")
                return
            created = create_playlist(value)
            await self.show_playlists()
            self.set_status(f"Created playlist: {value}" if created else f"Playlist already exists: {value}")
            return

        if action == "add_to_playlist":
            if not self.selected_station:
                self.set_status("No station selected to add to a playlist.")
                return
            if not value:
                self.set_status("Add to playlist cancelled: empty playlist name.")
                return
            added = add_station_to_playlist(value, self.selected_station)
            name = favorite_display_name(self.selected_station)
            self.set_status(f"Added {name} to playlist: {value}" if added else f"{name} is already in playlist: {value}")
            return

        if not self.selected_station:
            self.set_status("No favorite selected.")
            return

        key = self.station_url(self.selected_station)
        if not key:
            self.set_status("Selected favorite has no stable URL key.")
            return

        if action == "rename_favorite":
            update_favorite(key, custom_name=value or None)
            await self.show_favorites(tag_filter=self.favorite_tag_filter)
            self.set_status("Favorite renamed." if value else "Favorite custom name cleared.")
            return

        if action == "edit_favorite_tags":
            tags = [tag.strip() for tag in value.split(",") if tag.strip()]
            update_favorite(key, favorite_tags=tags)
            await self.show_favorites(tag_filter=self.favorite_tag_filter)
            self.set_status(f"Favorite tags updated: {', '.join(tags)}" if tags else "Favorite tags cleared.")
            return

        self.set_status("Unknown input action.")


    def restore_playback_state(self) -> None:
        """Load persisted playback metadata and preferences."""
        state = get_playback_state()
        last_station = state.get("last_station")
        self.last_station = last_station if isinstance(last_station, dict) else None
        self.selected_station = self.last_station
        volume = state.get("volume")
        self.restored_volume = volume if isinstance(volume, (int, float)) else None
        muted = state.get("muted")
        self.restored_muted = bool(muted) if isinstance(muted, bool) else None

    def apply_restored_playback_preferences(self) -> None:
        """Apply saved volume and mute values to a newly started mpv session."""
        if self.restored_volume is not None:
            try:
                self.player.set_volume(self.restored_volume)
            except Exception:
                pass
        if self.restored_muted is not None:
            try:
                self.player.set_mute(self.restored_muted)
            except Exception:
                pass

    def persist_player_state(self, last_station: dict[str, Any] | None = None) -> None:
        """Persist last station, volume and mute state when available."""
        volume = None
        muted = None
        try:
            state = self.player.get_state()
            if isinstance(state.get("volume"), (int, float)):
                volume = state.get("volume")
                self.restored_volume = volume
            if isinstance(state.get("muted"), bool):
                muted = state.get("muted")
                self.restored_muted = muted
        except Exception:
            pass
        save_playback_state(last_station=last_station, volume=volume, muted=muted)

    def station_url(self, station: dict[str, Any] | None) -> str | None:
        if not station:
            return None
        return station_key(station)

    def current_station_url(self) -> str | None:
        return self.station_url(self.playing_station)

    @staticmethod
    def volume_bar(volume: int | float | None, width: int = 10) -> str:
        """Return a compact visual volume bar for the Now Playing panel."""
        if not isinstance(volume, (int, float)):
            return "░" * width
        safe_volume = max(0, min(100, int(round(volume))))
        filled = int(round((safe_volume / 100) * width))
        return "█" * filled + "░" * (width - filled)

    def _side_panel_text_width(self) -> int:
        """Estimate usable text width for the right panel.

        The right panel is roughly one third of the content area. Keeping this
        adaptive avoids long station names taking over the whole Now Playing box
        on smaller terminals.
        """
        try:
            terminal_width = int(self.size.width)
        except Exception:
            terminal_width = 120

        # Subtract borders/padding and clamp to sensible limits.
        estimated = (terminal_width // 3) - 8
        return max(24, min(56, estimated))

    @staticmethod
    def _ellipsize(value: str, max_length: int) -> str:
        value = " ".join(str(value or "").split())
        if len(value) <= max_length:
            return value
        if max_length <= 1:
            return "…"
        return value[: max_length - 1].rstrip() + "…"

    def _wrap_short(self, value: str, width: int, max_lines: int = 2) -> str:
        value = " ".join(str(value or "").split())
        if not value:
            return "?"

        lines = textwrap.wrap(value, width=max(12, width), break_long_words=False, replace_whitespace=True)
        if not lines:
            return "?"
        if len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = self._ellipsize(lines[-1], max(12, width))
        return "\n".join(lines)

    def ensure_now_playing_layout(self) -> None:
        """Keep the Now Playing panel readable across themes and terminal sizes."""
        try:
            now_playing = self.query_one("#now-playing", Static)
            now_playing.styles.height = 12
            now_playing.styles.min_height = 12
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
            if self.last_station:
                width = self._side_panel_text_width()
                name = self._wrap_short(favorite_display_name(self.last_station), width=width, max_lines=2)
                country = self._ellipsize(self.last_station.get("country") or "Unknown country", max(18, width // 2))
                bitrate = self.last_station.get("bitrate") or "?"
                codec = self.last_station.get("codec") or "?"
                now_playing.update(
                    "[b]Now Playing[/b]\n"
                    "Nothing playing.\n"
                    "[b]Last Station[/b]\n"
                    f"{name}\n"
                    f"{country} • {bitrate} kbps • {codec}\n"
                    "Press [b]l[/b] to play last station."
                )
            else:
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
        volume_value = int(round(volume)) if isinstance(volume, (int, float)) else None
        volume_label = f"{volume_value}%" if volume_value is not None else "?"
        volume_bar = self.volume_bar(volume_value, width=10)
        tags = station.get("tags") or "no tags"

        width = self._side_panel_text_width()
        name = self._wrap_short(favorite_display_name(station), width=width, max_lines=2)
        country = self._ellipsize(station.get("country") or "Unknown country", max(18, width // 2))
        bitrate = station.get("bitrate") or "?"
        codec = station.get("codec") or "?"
        tags_line = self._ellipsize(tags, max(32, width + 10))

        now_playing.update(
            "[b]Now Playing[/b]\n"
            f"{status_icon} {status_label} • {mute_label}\n"
            f"Volume {volume_bar} {volume_label}\n"
            "[b]Station[/b]\n"
            f"{name}\n"
            "[b]Info[/b]\n"
            f"{country} • {bitrate} kbps • {codec}\n"
            f"[b]Tags[/b] {tags_line}"
        )

    def update_mode_title(self, title: str) -> None:
        self.query_one("#mode-title", Static).update(title)

    def set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)


def run_tui(theme: str | None = None, player_name: str = "mpv") -> None:
    FluxTunerTUI(theme=theme, player_name=player_name).run()


    def show_data_usage(self):
        try:
            print(self.data_usage_text())
        except Exception:
            pass
