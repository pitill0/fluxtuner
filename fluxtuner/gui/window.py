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

    def _build_side_panel(self, content: Gtk.Box) -> None:
        side_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        side_panel.set_size_request(260, -1)
        side_panel.set_hexpand(False)
        side_panel.set_vexpand(True)
        content.append(side_panel)

        self._append_section_title(side_panel, "Now Playing")

        self.now_playing_label = Gtk.Label(label="Nothing playing")
        self.now_playing_label.set_xalign(0)
        self.now_playing_label.set_wrap(True)
        self.now_playing_label.set_selectable(True)
        side_panel.append(self.now_playing_label)

        self.data_usage_label = Gtk.Label(label="Data: 0.0 MB session · 0.0 MB today · 0.0 MB/h est.")
        self.data_usage_label.set_xalign(0)
        self.data_usage_label.set_wrap(True)
        self.data_usage_label.set_selectable(True)
        side_panel.append(self.data_usage_label)

        self.player_state_label = Gtk.Label(label="Player: stopped")
        self.player_state_label.set_xalign(0)
        self.player_state_label.set_wrap(True)
        self.player_state_label.set_selectable(True)
        side_panel.append(self.player_state_label)

        self._build_favorite_controls(side_panel)

        hint = Gtk.Label(label="Tip: select a station and use ▶ below, or double-click it.")
        hint.set_xalign(0)
        hint.set_wrap(True)
        hint.add_css_class("dim-label")
        side_panel.append(hint)

    def _build_bottom_playback_bar(self, root: Gtk.Box) -> None:
        playback_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
        playback_bar.set_hexpand(True)
        root.append(playback_bar)

        playback_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        playback_group.set_hexpand(False)
        playback_bar.append(playback_group)

        self.stop_button = Gtk.Button(label="■")
        self.stop_button.set_tooltip_text("Stop playback")
        self.stop_button.connect("clicked", self.on_stop_clicked)
        playback_group.append(self.stop_button)

        self.pause_button = Gtk.Button(label="⏯")
        self.pause_button.set_tooltip_text("Pause / resume")
        self.pause_button.connect("clicked", self.on_pause_clicked)
        playback_group.append(self.pause_button)

        self.play_button = Gtk.Button(label="▶")
        self.play_button.set_tooltip_text("Play selected station")
        self.play_button.connect("clicked", self.on_play_clicked)
        playback_group.append(self.play_button)

        volume_group = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        volume_group.set_hexpand(False)
        playback_bar.append(volume_group)

        volume_down_button = Gtk.Button(label="−")
        volume_down_button.set_tooltip_text("Volume down")
        volume_down_button.connect("clicked", self.on_volume_down_clicked)
        volume_group.append(volume_down_button)

        self.mute_button = Gtk.Button(label="🔇")
        self.mute_button.set_tooltip_text("Mute / unmute")
        self.mute_button.connect("clicked", self.on_mute_clicked)
        volume_group.append(self.mute_button)

        volume_up_button = Gtk.Button(label="+")
        volume_up_button.set_tooltip_text("Volume up")
        volume_up_button.connect("clicked", self.on_volume_up_clicked)
        volume_group.append(volume_up_button)

    def _build_favorite_controls(self, side_panel: Gtk.Box) -> None:
        self._append_section_title(side_panel, "Favorites")

        favorite_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        favorite_controls.set_hexpand(True)
        side_panel.append(favorite_controls)

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
        self.stations = stations
        self._render_results()
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
            return
        self.selected_station = getattr(row, "station", None)

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
            self.player.play(url)
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
        self.status_label.set_text("Playing")
        self._render_results()

    def update_now_playing(self) -> None:
        if not self.current_station:
            self.now_playing_label.set_text("Nothing playing")
            return

        self.now_playing_label.set_text(
            f"{self._station_label(self.current_station)}\n"
            f"{self._station_detail(self.current_station)}"
        )

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

    def on_volume_down_clicked(self, _button: Gtk.Button) -> None:
        if not self._has_active_playback():
            self.status_label.set_text("Nothing is playing.")
            return

        try:
            self.player.volume_down()
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self._playback_command_failed("Volume down", exc)
            return

        self.update_player_state()
        self.status_label.set_text("Volume down")

    def on_volume_up_clicked(self, _button: Gtk.Button) -> None:
        if not self._has_active_playback():
            self.status_label.set_text("Nothing is playing.")
            return

        try:
            self.player.volume_up()
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self._playback_command_failed("Volume up", exc)
            return

        self.update_player_state()
        self.status_label.set_text("Volume up")

    def on_add_favorite_clicked(self, _button: Gtk.Button) -> None:
        if not self.selected_station:
            self.status_label.set_text("Select a station first.")
            return

        if add_favorite(self.selected_station):
            self._refresh_favorite_cache()
            self.status_label.set_text("Added to favorites.")
            self._render_results()
            return

        self.status_label.set_text("Station is already in favorites or has no URL.")

    def on_remove_favorite_clicked(self, _button: Gtk.Button) -> None:
        if not self.selected_station:
            self.status_label.set_text("Select a station first.")
            return

        key = station_key(self.selected_station)
        if not key:
            self.status_label.set_text("Selected station has no favorite URL.")
            return

        if remove_favorite(key):
            self._refresh_favorite_cache()
            self.status_label.set_text("Removed from favorites.")

            # If the current view is the favorites list, remove it from the table too.
            if all(self._is_favorite_station(station) for station in self.stations):
                self.stations = load_favorites()
                self.selected_station = None

            self._render_results()
            return

        self.status_label.set_text("Selected station is not in favorites.")

    def on_show_favorites_clicked(self, _button: Gtk.Button) -> None:
        favorites = load_favorites()
        self._refresh_favorite_cache()
        self.stations = favorites
        self.selected_station = None
        self._render_results()
        self.status_label.set_text(f"Loaded {len(favorites)} favorite station(s).")

    def on_stop_clicked(self, _button: Gtk.Button) -> None:
        self._stop_usage_timer()
        self._stop_player_state_timer()
        self.player.stop()
        self.usage_tracker.stop()
        self.update_data_usage()
        self.current_station = None
        self.update_now_playing()
        self.update_player_state()
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

    def update_player_state(self) -> None:
        if not hasattr(self, "player_state_label"):
            return

        if not self._has_active_playback():
            self.player_state_label.set_text("Player: stopped")
            return

        get_state = getattr(self.player, "get_state", None)
        if not callable(get_state):
            self.player_state_label.set_text("Player: playing")
            return

        try:
            state = get_state() or {}
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self.player_state_label.set_text(f"Player: state unavailable ({exc})")
            return

        if not state.get("playing"):
            self.player_state_label.set_text("Player: stopped")
            return

        playback = "paused" if state.get("paused") else "playing"
        muted = "muted" if state.get("muted") else "sound on"
        volume = state.get("volume")

        if isinstance(volume, (int, float)):
            volume_text = f"{int(round(volume))}%"
        else:
            volume_text = "unknown volume"

        self.player_state_label.set_text(f"Player: {playback} · {muted} · {volume_text}")

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
            self.data_usage_label.set_text(format_usage_line(self.usage_tracker.snapshot()))
