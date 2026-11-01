"""GTK library controls, dialogs and view transitions."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import gi

from fluxtuner.core.compatibility import filter_supported_stations
from fluxtuner.core.stations import station_key, station_name, station_url
from fluxtuner.gui.gtk_library import LibraryController
from fluxtuner.gui.gtk_m3u_import import open_m3u_import, open_remote_m3u_import
from fluxtuner.gui.gtk_view_state import ViewState
from fluxtuner.players.capabilities import PlayerCapabilities

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402


@dataclass(frozen=True)
class LibraryViewPorts:
    """Access the station view's live state without retaining its window.

    Reads and writes use the same authoritative objects as search/playback;
    opening the library never creates a second selection or station cache.
    """

    get_stations: Callable[[], list[dict[str, Any]]]
    set_stations: Callable[[list[dict[str, Any]]], None]
    get_selected: Callable[[], dict[str, Any] | None]
    set_selected: Callable[[dict[str, Any] | None], None]
    get_current: Callable[[], dict[str, Any] | None]
    get_capabilities: Callable[[], PlayerCapabilities]


class LibraryPanel:
    """Own library widgets and dialogs; call the shared station-view boundary."""

    def __init__(
        self,
        *,
        parent: Gtk.Window,
        controller: LibraryController,
        ports: LibraryViewPorts,
        view_state: ViewState,
        invalidate_search: Callable[[], object],
        render_results: Callable[[], None],
        play_selected: Callable[[], None],
        update_now_playing: Callable[[], None],
        set_status: Callable[[str], None],
        set_view_status: Callable[..., None],
        make_value_label: Callable[..., Gtk.Label],
        append_section_title: Callable[[Gtk.Box, str], None],
        close_menu: Callable[[], None],
    ) -> None:
        self._parent = parent  # Gtk transient parent only; never used for application state.
        self._controller = controller
        self._ports = ports
        self._view_state = view_state
        self._invalidate_search = invalidate_search
        self._render_results = render_results
        self.play_selected_station = play_selected
        self.update_now_playing = update_now_playing
        self._set_status = set_status
        self._set_view_status = set_view_status
        self._make_value_label = make_value_label
        self._append_section_title = append_section_title
        self._close_menu = close_menu
        self._playlist_profile_id = controller.playlist_profile_id
        self._refresh_favorite_cache = controller.refresh_favorite_cache
        self._is_favorite_station = controller.is_favorite_station
        self._favorites_matching_favorite_tag = controller.favorites_matching_favorite_tag
        self._all_favorite_playlist_tags = controller.all_favorite_playlist_tags

    @property
    def stations(self) -> list[dict[str, Any]]:
        return self._ports.get_stations()

    @stations.setter
    def stations(self, stations: list[dict[str, Any]]) -> None:
        self._ports.set_stations(stations)

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

    def _selected_station_key(self) -> str | None:
        return station_key(self.selected_station) if self.selected_station is not None else None

    @staticmethod
    def _station_url(station: dict[str, Any]) -> str | None:
        return station_url(station)

    def on_import_stations_clicked(self, _button: Gtk.Button) -> None:
        self._close_menu()
        try:
            profile_id = self._playlist_profile_id()
        except Exception as exc:
            self._set_status(f"Could not import stations: {exc}")
            return
        open_m3u_import(
            self._parent,
            profile_id=profile_id,
            profile_is_current=lambda: self._playlist_profile_id() == profile_id,
            on_saved=self._on_m3u_import_saved,
            on_error=self._set_status,
        )

    def on_import_stations_url_clicked(self, _button: Gtk.Button) -> None:
        self._close_menu()
        try:
            profile_id = self._playlist_profile_id()
        except Exception as exc:
            self._set_status(f"Could not import stations: {exc}")
            return
        open_remote_m3u_import(
            self._parent,
            profile_id=profile_id,
            profile_is_current=lambda: self._playlist_profile_id() == profile_id,
            on_saved=self._on_m3u_import_saved,
            on_error=self._set_status,
        )

    def _on_m3u_import_saved(self, name: str, result: Any) -> None:
        self._refresh_saved_playlists()
        self._show_saved_playlist(name)
        self._set_status(
            f"Imported {result.added_to_playlist} into {name}; {result.already_in_playlist} already in playlist. Favorites: {result.added_favorites} new, {result.existing_favorites} kept."
        )

    def on_add_custom_station_clicked(self, _button: Gtk.Button) -> None:
        self._close_menu()
        try:
            profile_id = self._playlist_profile_id()
        except Exception as exc:
            self._set_status(f"Could not add station: {exc}")
            return
        dialog, content = self._make_playlist_dialog("Add station", "Add")
        content.append(self._make_value_label("Station name"))
        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("My radio")
        name_entry.set_activates_default(True)
        content.append(name_entry)
        content.append(self._make_value_label("Stream URL"))
        url_entry = Gtk.Entry()
        url_entry.set_placeholder_text("https://example.org/live")
        url_entry.set_activates_default(True)
        content.append(url_entry)
        content.append(self._make_value_label("Saved to favorites in the current profile."))
        error = self._make_value_label("")
        error.set_wrap(True)
        content.append(error)

        def respond(current: Gtk.Dialog, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                current.destroy()
                return
            try:
                if self._playlist_profile_id() != profile_id:
                    raise ValueError("The profile changed. Reopen this dialog.")
                added = self._controller.add_custom_station(
                    profile_id=profile_id, name=name_entry.get_text(), url=url_entry.get_text()
                )
            except Exception as exc:
                error.set_text(str(exc))
                return
            current.destroy()
            self._show_all_favorites()
            self._refresh_saved_playlists()
            self._set_status(
                "Station added to favorites." if added else "Station is already in favorites."
            )

        dialog.connect("response", respond)
        dialog.present()
        name_entry.grab_focus()

    def _build_library_controls(self, side_panel: Gtk.Box) -> None:
        self._append_section_title(side_panel, "Library")
        library_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        library_controls.set_hexpand(True)
        side_panel.append(library_controls)
        self.show_favorites_button = Gtk.Button(label="★ Show favorites")
        self.show_favorites_button.set_tooltip_text("Show favorite stations")
        self.show_favorites_button.connect("clicked", self.on_show_favorites_clicked)
        library_controls.append(self.show_favorites_button)
        self.show_history_button = Gtk.Button(label="History")
        self.show_history_button.set_tooltip_text("Show recently played stations")
        self.show_history_button.connect("clicked", self.on_show_history_clicked)
        library_controls.append(self.show_history_button)

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

    def on_context_add_playlist_clicked(self, _button: Gtk.Button, station: dict[str, Any]) -> None:
        self.open_playlist_picker(station)

    def open_playlist_picker(self, station: dict[str, Any]) -> None:
        try:
            profile_id = self._playlist_profile_id()
            picker = self._controller.create_playlist_picker(station, profile_id=profile_id)
        except Exception as exc:
            self._set_status(f"Could not open playlist picker: {exc}")
            return
        if not picker.names:
            self._set_status("Create a saved playlist with New playlist… first.")
            return
        dialog, content = self._make_playlist_dialog("Add to playlist", "Add")
        content.append(self._make_value_label(f"Add {station_name(station)} to a saved playlist."))
        dropdown = Gtk.DropDown.new_from_strings(list(picker.names))
        dropdown.set_enable_search(True)
        content.append(dropdown)
        content.append(
            self._make_value_label("Adding a station to a playlist also saves it to favorites.")
        )
        error = self._make_value_label()
        content.append(error)

        def respond(current: Gtk.Dialog, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                current.destroy()
                return
            try:
                if self._playlist_profile_id() != profile_id:
                    raise ValueError("The profile changed. Reopen this dialog.")
                index = dropdown.get_selected()
                if index < 0 or index >= len(picker.names):
                    raise ValueError("Choose a playlist.")
                name = picker.names[index]
                added = picker.add(name)
            except Exception as exc:
                error.set_text(str(exc))
                return
            current.destroy()
            self._refresh_favorite_cache()
            if (
                self._view_state.current_view == "playlist"
                and self._view_state.active_playlist_name == name
            ):
                self._show_saved_playlist(name, preserve_selection=True)
            else:
                self._refresh_saved_playlists()
                self._render_results()
            self._set_status(
                f"Added to playlist: {name}."
                if added
                else f"Station is already in playlist: {name}."
            )

        dialog.connect("response", respond)
        dialog.present()

    def on_context_remove_playlist_clicked(
        self, _button: Gtk.Button, station: dict[str, Any], name: str
    ) -> None:
        self.remove_station_from_saved_playlist(station, name)

    def remove_station_from_saved_playlist(self, station: dict[str, Any], name: str) -> None:
        try:
            profile_id = self._playlist_profile_id()
            removed = self._controller.remove_station_from_playlist(
                name, station, profile_id=profile_id
            )
        except Exception as exc:
            self._set_status(f"Could not remove station from playlist: {exc}")
            return
        if (
            self._view_state.current_view == "playlist"
            and self._view_state.active_playlist_name == name
        ):
            self._show_saved_playlist(name, preserve_selection=True)
        else:
            self._refresh_saved_playlists()
        self._set_status(
            "Removed from playlist. Station remains in favorites."
            if removed
            else "Station is no longer in this playlist."
        )

    def _build_saved_playlist_controls(self, side_panel: Gtk.Box) -> None:
        self._append_section_title(side_panel, "Saved playlists")
        self.saved_playlists_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        side_panel.append(self.saved_playlists_box)
        controls = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        create_button = Gtk.Button(label="New playlist…")
        create_button.connect("clicked", self.on_create_playlist_clicked)
        controls.append(create_button)
        self.delete_saved_playlist_button = Gtk.Button(label="Delete…")
        self.delete_saved_playlist_button.set_sensitive(False)
        self.delete_saved_playlist_button.connect("clicked", self.on_delete_playlist_clicked)
        controls.append(self.delete_saved_playlist_button)
        side_panel.append(controls)

    def _refresh_saved_playlists(self) -> None:
        child = self.saved_playlists_box.get_first_child()
        while child is not None:
            self.saved_playlists_box.remove(child)
            child = self.saved_playlists_box.get_first_child()
        try:
            profile_id = self._playlist_profile_id()
            playlists = self._controller.load_playlists(profile_id=profile_id)
            for playlist in playlists:
                name = playlist["name"]
                count = len(self._controller.get_playlist_stations(name, profile_id=profile_id))
                button = Gtk.Button(label=f"{name} · {count}")
                button.set_tooltip_text(name)
                button.connect("clicked", self.on_saved_playlist_clicked, name)
                if self._view_state.active_playlist_name == name:
                    button.add_css_class("suggested-action")
                self.saved_playlists_box.append(button)
            if not playlists:
                self.saved_playlists_box.append(self._make_value_label("No saved playlists yet."))
        except Exception as exc:
            self.saved_playlists_box.append(self._make_value_label("Could not load playlists."))
            self._set_status(f"Could not load playlists: {exc}")

    def _show_saved_playlist(self, name: str, *, preserve_selection: bool = False) -> None:
        try:
            profile_id = self._playlist_profile_id()
            if self._controller.get_playlist(name, profile_id=profile_id) is None:
                raise ValueError("This playlist no longer exists.")
            stations = self._controller.get_playlist_stations(name, profile_id=profile_id)
        except Exception as exc:
            self._set_status(f"Could not open playlist: {exc}")
            return
        selected_key = (
            station_key(self.selected_station)
            if preserve_selection and self.selected_station is not None
            else None
        )
        self._invalidate_search()
        self._view_state.show_playlist(name)
        self._refresh_favorite_cache()
        self.stations = stations
        self.selected_station = next(
            (station for station in stations if station_key(station) == selected_key), None
        )
        self._render_results()
        self._update_playlist_status()
        self._refresh_saved_playlists()
        self._set_view_status(
            "Playlist",
            len(stations),
            detail=name,
            empty_message=f"Playlist {name} is empty. Add stations from their context menu.",
        )

    def on_saved_playlist_clicked(self, _button: Gtk.Button, name: str) -> None:
        self._show_saved_playlist(name)

    def _make_playlist_dialog(self, title: str, action: str) -> tuple[Gtk.Dialog, Gtk.Box]:
        dialog = Gtk.Dialog(title=title, transient_for=self._parent, modal=True)
        dialog.set_default_size(380, -1)
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button(action, Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.ACCEPT)
        content = dialog.get_content_area()
        content.set_spacing(10)
        content.set_margin_top(16)
        content.set_margin_bottom(16)
        content.set_margin_start(16)
        content.set_margin_end(16)
        return (dialog, content)

    def on_create_playlist_clicked(self, _button: Gtk.Button) -> None:
        try:
            profile_id = self._playlist_profile_id()
        except Exception as exc:
            self._set_status(f"Could not create playlist: {exc}")
            return
        dialog, content = self._make_playlist_dialog("New playlist", "Create")
        entry = Gtk.Entry()
        entry.set_placeholder_text("Playlist name")
        entry.set_activates_default(True)
        content.append(entry)
        error = self._make_value_label()
        content.append(error)

        def respond(current: Gtk.Dialog, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                current.destroy()
                return
            try:
                name = entry.get_text().strip()
                if not name:
                    raise ValueError("Enter a playlist name.")
                if self._playlist_profile_id() != profile_id:
                    raise ValueError("The profile changed. Reopen this dialog.")
                if not self._controller.create_playlist(name, profile_id=profile_id):
                    raise ValueError("A playlist with this name already exists.")
            except Exception as exc:
                error.set_text(str(exc))
                return
            current.destroy()
            self._show_saved_playlist(name)

        dialog.connect("response", respond)
        dialog.present()
        entry.grab_focus()

    def on_delete_playlist_clicked(self, _button: Gtk.Button) -> None:
        name = self._view_state.active_playlist_name
        if self._view_state.current_view != "playlist" or name is None:
            return
        try:
            profile_id = self._playlist_profile_id()
        except Exception as exc:
            self._set_status(f"Could not delete playlist: {exc}")
            return
        dialog, content = self._make_playlist_dialog("Delete playlist", "Delete")
        delete_button = dialog.get_widget_for_response(Gtk.ResponseType.ACCEPT)
        if delete_button is not None:
            delete_button.add_css_class("destructive-action")
        content.append(
            self._make_value_label(f'Delete "{name}"? Its stations will remain in your favorites.')
        )
        error = self._make_value_label()
        content.append(error)

        def respond(current: Gtk.Dialog, response: int) -> None:
            if response != Gtk.ResponseType.ACCEPT:
                current.destroy()
                return
            try:
                if self._playlist_profile_id() != profile_id:
                    raise ValueError("The profile changed. Reopen this dialog.")
                removed = self._controller.delete_playlist(name, profile_id=profile_id)
            except Exception as exc:
                error.set_text(str(exc))
                return
            current.destroy()
            if self._view_state.active_playlist_name == name:
                self._show_all_favorites()
            self._refresh_saved_playlists()
            self._set_status("Playlist deleted." if removed else "Playlist was already deleted.")

        dialog.connect("response", respond)
        dialog.present()

    def _build_playlist_controls(self, side_panel: Gtk.Box) -> None:
        self.favorite_filters_expander = Gtk.Expander(label="Filter favorites")
        self.favorite_filters_expander.set_expanded(False)
        side_panel.append(self.favorite_filters_expander)
        playlist_controls = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        playlist_controls.set_hexpand(True)
        self.favorite_filters_expander.set_child(playlist_controls)
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
        for favorite in self._controller.load_favorites():
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
        self, station: dict[str, Any], *, custom_name: str, favorite_tags: list[str]
    ) -> None:
        if custom_name:
            station["custom_name"] = custom_name
        else:
            station.pop("custom_name", None)
        station["favorite_tags"] = favorite_tags

    def _update_visible_favorite(
        self, key: str, *, custom_name: str, favorite_tags: list[str]
    ) -> None:
        for station in self.stations:
            if self._station_url(station) != key:
                continue
            self._apply_favorite_edits_to_station(
                station, custom_name=custom_name, favorite_tags=favorite_tags
            )
            self.selected_station = station
            break
        if self.current_station and self._station_url(self.current_station) == key:
            self._apply_favorite_edits_to_station(
                self.current_station, custom_name=custom_name, favorite_tags=favorite_tags
            )

    def _update_favorite_buttons(self) -> None:
        if not hasattr(self, "add_favorite_button"):
            return
        selected_station = self.selected_station
        has_selection = selected_station is not None
        is_favorite = bool(
            selected_station is not None and self._is_favorite_station(selected_station)
        )
        self.add_favorite_button.set_sensitive(has_selection and (not is_favorite))
        self.remove_favorite_button.set_sensitive(has_selection and is_favorite)
        if hasattr(self, "favorite_name_entry"):
            self.favorite_name_entry.set_sensitive(is_favorite)
            self.edit_favorite_tags_entry.set_sensitive(is_favorite)
            self.save_favorite_button.set_sensitive(is_favorite)
        self._populate_favorite_edit_fields()

    def add_station_to_favorites(self, station: dict[str, Any]) -> bool:
        """Add one explicit station to favorites without changing selection."""
        key = station_key(station)
        if not key:
            self._set_status("Selected station has no favorite URL.")
            self._update_favorite_buttons()
            return False
        if self._controller.add_favorite(station):
            self._refresh_favorite_cache()
            self._render_results()
            self._set_status("Added to favorites.")
            return True
        self._set_status("Station is already in favorites or has no URL.")
        self._update_favorite_buttons()
        return False

    def remove_station_from_favorites(self, station: dict[str, Any]) -> bool:
        """Remove one explicit station from favorites without changing selection."""
        key = station_key(station)
        if not key:
            self._set_status("Selected station has no favorite URL.")
            self._update_favorite_buttons()
            return False
        selected_key = (
            station_key(self.selected_station) if self.selected_station is not None else None
        )
        if self._controller.remove_favorite(key):
            self._refresh_favorite_cache()
            self._set_status("Removed from favorites.")
            if self._view_state.current_view == "favorites":
                self.stations = self._controller.load_favorites()
                if selected_key and selected_key != key:
                    self.selected_station = next(
                        (
                            candidate
                            for candidate in self.stations
                            if station_key(candidate) == selected_key
                        ),
                        None,
                    )
                else:
                    self.selected_station = None
            if hasattr(self, "saved_playlists_box"):
                if self._view_state.current_view == "playlist":
                    name = self._view_state.active_playlist_name
                    if name is not None:
                        self._show_saved_playlist(name, preserve_selection=True)
                else:
                    self._refresh_saved_playlists()
            self._render_results()
            self._update_favorite_buttons()
            return True
        self._set_status("Selected station is not in favorites.")
        self._update_favorite_buttons()
        return False

    def on_context_add_favorite_clicked(self, _button: Gtk.Button, station: dict[str, Any]) -> None:
        """Add the station targeted by a context-menu action."""
        self.add_station_to_favorites(station)

    def on_context_remove_favorite_clicked(
        self, _button: Gtk.Button, station: dict[str, Any]
    ) -> None:
        """Remove the station targeted by a context-menu action."""
        self.remove_station_from_favorites(station)

    def on_add_favorite_clicked(self, _button: Gtk.Button) -> None:
        if not self.selected_station:
            self._set_status("Select a station first.")
            self._update_favorite_buttons()
            return
        self.add_station_to_favorites(self.selected_station)

    def on_save_favorite_clicked(self, _button: Gtk.Button) -> None:
        favorite = self._selected_favorite_record()
        if not favorite:
            self._set_status("Select a favorite first.")
            self._update_favorite_buttons()
            return
        key = station_key(favorite)
        if not key:
            self._set_status("Selected favorite has no URL.")
            self._update_favorite_buttons()
            return
        favorite_name = self._favorite_edit_name_from_entry()
        favorite_tags = self._favorite_edit_tags_from_entry()
        if not self._controller.update_favorite(
            key, custom_name=favorite_name, favorite_tags=favorite_tags
        ):
            self._set_status("Could not update favorite.")
            self._update_favorite_buttons()
            return
        self._refresh_favorite_cache()
        self._update_visible_favorite(key, custom_name=favorite_name, favorite_tags=favorite_tags)
        self._render_results()
        self.update_now_playing()
        self._set_status("Favorite updated.")

    def on_remove_favorite_clicked(self, _button: Gtk.Button) -> None:
        if not self.selected_station:
            self._set_status("Select a station first.")
            self._update_favorite_buttons()
            return
        self.remove_station_from_favorites(self.selected_station)

    def _show_all_favorites(self) -> int:
        """Show all saved favorites and reset playlist filtering state."""
        self._invalidate_search()
        self._view_state.show_favorites()
        self._refresh_favorite_cache()
        self.stations = self._controller.load_favorites()
        self.selected_station = None
        self._render_results()
        self._update_playlist_status()
        return len(self.stations)

    def _set_favorites_status(self, count: int) -> None:
        self._set_view_status("Favorites", count, empty_message="No favorite stations yet.")

    def on_show_favorites_clicked(self, _button: Gtk.Button) -> None:
        self._set_favorites_status(self._show_all_favorites())

    def _show_history(self) -> int:
        """Show recently played stations in the main results list."""
        self._invalidate_search()
        self._view_state.show_history()
        self._refresh_favorite_cache()
        self.stations = self._controller.load_history()
        self.selected_station = None
        self._render_results()
        self._update_playlist_status()
        return len(self.stations)

    def on_show_history_clicked(self, _button: Gtk.Button) -> None:
        count = self._show_history()
        self._set_view_status("History", count, empty_message="No recently played stations yet.")

    def _update_playlist_status(self) -> None:
        if not hasattr(self, "playlist_status_label"):
            return
        if self._view_state.active_playlist_tag:
            self.playlist_status_label.set_text(
                f"Active tag: {self._view_state.active_playlist_tag}"
            )
        elif self._view_state.active_playlist_name:
            self.playlist_status_label.set_text(
                f"Playlist: {self._view_state.active_playlist_name}"
            )
        else:
            self.playlist_status_label.set_text("No favorite tag filter")
        if hasattr(self, "delete_saved_playlist_button"):
            self.delete_saved_playlist_button.set_sensitive(
                self._view_state.current_view == "playlist"
            )

    def _playlist_tag_value(self) -> str:
        if not hasattr(self, "playlist_tag_entry"):
            return ""
        return self.playlist_tag_entry.get_text().strip()

    def on_show_tags_clicked(self, _button: Gtk.Button) -> None:
        tags = self._all_favorite_playlist_tags()
        if not tags:
            self._set_status("No custom favorite tags found yet.")
            return
        self._set_status("Favorite tags: " + ", ".join(tags))

    def on_show_tag_playlist_clicked(self, _widget: Gtk.Widget) -> None:
        tag = self._playlist_tag_value()
        if not tag:
            tags = self._all_favorite_playlist_tags()
            if tags:
                self._set_status("Type a tag. Available: " + ", ".join(tags))
            else:
                self._set_status("No custom favorite tags found yet.")
            return
        stations = self._favorites_matching_favorite_tag(tag)
        self._invalidate_search()
        self._view_state.show_tag_playlist(tag)
        self._refresh_favorite_cache()
        self.stations = stations
        self.selected_station = None
        self._render_results()
        self._update_playlist_status()
        self._set_view_status("Tag playlist", len(stations), detail=tag)

    def on_random_tag_clicked(self, _button: Gtk.Button) -> None:
        import secrets

        tag = self._playlist_tag_value()
        if not tag:
            tags = self._all_favorite_playlist_tags()
            if tags:
                self._set_status("Type a tag first. Available: " + ", ".join(tags))
            else:
                self._set_status("No tags found in favorites yet.")
            return
        stations = filter_supported_stations(
            self._favorites_matching_favorite_tag(tag), self.player_capabilities
        )
        if not stations:
            self._set_status(f"No compatible favorite stations found for tag: {tag}")
            return
        self._invalidate_search()
        self._view_state.show_tag_playlist(tag)
        self._refresh_favorite_cache()
        self.stations = stations
        self.selected_station = secrets.choice(stations)
        self._render_results()
        self._update_playlist_status()
        self.play_selected_station()

    def on_clear_playlist_filter_clicked(self, _button: Gtk.Button) -> None:
        if hasattr(self, "playlist_tag_entry"):
            self.playlist_tag_entry.set_text("")
        self._set_favorites_status(self._show_all_favorites())
