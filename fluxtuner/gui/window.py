"""Experimental GTK desktop window for FluxTuner."""

from __future__ import annotations

import threading
from contextlib import suppress
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from fluxtuner.config import get_playback_state, save_playback_state  # noqa: E402
from fluxtuner.core.api import search_stations_filtered  # noqa: E402
from fluxtuner.core.data_usage import DataUsageTracker, format_usage_line  # noqa: E402
from fluxtuner.core.favorites import (  # noqa: E402
    add_favorite,
    all_favorite_tags,
    favorite_display_name,
    filter_favorites_by_tag,
    load_favorites,
    remove_favorite,
    update_favorite,
)
from fluxtuner.core.stations import (  # noqa: E402
    same_station,
    station_key,
    station_tags,
    station_url,
)
from fluxtuner.core.stream_metadata import fetch_stream_metadata  # noqa: E402
from fluxtuner.players import create_player, selected_player_name  # noqa: E402


class MainWindow(Gtk.ApplicationWindow):
    """Small GTK GUI MVP: search stations, list results and play selection."""

    def __init__(self, app: Gtk.Application, player_name: str = "mpv") -> None:
        super().__init__(application=app)
        self.set_title("FluxTuner")
        self.set_default_size(980, 620)
        self.set_size_request(520, 420)

        self.player_backend_name = selected_player_name(player_name)
        self.player = create_player(self.player_backend_name)
        self.usage_tracker = DataUsageTracker()
        self._usage_timer_id: int | None = None
        self._player_state_timer_id: int | None = None
        self.stations: list[dict[str, Any]] = []
        self.selected_station: dict[str, Any] | None = None
        self.current_station: dict[str, Any] | None = None
        self._metadata_timer_id: int | None = None
        self._metadata_fetch_in_progress = False
        self._last_metadata_raw: str | None = None
        self.last_search_results: list[dict[str, Any]] = []
        self.active_playlist_tag: str | None = None
        self.favorite_urls = self._favorite_url_set()
        self.restored_volume: int | None = None
        self.restored_muted: bool = False
        self._restore_playback_preferences()

        root = self._build_root()
        self.set_child(root)
        self.connect("close-request", self.on_close_request)

        self._build_header(root)
        self._build_search_bar(root)
        self._build_content(root)
        root.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))
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
        scroller.add_css_class("results-scroller")
        scroller.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)
        table_box.append(scroller)

        self.results_list = Gtk.ListBox()
        self.results_list.add_css_class("results-list")
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
        label.add_css_class("result-cell")
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

        self.artist_detail_label = self._append_detail_row(details_box, "Artist")
        self.track_detail_label = self._append_detail_row(details_box, "Track")

        self._append_section_title(side_panel, "Data usage")

        self.data_usage_label = self._make_value_label(
            "0.0 MB session · 0.0 MB today · 0.0 MB/h est.",
            selectable=True,
        )
        side_panel.append(self.data_usage_label)

        self.player_state_label = self._make_value_label(
            f"Player: {self.player_backend_name} · stopped", selectable=True
        )
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
        self.play_button.add_css_class("suggested-action")
        self.play_button.set_size_request(112, -1)
        self.play_button.set_hexpand(False)
        self.play_button.set_tooltip_text("Play selected station / stop playback")
        self.play_button.connect("clicked", self.on_play_clicked)
        playback_bar.append(self.play_button)

        self.mute_button = Gtk.Button(label="Mute")
        self.mute_button.set_tooltip_text("Mute / unmute")
        self.mute_button.connect("clicked", self.on_mute_clicked)
        self.mute_button.set_sensitive(self.player.supports_mute())
        playback_bar.append(self.mute_button)

        self.volume_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 1)
        self.volume_scale.set_value(
            self.restored_volume if self.restored_volume is not None else 50
        )
        self.volume_scale.set_size_request(180, -1)
        self.volume_scale.set_hexpand(False)
        self.volume_scale.set_draw_value(False)
        self.volume_scale.set_tooltip_text("Volume")
        self.volume_scale.connect("value-changed", self.on_volume_scale_changed)
        self.volume_scale.set_sensitive(self.player.supports_volume())
        playback_bar.append(self.volume_scale)

    def _build_favorite_controls(self, side_panel: Gtk.Box) -> None:
        self._append_section_title(side_panel, "Favorites")

        favorite_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        favorite_controls.set_hexpand(True)
        side_panel.append(favorite_controls)

        add_title = Gtk.Label(label="Add selected station")
        add_title.set_xalign(0)
        add_title.add_css_class("caption-heading")
        favorite_controls.append(add_title)

        self.add_favorite_button = Gtk.Button(label="★ Add favorite")
        self.add_favorite_button.add_css_class("suggested-action")
        self.add_favorite_button.set_tooltip_text("Add selected station to favorites")
        self.add_favorite_button.connect("clicked", self.on_add_favorite_clicked)
        favorite_controls.append(self.add_favorite_button)

        self.remove_favorite_button = Gtk.Button(label="☆ Remove favorite")
        self.remove_favorite_button.add_css_class("destructive-action")
        self.remove_favorite_button.set_tooltip_text("Remove selected station from favorites")
        self.remove_favorite_button.connect("clicked", self.on_remove_favorite_clicked)
        favorite_controls.append(self.remove_favorite_button)

        edit_title = Gtk.Label(label="Edit selected favorite")
        edit_title.set_xalign(0)
        edit_title.add_css_class("caption-heading")
        favorite_controls.append(edit_title)

        self.favorite_name_entry = Gtk.Entry()
        self.favorite_name_entry.set_placeholder_text("Edit favorite name")
        self.favorite_name_entry.set_hexpand(True)
        favorite_controls.append(self.favorite_name_entry)

        self.edit_favorite_tags_entry = Gtk.Entry()
        self.edit_favorite_tags_entry.set_placeholder_text("Edit favorite tags, comma separated")
        self.edit_favorite_tags_entry.set_hexpand(True)
        favorite_controls.append(self.edit_favorite_tags_entry)

        self.save_favorite_button = Gtk.Button(label="Save edited favorite")
        self.save_favorite_button.set_tooltip_text("Update selected favorite name and tags")
        self.save_favorite_button.connect("clicked", self.on_save_favorite_clicked)
        favorite_controls.append(self.save_favorite_button)

        self.show_favorites_button = Gtk.Button(label="★ Show favorites")
        self.show_favorites_button.set_tooltip_text("Show favorite stations")
        self.show_favorites_button.connect("clicked", self.on_show_favorites_clicked)
        favorite_controls.append(self.show_favorites_button)

    def _favorites_matching_favorite_tag(self, tag: str) -> list[dict[str, Any]]:
        return filter_favorites_by_tag(tag)

    def _all_favorite_playlist_tags(self) -> list[str]:
        return all_favorite_tags()

    def _build_playlist_controls(self, side_panel: Gtk.Box) -> None:
        self._append_section_title(side_panel, "Playlists")

        playlist_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        playlist_controls.set_hexpand(True)
        side_panel.append(playlist_controls)

        self.playlist_status_label = self._make_value_label("No playlist filter", selectable=True)
        playlist_controls.append(self.playlist_status_label)

        self.playlist_tag_entry = Gtk.Entry()
        self.playlist_tag_entry.set_placeholder_text("Favorite tag")
        self.playlist_tag_entry.set_hexpand(True)
        self.playlist_tag_entry.connect("activate", self.on_show_tag_playlist_clicked)
        playlist_controls.append(self.playlist_tag_entry)

        playlist_buttons = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        playlist_buttons.set_hexpand(True)
        playlist_controls.append(playlist_buttons)

        self.show_tag_playlist_button = Gtk.Button(label="Show")
        self.show_tag_playlist_button.set_tooltip_text(
            "Show favorites matching the selected favorite tag"
        )
        self.show_tag_playlist_button.connect("clicked", self.on_show_tag_playlist_clicked)
        playlist_buttons.append(self.show_tag_playlist_button)

        self.random_tag_button = Gtk.Button(label="Random")
        self.random_tag_button.set_tooltip_text(
            "Play a random favorite from the selected favorite tag"
        )
        self.random_tag_button.connect("clicked", self.on_random_tag_clicked)
        playlist_buttons.append(self.random_tag_button)

        self.show_tags_button = Gtk.Button(label="Tags")
        self.show_tags_button.set_tooltip_text("Show available custom favorite tags")
        self.show_tags_button.connect("clicked", self.on_show_tags_clicked)
        playlist_buttons.append(self.show_tags_button)

        self.clear_playlist_button = Gtk.Button(label="Clear")
        self.clear_playlist_button.set_tooltip_text("Clear playlist filter and show all favorites")
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

    def _build_station_row(self, station: dict[str, Any]) -> Gtk.ListBoxRow:
        row = Gtk.ListBoxRow()

        if self._is_current_station(station):
            row.add_css_class("suggested-action")

        row.station = station  # type: ignore[attr-defined]

        row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        row_box.set_margin_top(6)
        row_box.set_margin_bottom(6)
        row_box.set_margin_start(6)
        row_box.set_margin_end(6)

        self._append_cell(row_box, self._station_marker(station), 6)
        self._append_cell(row_box, self._station_display_name(station), 32, expand=True)
        self._append_cell(row_box, station.get("country") or "Unknown", 14)
        self._append_cell(row_box, ", ".join(station_tags(station)), 28, expand=True)
        self._append_cell(row_box, station.get("codec") or "", 8)
        self._append_cell(row_box, str(station.get("bitrate") or 0), 6)

        double_click = Gtk.GestureClick()
        double_click.set_button(0)
        double_click.connect("pressed", self.on_row_double_click, row)
        row.add_controller(double_click)

        row.set_child(row_box)
        return row

    def _select_rendered_row(self, row_to_select: Gtk.ListBoxRow | None) -> None:
        if row_to_select is not None:
            self.results_list.select_row(row_to_select)
            self.selected_station = getattr(row_to_select, "station", None)
        elif self.stations and self.selected_station is None:
            first_row = self.results_list.get_row_at_index(0)
            self.results_list.select_row(first_row)
            self.selected_station = getattr(first_row, "station", None) if first_row else None
        elif not self.stations:
            self.selected_station = None

    def _preferred_station_url(self) -> str | None:
        if self.selected_station:
            selected_url = self._station_url(self.selected_station)
            if selected_url:
                return selected_url
        if self.current_station:
            return self._station_url(self.current_station)
        return None

    def _station_url(self, station: dict[str, Any] | None) -> str | None:
        return station_url(station)

    def _selected_station_key(self) -> str | None:
        return station_key(self.selected_station)

    def _clear_results(self) -> None:
        child = self.results_list.get_first_child()
        while child is not None:
            next_child = child.get_next_sibling()
            self.results_list.remove(child)
            child = next_child

    def _is_current_station(self, station: dict[str, Any]) -> bool:
        return same_station(station, self.current_station)

    def _station_marker(self, station: dict[str, Any]) -> str:
        marker_parts = []
        if self._is_current_station(station):
            marker_parts.append("▶")
        if self._is_favorite_station(station):
            marker_parts.append("★")
        return "".join(marker_parts)

    def _render_results(self) -> None:
        preferred_url = self._preferred_station_url()
        self._clear_results()
        row_to_select: Gtk.ListBoxRow | None = None

        for station in self.stations:
            row = self._build_station_row(station)
            if preferred_url and self._station_url(station) == preferred_url:
                row_to_select = row
            self.results_list.append(row)

        self._select_rendered_row(row_to_select)
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
            self._apply_player_preferences_before_start()
            self.player.play(url)
            self._set_player_volume_from_scale()
            if self.player.supports_mute():
                self._set_player_mute(self.restored_muted)

        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self.status_label.set_text(f"Playback failed: {exc}")
            return

        self.current_station = self.selected_station
        self.usage_tracker.start(self.current_station)
        self.update_now_playing()
        self.update_data_usage()
        self.update_player_state()
        self._ensure_usage_timer()
        self._ensure_player_state_timer()
        self._update_play_stop_button()
        self.status_label.set_text("Playing")
        self._render_results()

    def _metadata_worker(self, stream_url: str) -> None:
        try:
            metadata = fetch_stream_metadata(stream_url)
        finally:
            GLib.idle_add(self._metadata_fetch_finished)

        if not metadata:
            return

        artist = metadata.get("artist") or "—"
        title = metadata.get("title") or metadata.get("raw") or "—"
        raw = metadata.get("raw") or f"{artist} - {title}"

        GLib.idle_add(self._update_metadata_labels, artist, title, raw)

    def _update_metadata_labels(self, artist: str, title: str, raw: str) -> bool:
        if raw == self._last_metadata_raw:
            return False

        self._last_metadata_raw = raw
        self.artist_detail_label.set_text(artist)
        self.track_detail_label.set_text(title)
        return False

    def _metadata_fetch_finished(self) -> bool:
        self._metadata_fetch_in_progress = False
        return False

    def _clear_metadata_labels(self) -> None:
        if hasattr(self, "artist_detail_label"):
            self.artist_detail_label.set_text("—")
        if hasattr(self, "track_detail_label"):
            self.track_detail_label.set_text("—")
        self._last_metadata_raw = None

    def _start_metadata_polling(self) -> None:
        if self._metadata_timer_id is not None:
            return

        self._metadata_timer_id = GLib.timeout_add_seconds(15, self._tick_metadata)
        self._tick_metadata()

    def _stop_metadata_polling(self) -> None:
        if self._metadata_timer_id is not None:
            GLib.source_remove(self._metadata_timer_id)
            self._metadata_timer_id = None
        self._metadata_fetch_in_progress = False
        self._clear_metadata_labels()

    def _tick_metadata(self) -> bool:
        if not self.current_station or not self._has_active_playback():
            self._stop_metadata_polling()
            return False

        if self._metadata_fetch_in_progress:
            return True

        stream_url = self._station_url(self.current_station)
        if not stream_url:
            return True

        self._metadata_fetch_in_progress = True
        threading.Thread(
            target=self._metadata_worker,
            args=(stream_url,),
            daemon=True,
        ).start()

        return True

    def update_now_playing(self) -> None:
        if not self.current_station:
            self.now_playing_label.set_text("Nothing playing")
            if hasattr(self, "country_detail_label"):
                self.country_detail_label.set_text("—")
                self.codec_detail_label.set_text("—")
                self.bitrate_detail_label.set_text("—")
                self.tags_detail_label.set_text("—")
            self._stop_metadata_polling()
            return

        station = self.current_station

        self.now_playing_label.set_text(self._station_display_name(station))
        self.country_detail_label.set_text(station.get("country") or "Unknown")
        self.codec_detail_label.set_text(station.get("codec") or "?")
        self.bitrate_detail_label.set_text(f"{station.get('bitrate') or 0} kbps")
        self.tags_detail_label.set_text(station.get("tags") or "No tags")

        self._start_metadata_polling()

    def _apply_player_preferences_before_start(self) -> None:
        if not self.player.supports_volume():
            set_volume = getattr(self.player, "set_volume", None)
            if callable(set_volume):
                set_volume(self._current_volume_value())

    def _restore_playback_preferences(self) -> None:
        state = get_playback_state()

        volume = state.get("volume")
        if isinstance(volume, int):
            self.restored_volume = volume

        self.restored_muted = bool(state.get("muted", False))

    def _current_volume_value(self) -> int:
        return int(round(self.volume_scale.get_value()))

    def _set_player_volume_from_scale(self) -> None:
        volume = self._current_volume_value()
        if self.player.supports_volume():
            self.player.set_volume(volume)
        else:
            self._send_player_command(["set_property", "volume", volume])

    def _set_player_mute(self, muted: bool) -> None:
        set_mute = getattr(self.player, "set_mute", None)
        if callable(set_mute):
            set_mute(muted)

    def _persist_playback_preferences(self) -> None:
        save_playback_state(
            volume=self.restored_volume,
            muted=self._player_muted_state(),
        )

    def _player_muted_state(self) -> bool:
        try:
            state = self.player.get_state()
        except Exception:  # noqa: BLE001
            return self.restored_muted
        return bool(state.get("muted", self.restored_muted))

    def on_mute_clicked(self, _button: Gtk.Button) -> None:
        if not self.player.supports_mute():
            self.status_label.set_text(f"{self.player_backend_name} does not support live mute.")
            return

        if not self._has_active_playback():
            self.status_label.set_text("Nothing is playing.")
            return

        try:
            self.player.toggle_mute()
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self._playback_command_failed("Mute", exc)
            return

        self.update_player_state()
        self.restored_muted = self._player_muted_state()
        self._persist_playback_preferences()
        self.status_label.set_text("Toggled mute")

    def on_volume_scale_changed(self, _scale: Gtk.Scale) -> None:
        self.restored_volume = self._current_volume_value()

        if not self._has_active_playback():
            save_playback_state(volume=self.restored_volume)
            return

        try:
            self._set_player_volume_from_scale()
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self._playback_command_failed("Volume", exc)
            return

        self.update_player_state()
        self._persist_playback_preferences()

    def _favorite_edit_name_from_entry(self) -> str:
        if not hasattr(self, "favorite_name_entry"):
            return ""
        return self.favorite_name_entry.get_text().strip()

    def _favorite_edit_tags_from_entry(self) -> list[str]:
        if not hasattr(self, "edit_favorite_tags_entry"):
            return []
        raw_value = self.edit_favorite_tags_entry.get_text().strip()
        if not raw_value:
            return []
        return sorted({tag.strip() for tag in raw_value.split(",") if tag.strip()})

    def _selected_favorite_record(self) -> dict[str, Any] | None:
        selected_key = self._selected_station_key()
        if not selected_key:
            return None

        for favorite in load_favorites():
            if station_key(favorite) == selected_key:
                return favorite
        return None

    def _populate_favorite_edit_fields(self) -> None:
        if not hasattr(self, "favorite_name_entry"):
            return
        favorite = self._selected_favorite_record()
        if not favorite:
            self.favorite_name_entry.set_text("")
            self.edit_favorite_tags_entry.set_text("")
            return
        display_name = (
            favorite.get("custom_name")
            or favorite.get("favorite_name")
            or favorite.get("name")
            or ""
        )
        tags = favorite.get("favorite_tags") or []
        tags_text = tags if isinstance(tags, str) else ", ".join(str(tag) for tag in tags)
        self.favorite_name_entry.set_text(display_name)
        self.edit_favorite_tags_entry.set_text(tags_text)

    def _apply_favorite_edits_to_station(
        self,
        station: dict[str, Any],
        *,
        custom_name: str,
        favorite_tags: list[str],
    ) -> None:
        if custom_name:
            station["custom_name"] = custom_name
        else:
            station.pop("custom_name", None)

        station["favorite_tags"] = favorite_tags

    def _update_visible_favorite(
        self,
        key: str,
        *,
        custom_name: str,
        favorite_tags: list[str],
    ) -> None:
        for station in self.stations:
            if self._station_url(station) != key:
                continue
            self._apply_favorite_edits_to_station(
                station,
                custom_name=custom_name,
                favorite_tags=favorite_tags,
            )
            self.selected_station = station
            break

        if self.current_station and self._station_url(self.current_station) == key:
            self._apply_favorite_edits_to_station(
                self.current_station,
                custom_name=custom_name,
                favorite_tags=favorite_tags,
            )

    def _update_favorite_buttons(self) -> None:
        if not hasattr(self, "add_favorite_button"):
            return

        has_selection = self.selected_station is not None
        is_favorite = bool(has_selection and self._is_favorite_station(self.selected_station))

        self.add_favorite_button.set_sensitive(has_selection and not is_favorite)
        self.remove_favorite_button.set_sensitive(has_selection and is_favorite)

        if hasattr(self, "favorite_name_entry"):
            self.favorite_name_entry.set_sensitive(is_favorite)
            self.edit_favorite_tags_entry.set_sensitive(is_favorite)
            self.save_favorite_button.set_sensitive(is_favorite)

        self._populate_favorite_edit_fields()

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

        if add_favorite(self.selected_station):
            self._refresh_favorite_cache()
            self._render_results()
            self.status_label.set_text("Added to favorites.")
            return

        self.status_label.set_text("Station is already in favorites or has no URL.")
        self._update_favorite_buttons()

    def on_save_favorite_clicked(self, _button: Gtk.Button) -> None:
        favorite = self._selected_favorite_record()
        if not favorite:
            self.status_label.set_text("Select a favorite first.")
            self._update_favorite_buttons()
            return

        key = station_key(favorite)
        if not key:
            self.status_label.set_text("Selected favorite has no URL.")
            self._update_favorite_buttons()
            return

        favorite_name = self._favorite_edit_name_from_entry()
        favorite_tags = self._favorite_edit_tags_from_entry()

        if not update_favorite(key, custom_name=favorite_name, favorite_tags=favorite_tags):
            self.status_label.set_text("Could not update favorite.")
            self._update_favorite_buttons()
            return

        self._refresh_favorite_cache()
        self._update_visible_favorite(
            key,
            custom_name=favorite_name,
            favorite_tags=favorite_tags,
        )

        self._render_results()
        self.update_now_playing()
        self.status_label.set_text("Favorite updated.")

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

    def _show_all_favorites(self) -> int:
        """Show all saved favorites and reset playlist filtering state."""
        self.active_playlist_tag = None
        self._refresh_favorite_cache()
        self.stations = load_favorites()
        self.selected_station = None
        self._render_results()
        self._update_playlist_status()
        return len(self.stations)

    def _set_favorites_status(self, count: int) -> None:
        if count:
            self.status_label.set_text(f"Showing {count} favorite station(s).")
        else:
            self.status_label.set_text("No favorite stations yet.")

    def on_show_favorites_clicked(self, _button: Gtk.Button) -> None:
        self._set_favorites_status(self._show_all_favorites())

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
        tags = self._all_favorite_playlist_tags()
        if not tags:
            self.status_label.set_text("No custom favorite tags found yet.")
            return
        self.status_label.set_text("Favorite tags: " + ", ".join(tags))

    def on_show_tag_playlist_clicked(self, _widget: Gtk.Widget) -> None:
        tag = self._playlist_tag_value()
        if not tag:
            tags = self._all_favorite_playlist_tags()
            if tags:
                self.status_label.set_text("Type a tag. Available: " + ", ".join(tags))
            else:
                self.status_label.set_text("No custom favorite tags found yet.")
            return

        stations = self._favorites_matching_favorite_tag(tag)
        self.active_playlist_tag = tag
        self._refresh_favorite_cache()
        self.stations = stations
        self.selected_station = None
        self._render_results()
        self._update_playlist_status()
        self.status_label.set_text(
            f"Loaded {len(stations)} favorite station(s) for favorite tag: {tag}"
        )

    def on_random_tag_clicked(self, _button: Gtk.Button) -> None:
        import random

        tag = self._playlist_tag_value()
        if not tag:
            tags = self._all_favorite_playlist_tags()
            if tags:
                self.status_label.set_text("Type a tag first. Available: " + ", ".join(tags))
            else:
                self.status_label.set_text("No tags found in favorites yet.")
            return

        stations = self._favorites_matching_favorite_tag(tag)
        if not stations:
            self.status_label.set_text(f"No favorite stations found for favorite tag: {tag}")
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

        self._set_favorites_status(self._show_all_favorites())

    def on_stop_clicked(self, _button: Gtk.Button) -> None:
        self._stop_usage_timer()
        self._stop_player_state_timer()
        self.player.stop()
        self._stop_metadata_polling()
        self.usage_tracker.stop()
        self.update_data_usage()
        self.current_station = None
        self.update_now_playing()
        self.update_player_state()
        self._update_play_stop_button()
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

        self.mute_button.set_label("Unmute" if muted else "Mute")

    def update_player_state(self) -> None:
        if not hasattr(self, "player_state_label"):
            return

        get_state = getattr(self.player, "get_state", None)
        if not callable(get_state):
            playing = self._has_active_playback()
            playback = "playing" if playing else "stopped"
            self.player_state_label.set_text(f"Player: {self.player_backend_name} · {playback}")
            self._update_mute_button(None)
            self._update_play_stop_button()
            return

        try:
            state = get_state()
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self.player_state_label.set_text(
                f"Player: {self.player_backend_name} · state unavailable"
            )
            self._playback_command_failed("Player state", exc)
            self._update_mute_button(None)
            self._update_play_stop_button()
            return

        if not state.get("playing"):
            self.player_state_label.set_text(f"Player: {self.player_backend_name} · stopped")
            self._update_mute_button(None)
            self._update_play_stop_button()
            return

        is_muted = bool(state.get("muted"))
        muted = "muted" if is_muted else "sound on"
        volume = state.get("volume")
        volume_text = f" · volume {int(volume)}%" if isinstance(volume, int | float) else ""

        self.player_state_label.set_text(
            f"Player: {self.player_backend_name} · playing · {muted}{volume_text}"
        )
        self._update_mute_button(is_muted)
        self._update_play_stop_button()

    def _update_play_stop_button(self) -> None:
        if not hasattr(self, "play_button"):
            return

        if self._has_active_playback():
            self.play_button.set_label("■ Stop")
            self.play_button.set_tooltip_text("Stop playback")
            return

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
        with suppress(Exception):
            self.player.stop()

    def update_data_usage(self) -> None:
        if hasattr(self, "data_usage_label"):
            self.data_usage_label.set_text(
                format_usage_line(self.usage_tracker.snapshot()).replace("Data: ", "")
            )
