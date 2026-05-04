"""Experimental GTK desktop window for FluxTuner."""
from __future__ import annotations

import threading
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango

from fluxtuner.core.api import search_stations_filtered
from fluxtuner.players import create_player

DEFAULT_SEARCH = "fip"
DEFAULT_STREAM_URL = "https://icecast.radiofrance.fr/fip-hifi.aac"


class MainWindow(Gtk.ApplicationWindow):
    """Small GTK GUI MVP: search stations, list results and play selection."""

    def __init__(self, app: Gtk.Application, player_name: str = "mpv") -> None:
        super().__init__(application=app)

        self.set_title("FluxTuner")
        self.set_default_size(980, 620)

        self.player = create_player(player_name)
        self.stations: list[dict[str, Any]] = []
        self.selected_station: dict[str, Any] | None = None
        self.current_station: dict[str, Any] | None = None

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)
        self.set_child(root)

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

        search_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        root.append(search_bar)

        self.search_entry = Gtk.Entry()
        self.search_entry.set_placeholder_text("Search station, genre or tag…")
        self.search_entry.set_text(DEFAULT_SEARCH)
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("activate", self.on_search_clicked)
        search_bar.append(self.search_entry)

        self.country_entry = Gtk.Entry()
        self.country_entry.set_placeholder_text("Country or code")
        self.country_entry.set_width_chars(14)
        self.country_entry.connect("activate", self.on_search_clicked)
        search_bar.append(self.country_entry)

        self.min_bitrate_entry = Gtk.Entry()
        self.min_bitrate_entry.set_placeholder_text("Min kbps")
        self.min_bitrate_entry.set_width_chars(10)
        self.min_bitrate_entry.connect("activate", self.on_search_clicked)
        search_bar.append(self.min_bitrate_entry)

        search_button = Gtk.Button(label="Search")
        search_button.connect("clicked", self.on_search_clicked)
        search_bar.append(search_button)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        content.set_vexpand(True)
        root.append(content)

        table_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        table_box.set_hexpand(True)
        table_box.set_vexpand(True)
        content.append(table_box)

        table_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        table_header.add_css_class("heading")
        table_box.append(table_header)

        self._append_cell(table_header, "", 2)
        self._append_cell(table_header, "Name", 32, expand=True)
        self._append_cell(table_header, "Country", 14)
        self._append_cell(table_header, "Code", 5)
        self._append_cell(table_header, "Tags", 28, expand=True)
        self._append_cell(table_header, "Codec", 8)
        self._append_cell(table_header, "Kbps", 6)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)
        table_box.append(scroller)

        self.results_list = Gtk.ListBox()
        self.results_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.results_list.connect("row-selected", self.on_row_selected)
        self.results_list.connect("row-activated", self.on_row_activated)
        scroller.set_child(self.results_list)

        side_panel = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        side_panel.set_size_request(260, -1)
        content.append(side_panel)

        now_title = Gtk.Label(label="Now Playing")
        now_title.set_xalign(0)
        now_title.add_css_class("heading")
        side_panel.append(now_title)

        self.now_playing_label = Gtk.Label(label="Nothing playing")
        self.now_playing_label.set_xalign(0)
        self.now_playing_label.set_wrap(True)
        side_panel.append(self.now_playing_label)

        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        side_panel.append(controls)

        play_button = Gtk.Button(label="Play")
        play_button.connect("clicked", self.on_play_clicked)
        controls.append(play_button)

        stop_button = Gtk.Button(label="Stop")
        stop_button.connect("clicked", self.on_stop_clicked)
        controls.append(stop_button)

        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_xalign(0)
        self.status_label.set_wrap(True)
        root.append(self.status_label)

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

    def _station_label(self, station: dict[str, Any]) -> str:
        name = station.get("name") or "Unknown station"
        country = station.get("country") or "Unknown"
        code = station.get("countrycode") or ""
        country_label = f"{country} ({code})" if code else country
        return f"{name}\n{country_label}"

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

    def _render_results(self) -> None:
        self._clear_results()

        for station in self.stations:
            row = Gtk.ListBoxRow()
            row.station = station  # type: ignore[attr-defined]

            row_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            row_box.set_margin_top(6)
            row_box.set_margin_bottom(6)
            row_box.set_margin_start(6)
            row_box.set_margin_end(6)

            marker = "▶" if self._is_current_station(station) else ""
            self._append_cell(row_box, marker, 2)
            self._append_cell(row_box, station.get("name") or "Unknown station", 32, expand=True)
            self._append_cell(row_box, station.get("country") or "Unknown", 14)
            self._append_cell(row_box, station.get("countrycode") or "", 5)
            self._append_cell(row_box, station.get("tags") or "", 28, expand=True)
            self._append_cell(row_box, station.get("codec") or "", 8)
            self._append_cell(row_box, str(station.get("bitrate") or 0), 6)

            row.set_child(row_box)
            self.results_list.append(row)

        if self.stations:
            self.results_list.select_row(self.results_list.get_row_at_index(0))
        else:
            self.selected_station = None

    def _is_current_station(self, station: dict[str, Any]) -> bool:
        if not self.current_station:
            return False
        return station.get("url") == self.current_station.get("url")

    def _parse_min_bitrate(self) -> int | None:
        raw_value = self.min_bitrate_entry.get_text().strip()
        if not raw_value:
            return None
        if not raw_value.isdigit():
            raise ValueError("Minimum bitrate must be a number.")
        return int(raw_value)

    def on_search_clicked(self, _widget: Gtk.Widget) -> None:
        query = self.search_entry.get_text().strip()
        country = self.country_entry.get_text().strip() or None

        try:
            min_bitrate = self._parse_min_bitrate()
        except ValueError as exc:
            self.status_label.set_text(str(exc))
            return

        if not query and not country and min_bitrate is None:
            self.status_label.set_text("Enter a search term or at least one filter.")
            return

        filters = []
        if country:
            filters.append(f"country={country}")
        if min_bitrate is not None:
            filters.append(f"min={min_bitrate}kbps")
        suffix = f" ({', '.join(filters)})" if filters else ""
        self.status_label.set_text(f"Searching{suffix}…")

        def worker() -> None:
            try:
                stations = search_stations_filtered(
                    query=query,
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

    def on_row_selected(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            self.selected_station = None
            return

        self.selected_station = getattr(row, "station", None)

    def on_row_activated(self, _list_box: Gtk.ListBox, row: Gtk.ListBoxRow) -> None:
        self.selected_station = getattr(row, "station", None)
        self.play_selected_station()

    def on_play_clicked(self, _button: Gtk.Button) -> None:
        self.play_selected_station()

    def play_selected_station(self) -> None:
        if not self.selected_station:
            self.status_label.set_text("Select a station first.")
            return

        url = self.selected_station.get("url") or DEFAULT_STREAM_URL
        if not url:
            self.status_label.set_text("Selected station has no playable URL.")
            return

        try:
            self.player.play(url)
        except Exception as exc:  # noqa: BLE001 - user-facing status in GUI MVP.
            self.status_label.set_text(f"Playback failed: {exc}")
            return

        self.current_station = self.selected_station
        self.now_playing_label.set_text(
            f"{self._station_label(self.current_station)}\n{self._station_detail(self.current_station)}"
        )
        self.status_label.set_text("Playing")
        self._render_results()

    def on_stop_clicked(self, _button: Gtk.Button) -> None:
        self.player.stop()
        self.current_station = None
        self.now_playing_label.set_text("Nothing playing")
        self.status_label.set_text("Stopped")
        self._render_results()
