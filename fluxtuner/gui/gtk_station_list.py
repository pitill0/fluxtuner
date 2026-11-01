"""GTK station-list widgets and selection projection through live state ports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Pango  # noqa: E402

from fluxtuner.core.compatibility import station_is_supported  # noqa: E402
from fluxtuner.core.favorites import favorite_display_name  # noqa: E402
from fluxtuner.core.stations import (  # noqa: E402
    same_station,
    station_bitrate,
    station_codec,
    station_country,
    station_name,
    station_url,
)
from fluxtuner.gui.gtk_library import library_tags_text  # noqa: E402
from fluxtuner.players.capabilities import PlayerCapabilities  # noqa: E402


@dataclass(frozen=True)
class StationListPorts:
    get_stations: Callable[[], list[dict[str, Any]]]
    get_selected: Callable[[], dict[str, Any] | None]
    set_selected: Callable[[dict[str, Any] | None], None]
    get_current: Callable[[], dict[str, Any] | None]
    get_capabilities: Callable[[], PlayerCapabilities]


class StationList:
    """Own rows and gestures, while keeping logical selection in the composition root."""

    def __init__(
        self,
        *,
        ports: StationListPorts,
        is_favorite: Callable[[dict[str, Any]], bool],
        update_favorite_buttons: Callable[[], None],
        play_selected: Callable[[], None],
        context_click: Callable[[Gtk.GestureClick, int, float, float, Gtk.ListBoxRow], None],
    ) -> None:
        self._ports = ports
        self._is_favorite_station = is_favorite
        self._update_favorite_buttons = update_favorite_buttons
        self.play_selected_station = play_selected
        self.on_row_context_click = context_click
        self._station_url = station_url

    @property
    def stations(self) -> list[dict[str, Any]]:
        return self._ports.get_stations()

    @property
    def selected_station(self) -> dict[str, Any] | None:
        return self._ports.get_selected()

    @selected_station.setter
    def selected_station(self, station: dict[str, Any] | None) -> None:
        self._ports.set_selected(station)

    @property
    def current_station(self) -> dict[str, Any] | None:
        return self._ports.get_current()

    @property
    def player_capabilities(self) -> PlayerCapabilities:
        return self._ports.get_capabilities()

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

    def _station_display_name(self, station: dict[str, Any]) -> str:
        if self._is_favorite_station(station):
            return favorite_display_name(station)
        return station_name(station)

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
        self._append_cell(row_box, station_country(station), 14)
        self._append_cell(row_box, library_tags_text(station, fallback=""), 28, expand=True)
        self._append_cell(row_box, station_codec(station), 8)
        self._append_cell(row_box, str(station_bitrate(station)), 6)

        double_click = Gtk.GestureClick()
        double_click.set_button(0)
        double_click.connect("pressed", self.on_row_double_click, row)
        row.add_controller(double_click)

        context_click = Gtk.GestureClick()
        context_click.set_button(3)
        context_click.connect("pressed", self.on_row_context_click, row)
        row.add_controller(context_click)

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
        if not station_is_supported(station, self.player_capabilities):
            marker_parts.append("!")
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
