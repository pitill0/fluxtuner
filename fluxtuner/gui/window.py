"""Experimental GTK desktop window for FluxTuner."""

from __future__ import annotations

import threading
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from fluxtuner.core.api import search_stations_filtered
from fluxtuner.players import create_player
from fluxtuner.core.data_usage import DataUsageTracker, format_usage_line
from fluxtuner.core.favorites import (
    add_favorite,
    favorite_display_name,
    load_favorites,
    remove_favorite,
    station_key,
    update_favorite,
)

DEFAULT_SEARCH = "fip"


class MainWindow(Gtk.ApplicationWindow):
    """Small GTK GUI MVP: search stations, list results and play selection."""

    def __init__(self, app: Gtk.Application, player_name: str = "mpv") -> None:
        super().__init__(application=app)
        self.set_title("FluxTuner")
        self.set_default_size(980, 620)
        self.set_size_request(520, 420)

        self.player = create_player(player_name)
        self.usage_tracker = DataUsageTracker()
        self._usage_timer_id: int | None = None
        self._player_state_timer_id: int | None = None
        self.stations: list[dict[str, Any]] = []
        self.selected_station: dict[str, Any] | None = None
        self.current_station: dict[str, Any] | None = None
        self.last_search_results: list[dict[str, Any]] = []
        self.active_playlist_tag: str | None = None
        self.favorite_urls = self._favorite_url_set()

        root = self._build_root()
        self.set_child(root)
        self.connect("close-request", self.on_close_request)

        self._build_header(root)
        self._build_search_bar(root)
        self._build_content(root)
        self._build_bottom_playback_bar(root)
        self._build_status_bar(root)

    def _build_root(self) -> Gtk.Box:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)
        root.set_hexpand(True)
        root.set_vexpand(True)
        return root

    def _build_header(self, root: Gtk.Box) -> None:
        header = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        root.append(header)

        title = Gtk.Label(label="FluxTuner")
        title.set_xalign(0)
        title.add_css_class("title-1")
        header.append(title)

        subtitle = Gtk.Label(label="Experimental GTK desktop GUI")
        subtitle.set_xalign(0)
        subtitle.add_css_class("dim-label")
        header.append(subtitle)

    def _build_search_bar(self, root: Gtk.Box) -> None:
        search_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        search_bar.set_hexpand(True)
        root.append(search_bar)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search station, genre or tag…")
        self.search_entry.set_text(DEFAULT_SEARCH)
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self.on_search_clicked)
        search_bar.append(self.search_entry)

        self.country_entry = Gtk.Entry()
        self.country_entry.set_hexpand(True)
        self.country_entry.set_placeholder_text("Country")
        self.country_entry.set_width_chars(12)
        self.country_entry.connect("activate", self.on_search_clicked)
        search_bar.append(self.country_entry)

        self.min_bitrate_entry = Gtk.Entry()
        self.min_bitrate_entry.set_hexpand(False)
        self.min_bitrate_entry.set_width_chars(8)
        self.min_bitrate_entry.set_placeholder_text("Min kbps")
        self.min_bitrate_entry.connect("activate", self.on_search_clicked)
        search_bar.append(self.min_bitrate_entry)

        search_button = Gtk.Button(label="Search")
        search_button.connect("clicked", self.on_search_clicked)
        search_bar.append(search_button)

    def _build_content(self, root: Gtk.Box) -> None:
        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.set_hexpand(True)
        content.set_vexpand(True)
        root.append(content)

        self._build_results_table(content)
        self._build_side_panel(content)

    def _build_results_table(self, content: Gtk.Box) -> None:
        table_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        table_box.set_hexpand(True)
        table_box.set_vexpand(True)
        content.append(table_box)

        table_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        table_header.add_css_class("heading")
        table_box.append(table_header)

        self._append_cell(table_header, "Status", 6)
        self._append_cell(table_header, "Name", 32, expand=True)
        self._append_cell(table_header, "Country", 14)
        self._append_cell(table_header, "Tags", 28, expand=True)
        self._append_cell(table_header, "Codec", 8)
        self._append_cell(table_header, "Kbps", 6)

        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)
        table_box.append(scroller)

        self.results_list = Gtk.ListBox()
        self.results_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.results_list.set_hexpand(True)
        self.results_list.set_vexpand(True)
        self.results_list.connect("row-selected", self.on_row_selected)
        scroller.set_child(self.results_list)

    def _append_section_title(self, container: Gtk.Box, text: str) -> None:
        title = Gtk.Label(label=text)
        title.set_xalign(0)
        title.add_css_class("heading")
        container.append(title)

    def _make_value_label(self, text: str = "—", *, selectable: bool = False) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_wrap(True)
        label.set_selectable(selectable)
        label.add_css_class("dim-label")
        return label

    def _append_detail_row(self, container: Gtk.Box, title: str) -> Gtk.Label:
        title_label = Gtk.Label(label=title)
        title_label.set_xalign(0)
        title_label.add_css_class("caption-heading")
        container.append(title_label)

        value_label = self._make_value_label()
        container.append(value_label)

        return value_label

    def _build_side_panel(self, content: Gtk.Box) -> None:
        side_scroller = Gtk.ScrolledWindow()
        side_scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        side_scroller.set_size_request(300, -1)
        side_scroller.set_hexpand(False)
        side_scroller.set_vexpand(True)
        content.append(side_scroller)

        side_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        side_panel.set_margin_end(6)
        side_scroller.set_child(side_panel)

        self._append_section_title(side_panel, "Now Playing")

        self.now_playing_label = Gtk.Label(label="Nothing playing")
        self.now_playing_label.set_xalign(0)
        self.now_playing_label.set_wrap(True)
        self.now_playing_label.set_selectable(True)
        self.now_playing_label.add_css_class("title-3")
        side_panel.append(self.now_playing_label)

        self._append_section_title(side_panel, "Station details")

        details_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        details_box.set_hexpand(True)
        side_panel.append(details_box)

        self.country_detail_label = self._append_detail_row(details_box, "Country")
        self.codec_detail_label = self._append_detail_row(details_box, "Codec")
        self.bitrate_detail_label = self._append_detail_row(details_box, "Bitrate")
        self.tags_detail_label = self._append_detail_row(details_box, "Tags")

        self._append_section_title(side_panel, "Data usage")

        self.data_usage_label = self._make_value_label(
            "0.0 MB session · 0.0 MB today · 0.0 MB/h est.",
            selectable=True,
        )
        side_panel.append(self.data_usage_label)

        self.player_state_label = self._make_value_label("Player: stopped", selectable=True)
        side_panel.append(self.player_state_label)

        self._build_favorite_controls(side_panel)
        self._build_playlist_controls(side_panel)

        hint = Gtk.Label(label="Tip: select a station and use ▶ Play below, or double-click it.")
        hint.set_xalign(0)
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        side_panel.append(hint)

    def _build_bottom_playback_bar(self, root: Gtk.Box) -> None:
        playback_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        playback_bar.set_hexpand(True)
        playback_bar.set_halign(Gtk.Align.CENTER)
        playback_bar.set_valign(Gtk.Align.CENTER)
        playback_bar.set_homogeneous(False)
        root.append(playback_bar)

        self.play_button = Gtk.Button(label="▶ Play")
        self.play_button.set_size_request(112, -1)
        self.play_button.set_hexpand(False)
        self.play_button.set_tooltip_text("Play selected station / stop playback")
        self.play_button.connect("clicked", self.on_play_clicked)
        playback_bar.append(self.play_button)

        self.mute_button = Gtk.Button(label="🔊")
        self.mute_button.set_tooltip_text("Mute / unmute")
        self.mute_button.connect("clicked", self.on_mute_clicked)
        playback_bar.append(self.mute_button)

        self.volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume_scale.set_value(50)
        self.volume_scale.set_size_request(180, -1)
        self.volume_scale.set_hexpand(False)
        self.volume_scale.set_draw_value(False)
        self.volume_scale.set_tooltip_text("Volume")
        self.volume_scale.connect("value-changed", self.on_volume_scale_changed)
        playback_bar.append(self.volume_scale)

    def _build_favorite_controls(self, side_panel: Gtk.Box) -> None:
        self._append_section_title(side_panel, "Favorites")

        favorite_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        favorite_controls.set_hexpand(True)
        side_panel.append(favorite_controls)

        self.favorite_tags_entry = Gtk.Entry()
        self.favorite_tags_entry.set_placeholder_text("Favorite tags, comma separated")
        self.favorite_tags_entry.set_hexpand(True)
        favorite_controls.append(self.favorite_tags_entry)

        self.add_favorite_button = Gtk.Button(label="★ Add favorite")
        self.add_favorite_button.set_tooltip_text("Add selected station to favorites")
        self.add_favorite_button.connect("clicked", self.on_add_favorite_clicked)
        favorite_controls.append(self.add_favorite_button)

        self.remove_favorite_button = Gtk.Button(label="☆ Remove favorite")
        self.remove_favorite_button.set_tooltip_text("Remove selected station from favorites")
        self.remove_favorite_button.connect("clicked", self.on_remove_favorite_clicked)
        favorite_controls.append(self.remove_favorite_button)

        self.show_favorites_button = Gtk.Button(label="★ Show favorites")
        self.show_favorites_button.set_tooltip_text("Show favorite stations")
        self.show_favorites_button.connect("clicked", self.on_show_favorites_clicked)
        favorite_controls.append(self.show_favorites_button)



    def _station_tag_values(self, station: dict[str, Any]) -> set[str]:
        values: set[str] = set()

        raw_favorite_tags = station.get("favorite_tags", [])
        if isinstance(raw_favorite_tags, list):
            values.update(str(tag).strip().lower() for tag in raw_favorite_tags if str(tag).strip())

        raw_stream_tags = station.get("tags", "")
        if isinstance(raw_stream_tags, str):
            values.update(tag.strip().lower() for tag in raw_stream_tags.split(',') if tag.strip())
        elif isinstance(raw_stream_tags, list):
            values.update(str(tag).strip().lower() for tag in raw_stream_tags if str(tag).strip())

        return values

    def _favorites_matching_tag(self, tag: str) -> list[dict[str, Any]]:
        clean_tag = tag.strip().lower()
        if not clean_tag:
            return load_favorites()
        return [
            station
            for station in load_favorites()
            if clean_tag in self._station_tag_values(station)
        ]

    def _all_gui_tags(self) -> list[str]:
        values: set[str] = set()
        for station in load_favorites():
            values.update(self._station_tag_values(station))
        return sorted(values)
    def _build_playlist_controls(self, side_panel: Gtk.Box) -> None:
        self._append_section_title(side_panel, "Playlists")

        playlist_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        playlist_controls.set_hexpand(True)
        side_panel.append(playlist_controls)

        self.playlist_status_label = self._make_value_label("No playlist filter", selectable=True)
        playlist_controls.append(self.playlist_status_label)

        self.playlist_tag_entry = Gtk.Entry()
        self.playlist_tag_entry.set_placeholder_text("Tag")
        self.playlist_tag_entry.set_hexpand(True)
        self.playlist_tag_entry.connect("activate", self.on_show_tag_playlist_clicked)
        playlist_controls.append(self.playlist_tag_entry)

        playlist_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        playlist_buttons.set_hexpand(True)
        playlist_controls.append(playlist_buttons)

        self.show_tag_playlist_button = Gtk.Button(label="Show")
        self.show_tag_playlist_button.set_tooltip_text("Show favorites matching the selected tag")
        self.show_tag_playlist_button.connect("clicked", self.on_show_tag_playlist_clicked)
        playlist_buttons.append(self.show_tag_playlist_button)

        self.random_tag_button = Gtk.Button(label="Random")
        self.random_tag_button.set_tooltip_text("Play a random favorite from the selected tag")
        self.random_tag_button.connect("clicked", self.on_random_tag_clicked)
        playlist_buttons.append(self.random_tag_button)

        self.show_tags_button = Gtk.Button(label="Tags")
        self.show_tags_button.set_tooltip_text("Show available favorite tags")
        self.show_tags_button.connect("clicked", self.on_show_tags_clicked)
        playlist_buttons.append(self.show_tags_button)

        self.clear_playlist_button = Gtk.Button(label="Clear")
        self.clear_playlist_button.set_tooltip_text("Clear playlist filter and restore last search results")
        self.clear_playlist_button.connect("clicked", self.on_clear_playlist_filter_clicked)
        playlist_buttons.append(self.clear_playlist_button)

    def _build_status_bar(self, root: Gtk.Box) -> None:
        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_hexpand(True)
        self.status_label.props.ellipsize = Pango.EllipsizeMode.END
        self.status_label.set_xalign(0)
        self.status_label.set_wrap(True)
        root.append(self.status_label)

    def _favorite_url_set(self) -> set[str]:
        return {key for item in load_favorites() if (key := station_key(item))}

    def _is_favorite_station(self, station: dict[str, Any]) -> bool:
        key = station_key(station)
        return bool(key and key in self.favorite_urls)

    def _refresh_favorite_cache(self) -> None:
        self.favorite_urls = self._favorite_url_set()

    def _station_display_name(self, station: dict[str, Any]) -> str:
        if self._is_favorite_station(station):
            return favorite_display_name(station)
        return str(station.get("name") or "Unknown station")

    def _append_cell(
        self,
        container: Gtk.Box,
        text: str,
        width_chars: int,
        *,
        expand: bool = False,
    ) -> Gtk.Label:
        label = Gtk.Label(label=text)
        label.set_xalign(0)
        label.set_width_chars(width_chars)
        label.set_max_width_chars(width_chars)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_hexpand(expand)
        container.append(label)
        return label

    def _station_url(self, station: dict[str, Any]) -> str | None:
        return station.get("url_resolved") or station.get("url")

    def _station_label(self, station: dict[str, Any]) -> str:
        name = station.get("name") or "Unknown station"
        country = station.get("country") or "Unknown"
        return f"{name}\n{country}"

    def _station_detail(self, station: dict[str, Any]) -> str:
        codec = station.get("codec") or "?"
        bitrate = station.get("bitrate") or 0
        tags = station.get("tags") or "No tags"
        return f"{codec} | {bitrate} kbps\n{tags}"

    def _clear_results(self) -> None:
        child = self.results_list.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.results_list.remove(child)
            child = next_child

    def _is_current_station(self, station: dict[str, Any]) -> bool:
        if not self.current_station:
            return False
        return self._station_url(station) == self._station_url(self.current_station)

    def _render_results(self) -> None:
        selected_url = self._station_url(self.selected_station) if self.selected_station else None
        current_url = self._station_url(self.current_station) if self.current_station else None
        preferred_url = selected_url or current_url

        self._clear_results()

        row_to_select: Gtk.ListBoxRow | None = None

        for station in self.stations:
            row = Gtk.ListBoxRow()
            if self._is_current_station(station):
                row.add_css_class("suggested-action")
            row.station = station  # type: ignore[attr-defined]

            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row_box.set_margin_top(6)
            row_box.set_margin_bottom(6)
            row_box.set_margin_start(6)
            row_box.set_margin_end(6)

            marker_parts = []
            if self._is_current_station(station):
                marker_parts.append("▶")
            if self._is_favorite_station(station):
                marker_parts.append("★")
            marker = "".join(marker_parts)
            self._append_cell(row_box, marker, 6)
            self._append_cell(row_box, self._station_display_name(station), 32, expand=True)
            self._append_cell(row_box, station.get("country") or "Unknown", 14)
            self._append_cell(row_box, station.get("tags") or "", 28, expand=True)
            self._append_cell(row_box, station.get("codec") or "", 8)
            self._append_cell(row_box, str(station.get("bitrate") or 0), 6)

            if preferred_url and self._station_url(station) == preferred_url:
                row_to_select = row

            double_click = Gtk.GestureClick()
            double_click.set_button(0)
            double_click.connect("pressed", self.on_row_double_click, row)
            row.add_controller(double_click)

            row.set_child(row_box)
            self.results_list.append(row)

        if row_to_select is not None:
            self.results_list.select_row(row_to_select)
            self.selected_station = getattr(row_to_select, "station", None)
        elif self.stations and self.selected_station is None:
            first_row = self.results_list.get_row_at_index(0)
            self.results_list.select_row(first_row)
            self.selected_station = getattr(first_row, "station", None) if first_row else None
        elif not self.stations:
            self.selected_station = None

        self._update_favorite_buttons()

    def on_search_clicked(self, _widget: Gtk.Widget) -> None:
        query = self.search_entry.get_text().strip()
        country = self.country_entry.get_text().strip() or None
        min_bitrate_text = self.min_bitrate_entry.get_text().strip()
        min_bitrate = int(min_bitrate_text) if min_bitrate_text.isdigit() else None

        self.status_label.set_text("Searching…")

        def worker() -> None:
            try:
                stations = search_stations_filtered(
                    query=query or None,
                    country=country,
                    min_bitrate=min_bitrate,
                    limit=50,
                )
            except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
                GLib.idle_add(self._search_failed, str(exc))
                return

            GLib.idle_add(self._search_finished, stations)

        threading.Thread(target=worker, daemon=True).start()

    def _search_failed(self, message: str) -> bool:
        self.status_label.set_text(f"Search failed: {message}")
        return False

    def _search_finished(self, stations: list[dict[str, Any]]) -> bool:
        self.active_playlist_tag = None
        self.last_search_results = stations
        self.stations = stations
        self._render_results()
        self._update_playlist_status()
        count = len(stations)
        self.status_label.set_text(f"Found {count} station(s).")
        return False

    def on_row_double_click(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        _x: float,
        _y: float,
        row: Gtk.ListBoxRow,
    ) -> None:
        """Play a station only on an explicit double click."""
        if n_press != 2:
            return

        self.selected_station = getattr(row, "station", None)
        self.play_selected_station()

    def on_row_selected(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            self.selected_station = None
            self._update_favorite_buttons()
            return
        self.selected_station = getattr(row, "station", None)
        self._update_favorite_buttons()

    def _has_active_playback(self) -> bool:
        """Return True when there is an active player process."""
        is_playing = getattr(self.player, "is_playing", None)
        if not callable(is_playing):
            return self.current_station is not None

        try:
            return bool(is_playing())
        except Exception:
            return self.current_station is not None

    def _playback_command_failed(self, action: str, exc: Exception) -> None:
        self.status_label.set_text(f"{action} failed: {exc}")

    def _send_player_command(self, command: list[Any]) -> bool:
        """Send a low-level command when the player backend supports it."""
        player_command = getattr(self.player, "command", None)
        if not callable(player_command):
            return False

        player_command(command)
        return True

    def on_play_pause_clicked(self, _button: Gtk.Button) -> None:
        if self._has_active_playback():
            self.toggle_pause()
            return

        self.play_selected_station()

    def on_play_clicked(self, _button: Gtk.Button) -> None:
        if self._has_active_playback():
            self.on_stop_clicked(_button)
            return
        self.play_selected_station()

    def play_selected_station(self) -> None:
        if not self.selected_station:
            self.status_label.set_text("Select a station first.")
            return

        url = self._station_url(self.selected_station)
        if not url:
            self.status_label.set_text("Selected station has no playable URL.")
            return

        try:
            self.status_label.set_text("Buffering…")
            self.player.play(url)
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self.status_label.set_text(f"Playback failed: {exc}")
            return

        self.current_station = self.selected_station
        self.usage_tracker.start(self.current_station)
        self.update_now_playing()
        self.update_data_usage()
        self.update_player_state()
        self._update_play_pause_button()
        self._ensure_usage_timer()
        self._ensure_player_state_timer()
        self._update_play_pause_button()
        self.status_label.set_text("Playing")
        self._render_results()

    def update_now_playing(self) -> None:
        if not self.current_station:
            self.now_playing_label.set_text("Nothing playing")
            if hasattr(self, "country_detail_label"):
                self.country_detail_label.set_text("—")
                self.codec_detail_label.set_text("—")
                self.bitrate_detail_label.set_text("—")
                self.tags_detail_label.set_text("—")
            return

        station = self.current_station

        self.now_playing_label.set_text(station.get("name") or "Unknown station")
        self.country_detail_label.set_text(station.get("country") or "Unknown")
        self.codec_detail_label.set_text(station.get("codec") or "?")
        self.bitrate_detail_label.set_text(f"{station.get('bitrate') or 0} kbps")
        self.tags_detail_label.set_text(station.get("tags") or "No tags")

    def toggle_pause(self) -> None:
        try:
            if not self._send_player_command(["cycle", "pause"]):
                self.player.toggle_pause()
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self._playback_command_failed("Pause", exc)
            return

        self.update_player_state()
        self.status_label.set_text("Toggled pause/resume")

    def on_pause_clicked(self, _button: Gtk.Button) -> None:
        if not self._has_active_playback():
            self.status_label.set_text("Nothing is playing.")
            return

        try:
            if not self._send_player_command(["cycle", "pause"]):
                self.player.toggle_pause()
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self._playback_command_failed("Pause", exc)
            return

        self.update_player_state()
        self.status_label.set_text("Toggled pause/resume")

    def on_mute_clicked(self, _button: Gtk.Button) -> None:
        if not self._has_active_playback():
            self.status_label.set_text("Nothing is playing.")
            return

        try:
            self.player.toggle_mute()
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self._playback_command_failed("Mute", exc)
            return

        self.update_player_state()
        self.status_label.set_text("Toggled mute")

    def on_volume_scale_changed(self, scale: Gtk.Scale) -> None:
        if not self._has_active_playback():
            return

        volume = int(round(scale.get_value()))

        try:
            set_volume = getattr(self.player, "set_volume", None)
            if callable(set_volume):
                set_volume(volume)
            else:
                self._send_player_command(["set_property", "volume", volume])
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self._playback_command_failed("Volume", exc)
            return

        self.update_player_state()


    def _favorite_tags_from_entry(self) -> list[str]:
        if not hasattr(self, "favorite_tags_entry"):
            return []
        raw_value = self.favorite_tags_entry.get_text().strip()
        if not raw_value:
            return []
        return sorted({tag.strip() for tag in raw_value.split(',') if tag.strip()})

    def _update_favorite_buttons(self) -> None:
        if not hasattr(self, "add_favorite_button"):
            return

        has_selection = self.selected_station is not None
        is_favorite = bool(has_selection and self._is_favorite_station(self.selected_station))

        self.add_favorite_button.set_sensitive(has_selection and not is_favorite)
        self.remove_favorite_button.set_sensitive(has_selection and is_favorite)

        if hasattr(self, "favorite_tags_entry"):
            self.favorite_tags_entry.set_sensitive(has_selection and not is_favorite)

    def on_add_favorite_clicked(self, _button: Gtk.Button) -> None:
        if not self.selected_station:
            self.status_label.set_text("Select a station first.")
            self._update_favorite_buttons()
            return

        key = station_key(self.selected_station)
        if not key:
            self.status_label.set_text("Selected station has no favorite URL.")
            self._update_favorite_buttons()
            return

        tags = self._favorite_tags_from_entry()

        if add_favorite(self.selected_station):
            if tags:
                update_favorite(key, favorite_tags=tags)
            self._refresh_favorite_cache()
            if hasattr(self, "favorite_tags_entry"):
                self.favorite_tags_entry.set_text("")
            self._render_results()
            self._update_favorite_buttons()
            tag_suffix = f" with tags: {', '.join(tags)}" if tags else ""
            self.status_label.set_text(f"Added to favorites{tag_suffix}.")
            return

        self.status_label.set_text("Station is already in favorites or has no URL.")
        self._update_favorite_buttons()

    def on_remove_favorite_clicked(self, _button: Gtk.Button) -> None:
        if not self.selected_station:
            self.status_label.set_text("Select a station first.")
            self._update_favorite_buttons()
            return

        key = station_key(self.selected_station)
        if not key:
            self.status_label.set_text("Selected station has no favorite URL.")
            self._update_favorite_buttons()
            return

        if remove_favorite(key):
            self._refresh_favorite_cache()
            self.status_label.set_text("Removed from favorites.")
            if all(self._is_favorite_station(station) for station in self.stations):
                self.stations = load_favorites()
                self.selected_station = None
            self._render_results()
            self._update_favorite_buttons()
            return

        self.status_label.set_text("Selected station is not in favorites.")
        self._update_favorite_buttons()

    def on_show_favorites_clicked(self, _button: Gtk.Button) -> None:
        favorites = load_favorites()
        self.active_playlist_tag = None
        self._refresh_favorite_cache()
        self.stations = favorites
        self.selected_station = None
        self._render_results()
        self._update_favorite_buttons()
        self._update_playlist_status()
        self.status_label.set_text(f"Loaded {len(favorites)} favorite station(s).")

    def _update_playlist_status(self) -> None:
        if not hasattr(self, "playlist_status_label"):
            return
        if self.active_playlist_tag:
            self.playlist_status_label.set_text(f"Active tag: {self.active_playlist_tag}")
        else:
            self.playlist_status_label.set_text("No playlist filter")

    def _playlist_tag_value(self) -> str:
        if not hasattr(self, "playlist_tag_entry"):
            return ""
        return self.playlist_tag_entry.get_text().strip()

    def on_show_tags_clicked(self, _button: Gtk.Button) -> None:
        tags = self._all_gui_tags()
        if not tags:
            self.status_label.set_text("No tags found in favorites yet.")
            return
        self.status_label.set_text("Tags: " + ", ".join(tags))

    def on_show_tag_playlist_clicked(self, _widget: Gtk.Widget) -> None:
        tag = self._playlist_tag_value()
        if not tag:
            tags = self._all_gui_tags()
            if tags:
                self.status_label.set_text("Type a tag. Available: " + ", ".join(tags))
            else:
                self.status_label.set_text("No tags found in favorites yet.")
            return

        stations = self._favorites_matching_tag(tag)
        self.active_playlist_tag = tag
        self._refresh_favorite_cache()
        self.stations = stations
        self.selected_station = None
        self._render_results()
        self._update_favorite_buttons()
        self._update_playlist_status()
        self.status_label.set_text(f"Loaded {len(stations)} favorite station(s) for tag: {tag}")

    def on_random_tag_clicked(self, _button: Gtk.Button) -> None:
        import random

        tag = self._playlist_tag_value()
        if not tag:
            tags = self._all_gui_tags()
            if tags:
                self.status_label.set_text("Type a tag first. Available: " + ", ".join(tags))
            else:
                self.status_label.set_text("No tags found in favorites yet.")
            return

        stations = self._favorites_matching_tag(tag)
        if not stations:
            self.status_label.set_text(f"No favorite stations found for tag: {tag}")
            return

        self.active_playlist_tag = tag
        self._refresh_favorite_cache()
        self.stations = stations
        self.selected_station = random.choice(stations)
        self._render_results()
        self._update_playlist_status()
        self.play_selected_station()


    def on_clear_playlist_filter_clicked(self, _button: Gtk.Button) -> None:
        self.active_playlist_tag = None
        if hasattr(self, "playlist_tag_entry"):
            self.playlist_tag_entry.set_text("")

        if self.last_search_results:
            self.stations = self.last_search_results
            self.status_label.set_text(f"Restored {len(self.stations)} search result(s).")
        else:
            self.stations = []
            self.status_label.set_text("Playlist filter cleared.")

        self.selected_station = None
        self._render_results()
        self._update_favorite_buttons()
        self._update_playlist_status()

    def on_stop_clicked(self, _button: Gtk.Button) -> None:
        self._stop_usage_timer()
        self._stop_player_state_timer()
        self.player.stop()
        self.usage_tracker.stop()
        self.update_data_usage()
        self.current_station = None
        self.update_now_playing()
        self.update_player_state()
        self._update_play_pause_button()
        self.status_label.set_text("Stopped")
        self._render_results()

    def _ensure_player_state_timer(self) -> None:
        """Refresh the player state label while playback is active."""
        if self._player_state_timer_id is None:
            self._player_state_timer_id = GLib.timeout_add_seconds(1, self._refresh_player_state)

    def _stop_player_state_timer(self) -> None:
        """Stop the periodic player state refresh."""
        if self._player_state_timer_id is not None:
            GLib.source_remove(self._player_state_timer_id)
            self._player_state_timer_id = None

    def _refresh_player_state(self) -> bool:
        """GTK timeout callback used while a player process is active."""
        if not self._has_active_playback():
            self._player_state_timer_id = None
            self.update_player_state()
            return False

        self.update_player_state()
        return True

    def _update_mute_button(self, muted: bool | None = None) -> None:
        if not hasattr(self, "mute_button"):
            return

        if muted is None:
            muted = False

        self.mute_button.set_label("🔇" if muted else "🔊")

    def update_player_state(self) -> None:
        if not hasattr(self, "player_state_label"):
            return

        if not self._has_active_playback():
            self.player_state_label.set_text("Player: stopped")
            self._update_play_pause_button()
            return

        get_state = getattr(self.player, "get_state", None)
        if not callable(get_state):
            self.player_state_label.set_text("Player: playing")
            self._update_play_pause_button()
            return

        try:
            state = get_state() or {}
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self.player_state_label.set_text(f"Player: state unavailable ({exc})")
            self._update_play_pause_button()
            return

        if not state.get("playing"):
            self.player_state_label.set_text("Player: stopped")
            self._update_play_pause_button()
            return

        is_muted = bool(state.get("muted"))
        playback = "paused" if state.get("paused") else "playing"
        muted = "muted" if is_muted else "sound on"
        volume = state.get("volume")
        self._update_mute_button(is_muted)

        if isinstance(volume, (int, float)):
            volume_value = int(round(volume))
            volume_text = f"{volume_value}%"
            if hasattr(self, "volume_scale") and int(round(self.volume_scale.get_value())) != volume_value:
                self.volume_scale.handler_block_by_func(self.on_volume_scale_changed)
                self.volume_scale.set_value(volume_value)
                self.volume_scale.handler_unblock_by_func(self.on_volume_scale_changed)
        else:
            volume_text = "unknown volume"

        self.player_state_label.set_text(f"Player: {playback} · {muted} · {volume_text}")
        self._update_play_pause_button()

    def _update_play_pause_button(self) -> None:
        if not hasattr(self, "play_button"):
            return
        if self._has_active_playback():
            self.play_button.set_label("■ Stop")
            self.play_button.set_tooltip_text("Stop playback")
        else:
            self.play_button.set_label("▶ Play")
            self.play_button.set_tooltip_text("Play selected station")

    def _ensure_usage_timer(self) -> None:
        """Refresh the data usage label while playback is active."""
        if self._usage_timer_id is None:
            self._usage_timer_id = GLib.timeout_add_seconds(1, self._refresh_data_usage)

    def _stop_usage_timer(self) -> None:
        """Stop the periodic data usage refresh."""
        if self._usage_timer_id is not None:
            GLib.source_remove(self._usage_timer_id)
            self._usage_timer_id = None

    def _refresh_data_usage(self) -> bool:
        """GTK timeout callback used while a station is playing."""
        if self.current_station is None:
            self._usage_timer_id = None
            return False

        self.update_data_usage()
        return True

    def on_close_request(self, _window: Gtk.Window) -> bool:
        """Persist usage and stop mpv when closing the GTK window."""
        self._stop_usage_timer()
        self._stop_player_state_timer()
        self.usage_tracker.stop()
        try:
            self.player.stop()
        except Exception:
            pass
        return False

    def update_data_usage(self) -> None:
        if hasattr(self, "data_usage_label"):
            self.data_usage_label.set_text(format_usage_line(self.usage_tracker.snapshot()).replace("Data: ", ""))
