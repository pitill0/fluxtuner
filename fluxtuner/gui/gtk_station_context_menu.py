"""GTK station context actions with explicit station targets and collaborators."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk  # noqa: E402

from fluxtuner.core.recording import RecordingManager  # noqa: E402
from fluxtuner.core.ripping_service import RippingService  # noqa: E402
from fluxtuner.core.stations import station_url  # noqa: E402
from fluxtuner.gui.gtk_library_panel import LibraryPanel  # noqa: E402
from fluxtuner.gui.gtk_ripping import ripping_menu_action  # noqa: E402
from fluxtuner.gui.gtk_ripping_controller import RippingController  # noqa: E402
from fluxtuner.gui.gtk_shutdown import ShutdownController  # noqa: E402
from fluxtuner.gui.gtk_view_state import ViewState  # noqa: E402


class StationContextMenu:
    """Compose contextual GTK actions without owning library or backend lifecycle state."""

    def __init__(
        self,
        *,
        library: LibraryPanel,
        view_state: ViewState,
        recording_manager: RecordingManager,
        recording_available: bool,
        ripping_service: RippingService,
        ripping_controller: Callable[[], RippingController],
        shutdown: ShutdownController,
        profile_context: Callable[[], tuple[int, str]],
        is_favorite: Callable[[dict[str, Any]], bool],
        display_name: Callable[[dict[str, Any]], str],
        get_display: Callable[[], Any],
        status_label: Callable[[], Any],
        play: Callable[[Gtk.Button, dict[str, Any]], None],
        record: Callable[[Gtk.Button, dict[str, Any]], None],
        stop_recording: Callable[[Gtk.Button, dict[str, Any]], None],
        rip: Callable[[Gtk.Button, dict[str, Any]], None],
        stop_ripping: Callable[[Gtk.Button, dict[str, Any]], None],
    ) -> None:
        self._library = library
        self._view_state = view_state
        self.recording_manager = recording_manager
        self.recording_available = recording_available
        self.ripping_service = ripping_service
        self._get_ripping_controller = ripping_controller
        self._shutdown_controller = shutdown
        self._ripping_profile_context = profile_context
        self._is_favorite_station = is_favorite
        self._station_display_name = display_name
        self._station_url = station_url
        self.get_display = get_display
        self._get_status_label = status_label
        self.on_context_play_clicked = play
        self.on_context_record_clicked = record
        self.on_context_stop_recording_clicked = stop_recording
        self.on_context_rip_clicked = rip
        self.on_context_stop_ripping_clicked = stop_ripping

    @property
    def _ripping_controller(self) -> RippingController:
        return self._get_ripping_controller()

    @property
    def status_label(self) -> Any:
        return self._get_status_label()

    def _station_from_context_row(
        self,
        row: Gtk.ListBoxRow,
    ) -> dict[str, Any] | None:
        """Return the station bound to a contextual-menu row."""
        return getattr(row, "station", None)

    def _clipboard_set_text(self, text: str) -> None:
        """Copy text to the GTK clipboard."""
        clipboard = self.get_display().get_clipboard()
        clipboard.set(text)

    def _open_external_uri(self, uri: str) -> None:
        """Open one external URI with the desktop default application."""
        from gi.repository import Gio

        Gio.AppInfo.launch_default_for_uri(uri, None)

    def _station_homepage_url(
        self,
        station: dict[str, Any],
    ) -> str | None:
        """Return a safe HTTP(S) homepage URL for one station."""
        from urllib.parse import urlparse

        homepage = str(station.get("homepage") or "").strip()
        if not homepage:
            return None

        parsed = urlparse(homepage)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return None

        return homepage

    def open_station_homepage(
        self,
        station: dict[str, Any],
    ) -> None:
        """Open one explicit station homepage without changing selection."""
        raw_homepage = str(station.get("homepage") or "").strip()
        if not raw_homepage:
            self.status_label.set_text("Station has no homepage.")
            return

        homepage = StationContextMenu._station_homepage_url(self, station)
        if homepage is None:
            self.status_label.set_text("Station homepage URL is not safe to open.")
            return

        try:
            self._open_external_uri(homepage)
        except Exception as exc:  # noqa: BLE001 - user-facing GTK status.
            self.status_label.set_text(f"Could not open station homepage: {exc}")

    def on_context_open_homepage_clicked(
        self,
        _button: Gtk.Button,
        station: dict[str, Any],
    ) -> None:
        """Open the homepage for the station targeted by the context menu."""
        self.open_station_homepage(station)

    def copy_station_url(
        self,
        _button: Gtk.Button,
        station: dict[str, Any],
    ) -> None:
        """Copy one explicit station URL without changing selection."""
        source_url = self._station_url(station)
        if not source_url:
            self.status_label.set_text("Station has no stream URL to copy.")
            return

        self._clipboard_set_text(source_url)

    def copy_station_name(
        self,
        _button: Gtk.Button,
        station: dict[str, Any],
    ) -> None:
        """Copy one explicit station display name without changing selection."""
        self._clipboard_set_text(self._station_display_name(station))

    def _show_station_context_menu(
        self,
        row: Gtk.ListBoxRow,
        station: dict[str, Any],
        x: float,
        y: float,
    ) -> None:
        """Show contextual actions bound to one explicit station row."""
        from gi.repository import Gdk

        popover = Gtk.Popover()
        popover.set_parent(row)

        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        menu_box.set_margin_top(6)
        menu_box.set_margin_bottom(6)
        menu_box.set_margin_start(6)
        menu_box.set_margin_end(6)

        play_button = Gtk.Button(label="Play")
        play_button.connect("clicked", self.on_context_play_clicked, station)
        menu_box.append(play_button)

        if self._is_favorite_station(station):
            favorite_button = Gtk.Button(label="Remove from favorites")
            favorite_button.connect(
                "clicked",
                self._library.on_context_remove_favorite_clicked,
                station,
            )
        else:
            favorite_button = Gtk.Button(label="Add to favorites")
            favorite_button.connect(
                "clicked",
                self._library.on_context_add_favorite_clicked,
                station,
            )
        menu_box.append(favorite_button)

        playlist_button = Gtk.Button(label="Add to playlist…")
        playlist_button.connect("clicked", self._library.on_context_add_playlist_clicked, station)
        menu_box.append(playlist_button)

        view_state = getattr(self, "_view_state", None)
        if view_state is not None and view_state.current_view == "playlist":
            playlist_name = view_state.active_playlist_name
            if playlist_name is not None:
                remove_button = Gtk.Button(label="Remove from playlist")
                remove_button.connect(
                    "clicked",
                    self._library.on_context_remove_playlist_clicked,
                    station,
                    playlist_name,
                )
                menu_box.append(remove_button)

        recording_manager = getattr(self, "recording_manager", None)
        if recording_manager is not None:
            active_session = recording_manager.active_session
            if active_session is None:
                if getattr(self, "recording_available", False):
                    record_button = Gtk.Button(label="Record session")
                    record_button.connect(
                        "clicked",
                        self.on_context_record_clicked,
                        station,
                    )
                    menu_box.append(record_button)
            elif StationContextMenu._is_station_recording(self, station):
                stop_recording_button = Gtk.Button(label="Stop recording")
                stop_recording_button.connect(
                    "clicked",
                    self.on_context_stop_recording_clicked,
                    station,
                )
                menu_box.append(stop_recording_button)

        ripping_action = None
        ripping_service = getattr(self, "ripping_service", None)
        if ripping_service is not None and not self._shutdown_controller.shutting_down:
            try:
                profile_id, _profile_name = self._ripping_profile_context()
                workers_finished = ripping_service.wait(timeout=0)
                snapshot = ripping_service.snapshot()
                ripping_action = ripping_menu_action(
                    station,
                    availability=self._ripping_controller.availability,
                    snapshot=snapshot,
                    workers_finished=workers_finished,
                    profile_id=profile_id,
                )
            except Exception as exc:  # noqa: BLE001 - contained optional menu action.
                self.status_label.set_text(f"Could not check ripping actions: {exc}")

        if ripping_action is not None:
            ripping_button = Gtk.Button(
                label="Rip tracks" if ripping_action == "start" else "Stop ripping"
            )
            ripping_button.connect(
                "clicked",
                self.on_context_rip_clicked
                if ripping_action == "start"
                else self.on_context_stop_ripping_clicked,
                station,
            )
            menu_box.append(ripping_button)

        if StationContextMenu._station_homepage_url(self, station) is not None:
            homepage_button = Gtk.Button(label="Open station homepage")
            homepage_button.connect(
                "clicked",
                self.on_context_open_homepage_clicked,
                station,
            )
            menu_box.append(homepage_button)

        copy_url_button = Gtk.Button(label="Copy stream URL")
        copy_url_button.connect("clicked", self.copy_station_url, station)
        menu_box.append(copy_url_button)

        copy_name_button = Gtk.Button(label="Copy station name")
        copy_name_button.connect("clicked", self.copy_station_name, station)
        menu_box.append(copy_name_button)

        popover.set_child(menu_box)
        popover.connect("closed", self._on_station_context_menu_closed)
        popover.set_pointing_to(
            Gdk.Rectangle(
                int(x),
                int(y),
                1,
                1,
            )
        )
        popover.popup()

    def _on_station_context_menu_closed(
        self,
        popover: Gtk.Popover,
    ) -> None:
        """Detach a closed contextual popover from its station row."""
        popover.unparent()

    def on_row_context_click(
        self,
        _gesture: Gtk.GestureClick,
        n_press: int,
        x: float,
        y: float,
        row: Gtk.ListBoxRow,
    ) -> None:
        """Open the station context menu for the explicitly targeted row."""
        if n_press != 1:
            return

        station = self._station_from_context_row(row)
        if station is None:
            return

        self._show_station_context_menu(row, station, x, y)

    def _is_station_recording(
        self,
        station: dict[str, Any],
    ) -> bool:
        """Return True when the active recording belongs to one station."""
        active_session = self.recording_manager.active_session
        if active_session is None:
            return False

        source_url = self._station_url(station)
        if not source_url:
            return False

        return active_session.source_url == source_url
