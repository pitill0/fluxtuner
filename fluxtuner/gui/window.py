"""Experimental GTK desktop window for FluxTuner."""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from time import monotonic
from typing import Any, Literal

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango  # noqa: E402

from fluxtuner import __app_name__, __version__  # noqa: E402
from fluxtuner.config import (  # noqa: E402
    get_config_value,
    get_playback_state,
    save_playback_state,
    set_config_value,
)
from fluxtuner.core import db, manual_playlists  # noqa: E402
from fluxtuner.core.compatibility import (  # noqa: E402
    filter_supported_stations,
    station_is_supported,
    unsupported_station_message,
)
from fluxtuner.core.custom_stations import add_custom_station  # noqa: E402
from fluxtuner.core.data_usage import DataUsageTracker, format_usage_line  # noqa: E402
from fluxtuner.core.discovery_execution import search_desktop_stations  # noqa: E402
from fluxtuner.core.favorites import (  # noqa: E402
    add_favorite,
    all_favorite_tags,
    favorite_display_name,
    filter_favorites_by_tag,
    load_favorites,
    remove_favorite,
    update_favorite,
)
from fluxtuner.core.history import add_history, load_history  # noqa: E402
from fluxtuner.core.profiles import (  # noqa: E402
    get_profile_by_name,
    resolve_effective_profile_name,
)
from fluxtuner.core.recording import RecordingManager  # noqa: E402
from fluxtuner.core.recordings import (  # noqa: E402
    SqliteRecordingStore,
    recording_output_path,
)
from fluxtuner.core.ripping import RippingError  # noqa: E402
from fluxtuner.core.ripping_service import RippingService  # noqa: E402
from fluxtuner.core.search_service import SearchRequest, SearchService  # noqa: E402
from fluxtuner.core.stations import (  # noqa: E402
    same_station,
    station_bitrate,
    station_codec,
    station_country,
    station_key,
    station_name,
    station_tags_text,
    station_url,
)
from fluxtuner.core.stream_metadata import fetch_stream_metadata  # noqa: E402
from fluxtuner.gui.appearance import (  # noqa: E402
    AppearanceMode,
    GtkAppearanceManager,
    normalize_appearance,
)
from fluxtuner.gui.gtk_m3u_import import (  # noqa: E402
    open_m3u_import,
    open_remote_m3u_import,
)
from fluxtuner.gui.gtk_metadata import MetadataLifecycle  # noqa: E402
from fluxtuner.gui.gtk_playback import (  # noqa: E402
    coordinate_playback_start,
    coordinate_playback_stop,
)
from fluxtuner.gui.gtk_playlists import create_playlist_picker  # noqa: E402
from fluxtuner.gui.gtk_recording import RecordingController  # noqa: E402
from fluxtuner.gui.gtk_recording_shutdown import AsyncRecordingStop  # noqa: E402
from fluxtuner.gui.gtk_ripping import (  # noqa: E402
    RippingShutdown,
    ripping_menu_action,
    shutdown_has_pending_recordings,
)
from fluxtuner.gui.gtk_ripping_controller import RippingController  # noqa: E402
from fluxtuner.gui.gtk_search import SearchLifecycle  # noqa: E402
from fluxtuner.gui.gtk_view_state import ViewState  # noqa: E402
from fluxtuner.paths import DATA_DIR  # noqa: E402
from fluxtuner.players import create_player, selected_player_name  # noqa: E402
from fluxtuner.recorders.brynse import BrynseRipper  # noqa: E402
from fluxtuner.recorders.ffmpeg import FfmpegRecorder  # noqa: E402


class MainWindow(Gtk.ApplicationWindow):
    """GTK desktop GUI: search stations, list results and play selection."""

    def __init__(
        self,
        app: Gtk.Application,
        player_name: str = "mpv",
        appearance_manager: GtkAppearanceManager | None = None,
    ) -> None:
        super().__init__(application=app)
        self.set_title("FluxTuner")
        self.set_default_size(980, 620)
        self.set_size_request(520, 420)
        self.appearance_manager = appearance_manager
        self.configured_appearance = normalize_appearance(
            get_config_value("gtk_appearance", "system")
        )
        self.close_to_tray = False

        self.player_backend_name = selected_player_name(player_name)
        self.profile_name = resolve_effective_profile_name()
        self.player = create_player(self.player_backend_name)
        self.player_capabilities = self.player.capabilities()
        self.recording_backend = FfmpegRecorder()
        self.recording_available = self.recording_backend.is_available()
        self.recording_manager = RecordingManager(
            self.recording_backend,
            store=SqliteRecordingStore(profile_name=self.profile_name),
        )
        ripping_backend = BrynseRipper()
        self.ripping_service = RippingService(backend_factory=BrynseRipper)
        self._ripping_shutdown = RippingShutdown(service=self.ripping_service)
        self._shutdown_timer_id: int | None = None
        self._shutdown_on_complete: Callable[[], None] | None = None
        self._quit_confirmation_pending = False
        self._recording_shutdown = AsyncRecordingStop(stop=self.recording_manager.stop)
        self._shutdown_deadline: float | None = None
        self._shutdown_warning_open = False
        self._shutdown_close_authorized = False
        self._ripping_shutting_down = False
        self.search_service = SearchService(capabilities=self.player_capabilities)
        self.usage_tracker = DataUsageTracker()
        self._usage_timer_id: int | None = None
        self._player_state_timer_id: int | None = None
        self.stations: list[dict[str, Any]] = []
        self.selected_station: dict[str, Any] | None = None
        self.current_station: dict[str, Any] | None = None
        self._metadata_timer_id: int | None = None
        self._metadata_lifecycle = MetadataLifecycle()
        self._search_lifecycle = SearchLifecycle()
        self._view_state = ViewState()
        self.last_search_results: list[dict[str, Any]] = []
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
        self._refresh_saved_playlists()
        self._ripping_controller = RippingController(
            service=self.ripping_service,
            check_availability=ripping_backend.availability,
            profile_context=self._ripping_profile_context,
            data_directory=DATA_DIR,
            show_status=self.status_label.set_text,
            is_shutting_down=lambda: self._ripping_shutting_down,
            schedule=GLib.timeout_add,
            remove_source=GLib.source_remove,
            dispatch=GLib.idle_add,
        )
        self._ripping_controller.probe_availability()

    def start_station_ripping(self, station: dict[str, Any]) -> int | None:
        """Submit one explicit station without changing the current selection."""
        return self._ripping_controller.start(station)

    def stop_station_ripping(self, station: dict[str, Any]) -> None:
        """Request stopping for an explicit station in the window's profile."""
        self._ripping_controller.stop(station)

    def on_context_rip_clicked(
        self,
        _button: Gtk.Button,
        station: dict[str, Any],
    ) -> None:
        """Start ripping the station targeted by a context-menu action."""
        self.start_station_ripping(station)

    def on_context_stop_ripping_clicked(
        self,
        _button: Gtk.Button,
        station: dict[str, Any],
    ) -> None:
        """Stop ripping for the station targeted by a context-menu action."""
        self.stop_station_ripping(station)

    def _ripping_profile_context(self) -> tuple[int, str]:
        """Resolve the window's persistent profile and its canonical name."""
        name = self.profile_name
        if name is None:
            name = db.DEFAULT_PROFILE_NAME

        with db.connect() as conn:
            profile = get_profile_by_name(conn, name)

        if profile is None:
            raise RippingError("Ripping profile is unavailable.")

        return int(profile["id"]), str(profile["name"])

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
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_hexpand(True)
        root.append(header)

        title_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        title_box.set_hexpand(True)
        header.append(title_box)

        title = Gtk.Label(label="FluxTuner")
        title.set_xalign(0)
        title.add_css_class("title-1")
        title_box.append(title)

        subtitle = Gtk.Label(label="GTK desktop GUI")
        subtitle.set_xalign(0)
        subtitle.add_css_class("dim-label")
        title_box.append(subtitle)

        self._build_application_menu(header)

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

        self.search_source_dropdown = Gtk.DropDown.new_from_strings(
            ["Radio Browser", "Local", "All"]
        )
        self.search_source_dropdown.set_selected(0)
        self.search_source_dropdown.set_tooltip_text("Station discovery source")
        search_bar.append(self.search_source_dropdown)
        self.search_source_dropdown.connect("notify::selected", self._on_search_source_changed)

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

        self._build_library_controls(side_panel)
        self._build_saved_playlist_controls(side_panel)

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

    def _build_application_menu(self, container: Gtk.Box) -> None:
        self.application_menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        self.application_menu_button.set_tooltip_text("Application menu")
        self.application_menu_button.set_halign(Gtk.Align.END)
        self.application_menu_button.set_valign(Gtk.Align.CENTER)

        self.application_menu_popover = Gtk.Popover()
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)

        self._build_appearance_controls(content)

        add_station_button = Gtk.Button(label="Add station…")
        add_station_button.connect("clicked", self.on_add_custom_station_clicked)
        content.append(add_station_button)

        import_button = Gtk.Button(label="Import stations…")
        import_button.connect("clicked", self.on_import_stations_clicked)
        content.append(import_button)

        remote_import_button = Gtk.Button(label="Import stations from URL…")
        remote_import_button.connect("clicked", self.on_import_stations_url_clicked)
        content.append(remote_import_button)

        about_button = Gtk.Button(label="About FluxTuner")
        about_button.connect("clicked", self.on_about_clicked)
        content.append(about_button)

        quit_button = Gtk.Button(label="Quit")
        quit_button.set_action_name("app.quit")
        content.append(quit_button)

        self.application_menu_popover.set_child(content)
        self.application_menu_button.set_popover(self.application_menu_popover)
        container.append(self.application_menu_button)

    def on_import_stations_clicked(self, _button: Gtk.Button) -> None:
        popover = getattr(self, "application_menu_popover", None)
        if popover is not None:
            popover.popdown()
        try:
            profile_id = self._playlist_profile_id()
        except Exception as exc:  # noqa: BLE001 - contained GTK profile failure.
            self.status_label.set_text(f"Could not import stations: {exc}")
            return
        open_m3u_import(
            self,
            profile_id=profile_id,
            profile_is_current=lambda: self._playlist_profile_id() == profile_id,
            on_saved=self._on_m3u_import_saved,
            on_error=self.status_label.set_text,
        )

    def on_import_stations_url_clicked(self, _button: Gtk.Button) -> None:
        popover = getattr(self, "application_menu_popover", None)
        if popover is not None:
            popover.popdown()
        try:
            profile_id = self._playlist_profile_id()
        except Exception as exc:  # noqa: BLE001 - contained GTK profile failure.
            self.status_label.set_text(f"Could not import stations: {exc}")
            return
        open_remote_m3u_import(
            self,
            profile_id=profile_id,
            profile_is_current=lambda: self._playlist_profile_id() == profile_id,
            on_saved=self._on_m3u_import_saved,
            on_error=self.status_label.set_text,
        )

    def _on_m3u_import_saved(self, name: str, result: Any) -> None:
        self._refresh_saved_playlists()
        self._show_saved_playlist(name)
        self.status_label.set_text(
            f"Imported {result.added_to_playlist} into {name}; "
            f"{result.already_in_playlist} already in playlist. "
            f"Favorites: {result.added_favorites} new, {result.existing_favorites} kept."
        )

    def on_add_custom_station_clicked(self, _button: Gtk.Button) -> None:
        popover = getattr(self, "application_menu_popover", None)
        if popover is not None:
            popover.popdown()
        try:
            profile_id = self._playlist_profile_id()
        except Exception as exc:  # noqa: BLE001 - contained GTK profile failure.
            self.status_label.set_text(f"Could not add station: {exc}")
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
                with db.connect() as conn:
                    added = add_custom_station(
                        conn,
                        profile_id=profile_id,
                        name=name_entry.get_text(),
                        url=url_entry.get_text(),
                        record_manual_provenance=True,
                    )
                    conn.commit()
            except Exception as exc:  # noqa: BLE001 - contained GTK storage failure.
                error.set_text(str(exc))
                return
            current.destroy()
            self._show_all_favorites()
            self._refresh_saved_playlists()
            self.status_label.set_text(
                "Station added to favorites." if added else "Station is already in favorites."
            )

        dialog.connect("response", respond)
        dialog.present()
        name_entry.grab_focus()

    def on_about_clicked(self, _button: Gtk.Button) -> None:
        popover = getattr(self, "application_menu_popover", None)
        if popover is not None:
            popover.popdown()

        dialog = Gtk.AboutDialog(transient_for=self, modal=True)
        dialog.set_destroy_with_parent(True)
        from gi.repository import Gdk

        logo_path = Path(__file__).resolve().parent / "assets" / "io.github.pitill0.Fluxtuner.png"
        dialog.set_logo(Gdk.Texture.new_from_filename(str(logo_path)))
        dialog.set_program_name(__app_name__)
        dialog.set_version(__version__)
        dialog.set_comments("Internet radio for terminal, desktop and web.")
        dialog.set_website("https://github.com/pitill0/fluxtuner")
        dialog.set_website_label("FluxTuner on GitHub")
        self._about_dialog = dialog
        dialog.present()

    def _build_appearance_controls(self, container: Gtk.Box) -> None:
        appearance_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        appearance_box.set_halign(Gtk.Align.END)
        appearance_box.set_valign(Gtk.Align.CENTER)
        container.append(appearance_box)

        appearance_label = Gtk.Label(label="Appearance")
        appearance_label.add_css_class("dim-label")
        appearance_box.append(appearance_label)

        self.appearance_dropdown = Gtk.DropDown.new_from_strings(["System", "Dark", "Light"])
        self.appearance_dropdown.set_tooltip_text("Choose the GTK appearance")
        self.appearance_dropdown.set_selected(
            {
                AppearanceMode.SYSTEM: 0,
                AppearanceMode.DARK: 1,
                AppearanceMode.LIGHT: 2,
            }[self.configured_appearance]
        )
        self.appearance_dropdown.connect(
            "notify::selected",
            self.on_appearance_changed,
        )
        appearance_box.append(self.appearance_dropdown)

    def on_appearance_changed(
        self,
        dropdown: Gtk.DropDown,
        _pspec: object,
    ) -> None:
        selected = dropdown.get_selected()
        modes = (
            AppearanceMode.SYSTEM,
            AppearanceMode.DARK,
            AppearanceMode.LIGHT,
        )
        if selected >= len(modes):
            return

        mode = modes[selected]
        self.configured_appearance = mode
        set_config_value("gtk_appearance", mode.value)

        if self.appearance_manager is not None:
            self.appearance_manager.apply(mode)

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

        self.record_button = Gtk.Button(label="● Record")
        self.record_button.set_size_request(140, -1)
        self.record_button.set_hexpand(False)
        self.record_button.set_tooltip_text("Record selected station")
        self.record_button.connect("clicked", self.on_record_clicked)
        self.record_button.set_sensitive(self.recording_available)
        playback_bar.append(self.record_button)

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
        supports_volume = self.player.supports_volume()
        self.volume_scale.set_tooltip_text(
            "Volume"
            if supports_volume
            else f"{self.player_backend_name} does not support live volume control."
        )
        self.volume_scale.connect("value-changed", self.on_volume_scale_changed)
        self.volume_scale.set_sensitive(supports_volume)
        playback_bar.append(self.volume_scale)

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

    def _favorites_matching_favorite_tag(self, tag: str) -> list[dict[str, Any]]:
        return filter_favorites_by_tag(tag)

    def _all_favorite_playlist_tags(self) -> list[str]:
        return all_favorite_tags()

    def on_context_add_playlist_clicked(self, _button: Gtk.Button, station: dict[str, Any]) -> None:
        self.open_playlist_picker(station)

    def open_playlist_picker(self, station: dict[str, Any]) -> None:
        try:
            profile_id = self._playlist_profile_id()
            picker = create_playlist_picker(station, profile_id=profile_id)
        except Exception as exc:  # noqa: BLE001 - contained GTK storage failure.
            self.status_label.set_text(f"Could not open playlist picker: {exc}")
            return
        if not picker.names:
            self.status_label.set_text("Create a saved playlist with New playlist… first.")
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
            except Exception as exc:  # noqa: BLE001 - contained GTK storage failure.
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
            self.status_label.set_text(
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
            removed = manual_playlists.remove_station_from_playlist(
                name, station, profile_id=profile_id
            )
        except Exception as exc:  # noqa: BLE001 - contained GTK storage failure.
            self.status_label.set_text(f"Could not remove station from playlist: {exc}")
            return
        if (
            self._view_state.current_view == "playlist"
            and self._view_state.active_playlist_name == name
        ):
            self._show_saved_playlist(name, preserve_selection=True)
        else:
            self._refresh_saved_playlists()
        self.status_label.set_text(
            "Removed from playlist. Station remains in favorites."
            if removed
            else "Station is no longer in this playlist."
        )

    def _playlist_profile_id(self) -> int:
        name = self.profile_name
        if name is None:
            name = db.DEFAULT_PROFILE_NAME
        with db.connect() as conn:
            profile = get_profile_by_name(conn, name)
        if profile is None:
            raise ValueError("The current profile is unavailable.")
        return int(profile["id"])

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
            playlists = manual_playlists.load_playlists(profile_id=profile_id)
            for playlist in playlists:
                name = playlist["name"]
                count = len(manual_playlists.get_playlist_stations(name, profile_id=profile_id))
                button = Gtk.Button(label=f"{name} · {count}")
                button.set_tooltip_text(name)
                button.connect("clicked", self.on_saved_playlist_clicked, name)
                if self._view_state.active_playlist_name == name:
                    button.add_css_class("suggested-action")
                self.saved_playlists_box.append(button)
            if not playlists:
                self.saved_playlists_box.append(self._make_value_label("No saved playlists yet."))
        except Exception as exc:  # noqa: BLE001 - contained GTK storage failure.
            self.saved_playlists_box.append(self._make_value_label("Could not load playlists."))
            self.status_label.set_text(f"Could not load playlists: {exc}")

    def _show_saved_playlist(self, name: str, *, preserve_selection: bool = False) -> None:
        try:
            profile_id = self._playlist_profile_id()
            if manual_playlists.get_playlist(name, profile_id=profile_id) is None:
                raise ValueError("This playlist no longer exists.")
            stations = manual_playlists.get_playlist_stations(name, profile_id=profile_id)
        except Exception as exc:  # noqa: BLE001 - contained GTK storage failure.
            self.status_label.set_text(f"Could not open playlist: {exc}")
            return

        selected_key = (
            station_key(self.selected_station)
            if preserve_selection and self.selected_station is not None
            else None
        )
        self._search_lifecycle.invalidate()
        self._view_state.show_playlist(name)
        self._refresh_favorite_cache()
        self.stations = stations
        self.selected_station = next(
            (station for station in stations if station_key(station) == selected_key),
            None,
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
        dialog = Gtk.Dialog(title=title, transient_for=self, modal=True)
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
        return dialog, content

    def on_create_playlist_clicked(self, _button: Gtk.Button) -> None:
        try:
            profile_id = self._playlist_profile_id()
        except Exception as exc:  # noqa: BLE001 - contained GTK profile failure.
            self.status_label.set_text(f"Could not create playlist: {exc}")
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
                if not manual_playlists.create_playlist(name, profile_id=profile_id):
                    raise ValueError("A playlist with this name already exists.")
            except Exception as exc:  # noqa: BLE001 - contained GTK storage failure.
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
        except Exception as exc:  # noqa: BLE001 - contained GTK profile failure.
            self.status_label.set_text(f"Could not delete playlist: {exc}")
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
                removed = manual_playlists.delete_playlist(name, profile_id=profile_id)
            except Exception as exc:  # noqa: BLE001 - contained GTK storage failure.
                error.set_text(str(exc))
                return
            current.destroy()
            if self._view_state.active_playlist_name == name:
                self._show_all_favorites()
            self._refresh_saved_playlists()
            self.status_label.set_text(
                "Playlist deleted." if removed else "Playlist was already deleted."
            )

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

    def _build_status_bar(self, root: Gtk.Box) -> None:
        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_hexpand(True)
        self.status_label.props.ellipsize = Pango.EllipsizeMode.END
        self.status_label.set_xalign(0)
        self.status_label.set_wrap(True)
        root.append(self.status_label)

    def _favorite_url_set(self) -> set[str]:
        return {
            key
            for item in load_favorites(profile_name=self.profile_name)
            if (key := station_key(item))
        }

    def _is_favorite_station(self, station: dict[str, Any]) -> bool:
        key = station_key(station)
        return bool(key and key in self.favorite_urls)

    def _refresh_favorite_cache(self) -> None:
        self.favorite_urls = self._favorite_url_set()

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
        self._append_cell(row_box, station_tags_text(station, fallback=""), 28, expand=True)
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

    def _station_url(self, station: dict[str, Any] | None) -> str | None:
        return station_url(station)

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

        homepage = MainWindow._station_homepage_url(self, station)
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

    def _set_view_status(
        self,
        view_name: str,
        count: int,
        *,
        detail: str | None = None,
        empty_message: str | None = None,
    ) -> None:
        """Set a consistent status message for list-like GUI views."""
        if count == 0 and empty_message:
            self.status_label.set_text(empty_message)
            return

        suffix = f" · {detail}" if detail else ""
        station_word = "station" if count == 1 else "stations"
        self.status_label.set_text(f"{view_name}{suffix} · {count} {station_word}")

    def _selected_search_source(self) -> Literal["radio-browser", "local", "all"]:
        sources: tuple[Literal["radio-browser", "local", "all"], ...] = (
            "radio-browser",
            "local",
            "all",
        )
        selected = self.search_source_dropdown.get_selected()
        if selected >= len(sources):
            raise ValueError("Unknown station discovery source.")
        return sources[selected]

    def _on_search_source_changed(self, _dropdown: Gtk.DropDown, _param: object) -> None:
        self._search_lifecycle.invalidate()
        self._view_state.show_search()
        self.last_search_results = []
        self.stations = []
        self.selected_station = None
        self._render_results()
        self._update_playlist_status()
        self._set_view_status("Search results", 0)

    def on_search_clicked(self, _widget: Gtk.Widget) -> None:
        query = self.search_entry.get_text().strip()
        country = self.country_entry.get_text().strip() or None
        min_bitrate_text = self.min_bitrate_entry.get_text().strip()
        min_bitrate = int(min_bitrate_text) if min_bitrate_text.isdigit() else None

        source = self._selected_search_source()
        profile_name = self.profile_name
        capabilities = self.player_capabilities
        generation = self._search_lifecycle.begin()
        self.status_label.set_text("Searching…")

        def worker() -> None:
            try:
                request = SearchRequest(
                    query=query,
                    country=country,
                    min_bitrate=min_bitrate,
                    limit=50,
                    source=source,
                )
                if source == "radio-browser":
                    result = self.search_service.search(request)
                else:
                    result = search_desktop_stations(
                        request,
                        profile_name=profile_name,
                        capabilities=capabilities,
                    )
                stations = result.stations
            except Exception as exc:  # noqa: BLE001 - user-facing status in GTK GUI.
                GLib.idle_add(self._search_failed, generation, str(exc))
                return

            GLib.idle_add(self._search_finished, generation, stations)

        threading.Thread(target=worker, daemon=True).start()

    def _search_failed(self, generation: int, message: str) -> bool:
        if not self._search_lifecycle.is_current(generation):
            return False
        self.status_label.set_text(f"Search failed: {message}")
        return False

    def _search_finished(
        self,
        generation: int,
        stations: list[dict[str, Any]],
    ) -> bool:
        if not self._search_lifecycle.is_current(generation):
            return False
        self._view_state.show_search()
        self.last_search_results = stations
        self.stations = stations
        self._render_results()
        self._update_playlist_status()
        self._set_view_status("Search results", len(stations))
        return False

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
                self.on_context_remove_favorite_clicked,
                station,
            )
        else:
            favorite_button = Gtk.Button(label="Add to favorites")
            favorite_button.connect(
                "clicked",
                self.on_context_add_favorite_clicked,
                station,
            )
        menu_box.append(favorite_button)

        playlist_button = Gtk.Button(label="Add to playlist…")
        playlist_button.connect("clicked", self.on_context_add_playlist_clicked, station)
        menu_box.append(playlist_button)

        view_state = getattr(self, "_view_state", None)
        if view_state is not None and view_state.current_view == "playlist":
            playlist_name = view_state.active_playlist_name
            if playlist_name is not None:
                remove_button = Gtk.Button(label="Remove from playlist")
                remove_button.connect(
                    "clicked",
                    self.on_context_remove_playlist_clicked,
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
            elif MainWindow._is_station_recording(self, station):
                stop_recording_button = Gtk.Button(label="Stop recording")
                stop_recording_button.connect(
                    "clicked",
                    self.on_context_stop_recording_clicked,
                    station,
                )
                menu_box.append(stop_recording_button)

        ripping_action = None
        ripping_service = getattr(self, "ripping_service", None)
        if ripping_service is not None and not getattr(self, "_ripping_shutting_down", False):
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

        if MainWindow._station_homepage_url(self, station) is not None:
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

    def on_play_clicked(self, _button: Gtk.Button) -> None:
        if self._has_active_playback():
            self.on_stop_clicked(_button)
            return
        self.play_selected_station()

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

    def on_record_clicked(self, _button: Gtk.Button) -> None:
        if self.recording_manager.active_session is not None:
            self.stop_recording()
            return
        self.start_selected_recording()

    def _recording_actions(self) -> RecordingController:
        """Bind narrow projection callbacks to the existing recording manager."""
        return RecordingController(
            manager=self.recording_manager,
            show_status=self.status_label.set_text,
            refresh_controls=self._update_record_button,
        )

    def start_station_recording(
        self,
        station: dict[str, Any],
    ) -> None:
        """Start recording one explicit station without changing selection."""
        if getattr(self, "_ripping_shutting_down", False):
            return
        MainWindow._recording_actions(self).start(
            station,
            available=self.recording_available,
            station_url=self._station_url,
            station_name=self._station_display_name,
            output_path=recording_output_path,
        )

    def start_selected_recording(self) -> None:
        if not self.recording_available:
            self.status_label.set_text("Recording unavailable: ffmpeg was not found in PATH.")
            self._update_record_button()
            return

        if not self.selected_station:
            self.status_label.set_text("Select a station first.")
            self._update_record_button()
            return

        start_station_recording = getattr(
            self,
            "start_station_recording",
            None,
        )
        if callable(start_station_recording):
            start_station_recording(self.selected_station)
            return

        MainWindow.start_station_recording(
            self,
            self.selected_station,
        )

    def on_context_record_clicked(
        self,
        _button: Gtk.Button,
        station: dict[str, Any],
    ) -> None:
        """Record the station targeted by a context-menu action."""
        self.start_station_recording(station)

    def on_context_stop_recording_clicked(
        self,
        _button: Gtk.Button,
        _station: dict[str, Any],
    ) -> None:
        """Stop the active recording from a station context-menu action."""
        self.stop_recording()

    def stop_recording(self) -> None:
        MainWindow._recording_actions(self).stop()

    def _update_record_button(self) -> None:
        if not hasattr(self, "record_button"):
            return

        active = self.recording_manager.active_session is not None
        self.record_button.set_label("■ Stop recording" if active else "● Record")
        self.record_button.set_tooltip_text(
            "Stop recording" if active else "Record selected station"
        )
        self.record_button.set_sensitive(self.recording_available or active)

    def play_station(self, station: dict[str, Any]) -> None:
        """Play one explicit station without changing the selected station."""
        if getattr(self, "_ripping_shutting_down", False):
            return

        result = coordinate_playback_start(
            station,
            player=self.player,
            player_backend_name=self.player_backend_name,
            player_capabilities=self.player_capabilities,
            profile_name=self.profile_name,
            restored_muted=self.restored_muted,
            station_supported=station_is_supported,
            unsupported_message=unsupported_station_message,
            station_url=self._station_url,
            announce_buffering=lambda: self.status_label.set_text("Buffering…"),
            apply_preferences_before_start=self._apply_player_preferences_before_start,
            apply_volume_after_start=self._set_player_volume_from_scale,
            apply_mute_after_start=self._set_player_mute,
            usage_tracker=self.usage_tracker,
            add_history_entry=add_history,
        )
        self.status_label.set_text(result.status)
        if not result.success or result.station is None:
            return

        self.current_station = result.station
        self.update_now_playing()
        self.update_data_usage()
        self.update_player_state()
        self._ensure_usage_timer()
        self._ensure_player_state_timer()
        self._update_play_stop_button()
        self._render_results()

    def play_selected_station(self) -> None:
        if not self.selected_station:
            self.status_label.set_text("Select a station first.")
            return

        MainWindow.play_station(self, self.selected_station)

    def on_context_play_clicked(
        self,
        _button: Gtk.Button,
        station: dict[str, Any],
    ) -> None:
        """Play the station targeted by a context-menu action."""
        self.play_station(station)

    def _metadata_worker(self, stream_url: str, generation: int) -> None:
        try:
            metadata = fetch_stream_metadata(stream_url)
        except Exception:  # noqa: BLE001 - metadata failure must not escape the worker.
            metadata = None
        finally:
            GLib.idle_add(self._metadata_fetch_finished, generation)

        if metadata:
            GLib.idle_add(
                self._update_metadata_labels,
                generation,
                metadata,
            )

    def _update_metadata_labels(
        self,
        generation: int,
        metadata: dict[str, Any],
    ) -> bool:
        projection = self._metadata_lifecycle.accept(generation, metadata)
        if projection is None:
            return False

        self.artist_detail_label.set_text(projection.artist)
        self.track_detail_label.set_text(projection.track)
        return False

    def _metadata_fetch_finished(self, generation: int) -> bool:
        self._metadata_lifecycle.finish_fetch(generation)
        return False

    def _clear_metadata_labels(self) -> None:
        if hasattr(self, "artist_detail_label"):
            self.artist_detail_label.set_text("—")
        if hasattr(self, "track_detail_label"):
            self.track_detail_label.set_text("—")

    def _start_metadata_polling(self) -> None:
        self._metadata_lifecycle.start()

        if self._metadata_timer_id is None:
            self._metadata_timer_id = GLib.timeout_add_seconds(15, self._tick_metadata)

        self._tick_metadata()

    def _stop_metadata_polling(self) -> None:
        self._metadata_lifecycle.stop()
        if self._metadata_timer_id is not None:
            GLib.source_remove(self._metadata_timer_id)
            self._metadata_timer_id = None
        self._clear_metadata_labels()

    def _tick_metadata(self) -> bool:
        if not self.current_station or not self._has_active_playback():
            self._stop_metadata_polling()
            return False

        stream_url = self._station_url(self.current_station)
        if not stream_url:
            return True

        generation = self._metadata_lifecycle.begin_fetch()
        if generation is None:
            return True

        threading.Thread(
            target=self._metadata_worker,
            args=(stream_url, generation),
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
        self.country_detail_label.set_text(station_country(station))
        self.codec_detail_label.set_text(station_codec(station))
        self.bitrate_detail_label.set_text(f"{station_bitrate(station)} kbps")
        self.tags_detail_label.set_text(station_tags_text(station))

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
        if not self.player.supports_volume():
            return
        self.player.set_volume(self._current_volume_value())

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
        except Exception as exc:  # noqa: BLE001 - user-facing status in GTK GUI.
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
        except Exception as exc:  # noqa: BLE001 - user-facing status in GTK GUI.
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

        for favorite in load_favorites(profile_name=self.profile_name):
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

        selected_station = self.selected_station
        has_selection = selected_station is not None
        is_favorite = bool(
            selected_station is not None and self._is_favorite_station(selected_station)
        )

        self.add_favorite_button.set_sensitive(has_selection and not is_favorite)
        self.remove_favorite_button.set_sensitive(has_selection and is_favorite)

        if hasattr(self, "favorite_name_entry"):
            self.favorite_name_entry.set_sensitive(is_favorite)
            self.edit_favorite_tags_entry.set_sensitive(is_favorite)
            self.save_favorite_button.set_sensitive(is_favorite)

        self._populate_favorite_edit_fields()

    def add_station_to_favorites(
        self,
        station: dict[str, Any],
    ) -> bool:
        """Add one explicit station to favorites without changing selection."""
        key = station_key(station)
        if not key:
            self.status_label.set_text("Selected station has no favorite URL.")
            self._update_favorite_buttons()
            return False

        if add_favorite(station, profile_name=self.profile_name):
            self._refresh_favorite_cache()
            self._render_results()
            self.status_label.set_text("Added to favorites.")
            return True

        self.status_label.set_text("Station is already in favorites or has no URL.")
        self._update_favorite_buttons()
        return False

    def remove_station_from_favorites(
        self,
        station: dict[str, Any],
    ) -> bool:
        """Remove one explicit station from favorites without changing selection."""
        key = station_key(station)
        if not key:
            self.status_label.set_text("Selected station has no favorite URL.")
            self._update_favorite_buttons()
            return False

        selected_key = (
            station_key(self.selected_station) if self.selected_station is not None else None
        )

        if remove_favorite(key, profile_name=self.profile_name):
            self._refresh_favorite_cache()
            self.status_label.set_text("Removed from favorites.")

            if self._view_state.current_view == "favorites":
                self.stations = load_favorites(profile_name=self.profile_name)

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

        self.status_label.set_text("Selected station is not in favorites.")
        self._update_favorite_buttons()
        return False

    def on_context_add_favorite_clicked(
        self,
        _button: Gtk.Button,
        station: dict[str, Any],
    ) -> None:
        """Add the station targeted by a context-menu action."""
        self.add_station_to_favorites(station)

    def on_context_remove_favorite_clicked(
        self,
        _button: Gtk.Button,
        station: dict[str, Any],
    ) -> None:
        """Remove the station targeted by a context-menu action."""
        self.remove_station_from_favorites(station)

    def on_add_favorite_clicked(self, _button: Gtk.Button) -> None:
        if not self.selected_station:
            self.status_label.set_text("Select a station first.")
            self._update_favorite_buttons()
            return

        self.add_station_to_favorites(self.selected_station)

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

        if not update_favorite(
            key,
            custom_name=favorite_name,
            favorite_tags=favorite_tags,
            profile_name=self.profile_name,
        ):
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

        self.remove_station_from_favorites(self.selected_station)

    def _show_all_favorites(self) -> int:
        """Show all saved favorites and reset playlist filtering state."""
        self._search_lifecycle.invalidate()
        self._view_state.show_favorites()
        self._refresh_favorite_cache()
        self.stations = load_favorites(profile_name=self.profile_name)
        self.selected_station = None
        self._render_results()
        self._update_playlist_status()
        return len(self.stations)

    def _set_favorites_status(self, count: int) -> None:
        self._set_view_status(
            "Favorites",
            count,
            empty_message="No favorite stations yet.",
        )

    def on_show_favorites_clicked(self, _button: Gtk.Button) -> None:
        self._set_favorites_status(self._show_all_favorites())

    def _show_history(self) -> int:
        """Show recently played stations in the main results list."""
        self._search_lifecycle.invalidate()
        self._view_state.show_history()
        self._refresh_favorite_cache()
        self.stations = load_history(profile_name=self.profile_name)
        self.selected_station = None
        self._render_results()
        self._update_playlist_status()
        return len(self.stations)

    def on_show_history_clicked(self, _button: Gtk.Button) -> None:
        count = self._show_history()
        self._set_view_status(
            "History",
            count,
            empty_message="No recently played stations yet.",
        )

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
        self._search_lifecycle.invalidate()
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
                self.status_label.set_text("Type a tag first. Available: " + ", ".join(tags))
            else:
                self.status_label.set_text("No tags found in favorites yet.")
            return

        stations = filter_supported_stations(
            self._favorites_matching_favorite_tag(tag),
            self.player_capabilities,
        )
        if not stations:
            self.status_label.set_text(f"No compatible favorite stations found for tag: {tag}")
            return

        self._search_lifecycle.invalidate()
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

    def tray_now_playing_text(self) -> str:
        """Return a tray-friendly description of the current station."""
        if self.current_station is None:
            return "Nothing playing"
        return self._station_display_name(self.current_station)

    def tray_can_stop(self) -> bool:
        """Return whether the tray Stop action should be enabled."""
        return self._has_active_playback()

    def tray_stop(self) -> None:
        """Stop playback through the same path as the main GTK UI."""
        if not self._has_active_playback():
            return
        self.on_stop_clicked(self.play_button)

    def on_stop_clicked(self, _button: Gtk.Button) -> None:
        self._stop_usage_timer()
        self._stop_player_state_timer()
        result = coordinate_playback_stop(
            player=self.player,
            usage_tracker=self.usage_tracker,
        )
        self._stop_metadata_polling()
        self.update_data_usage()
        self.current_station = None
        self.update_now_playing()
        self.update_player_state()
        self._update_play_stop_button()
        self.status_label.set_text(result.status)
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
        except Exception as exc:  # noqa: BLE001 - user-facing status in GTK GUI.
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

    def _show_quit_confirmation(
        self,
        *,
        on_confirm: Callable[[], None],
        on_cancel: Callable[[], None],
    ) -> None:
        """Ask before interrupting unfinished recording work."""
        dialog = Gtk.Dialog(
            title="Recording in progress",
            transient_for=self,
            modal=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Stop recording & Quit", Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)

        content = dialog.get_content_area()
        content.set_spacing(12)
        for margin in (
            "margin_top",
            "margin_bottom",
            "margin_start",
            "margin_end",
        ):
            setattr(content.props, margin, 16)

        message = Gtk.Label(
            label=(
                "A recording is still active or finishing. "
                "Quitting FluxTuner will request that it stop. "
                "Do you want to continue?"
            )
        )
        message.set_wrap(True)
        content.append(message)

        response_handled = False

        def respond(current: Gtk.Dialog, response: int) -> None:
            nonlocal response_handled
            if response_handled:
                return
            response_handled = True

            current.destroy()
            if response == Gtk.ResponseType.ACCEPT:
                on_confirm()
            else:
                on_cancel()

        dialog.connect("response", respond)
        dialog.present()

    def request_quit(self, *, on_complete: Callable[[], None]) -> None:
        """Confirm pending recording work before beginning shutdown."""
        if self._quit_confirmation_pending or self._ripping_shutting_down:
            return

        if not shutdown_has_pending_recordings(
            recording_manager=self.recording_manager,
            ripping_service=self.ripping_service,
        ):
            self.close_to_tray = False
            if MainWindow.shutdown(self, on_complete=on_complete):
                self._shutdown_close_authorized = True
                on_complete()
            return

        self._quit_confirmation_pending = True
        settled = False

        def cancel() -> None:
            nonlocal settled
            if settled:
                return
            settled = True
            self._quit_confirmation_pending = False

        def confirm() -> None:
            nonlocal settled
            if settled:
                return
            settled = True
            self._quit_confirmation_pending = False
            self.close_to_tray = False
            if MainWindow.shutdown(self, on_complete=on_complete):
                self._shutdown_close_authorized = True
                on_complete()

        self._show_quit_confirmation(
            on_confirm=confirm,
            on_cancel=cancel,
        )

    def shutdown(self, *, on_complete: Callable[[], None] | None = None) -> bool:
        """Request orderly stops; never block or force a timed-out exit."""
        if not self._ripping_shutting_down:
            self._ripping_shutting_down = True
            self._shutdown_deadline = monotonic() + 12.0
            self._ripping_shutdown.request()
            if self._ripping_shutdown.error is not None:
                self.status_label.set_text(
                    f"Could not stop ripping: {self._ripping_shutdown.error}"
                )
            self._ripping_controller.stop_monitoring()
            self._stop_usage_timer()
            self._stop_player_state_timer()
            self._stop_metadata_polling()
            self.usage_tracker.stop()
            if self.recording_manager.active_session is not None:
                self._recording_shutdown.request()
            with suppress(Exception):
                self.player.stop()

        if on_complete is not None and self._shutdown_on_complete is None:
            self._shutdown_on_complete = on_complete

        ripping_done = self._ripping_shutdown.poll()
        ffmpeg_done = not self._recording_shutdown.requested or self._recording_shutdown.poll()
        successful = (
            ripping_done
            and ffmpeg_done
            and self._ripping_shutdown.error is None
            and self._recording_shutdown.error is None
        )
        if successful:
            if self._shutdown_timer_id is not None:
                GLib.source_remove(self._shutdown_timer_id)
                self._shutdown_timer_id = None
            self._shutdown_on_complete = None
            self._shutdown_deadline = None
            return True

        if self._shutdown_on_complete is not None and self._shutdown_timer_id is None:
            self._shutdown_timer_id = GLib.timeout_add(200, self._poll_shutdown)
        return False

    def _show_shutdown_warning(
        self,
        *,
        on_wait: Callable[[], None],
        on_force: Callable[[], None],
        has_error: bool,
    ) -> None:
        """Only an explicit user response may abandon unfinished recordings."""
        dialog = Gtk.Dialog(
            title="Recording has not finished",
            transient_for=self,
            modal=True,
        )
        dialog.add_button("Keep waiting", Gtk.ResponseType.CANCEL)
        dialog.add_button("Quit anyway", Gtk.ResponseType.ACCEPT)
        dialog.set_default_response(Gtk.ResponseType.CANCEL)
        content = dialog.get_content_area()
        content.set_spacing(12)
        content.props.margin_top = 16
        content.props.margin_bottom = 16
        content.props.margin_start = 16
        content.props.margin_end = 16
        if has_error:
            detail = "A recording could not be finalized successfully. "
        else:
            detail = "A recording is still being finalized. "
        label = Gtk.Label(
            label=(
                detail + "Quitting anyway may leave the current file incomplete. "
                "Already finalized tracks are not intentionally removed."
            )
        )
        label.set_wrap(True)
        content.append(label)
        answered = False

        def respond(current: Gtk.Dialog, response: int) -> None:
            nonlocal answered
            if answered:
                return
            answered = True
            current.destroy()
            if response == Gtk.ResponseType.ACCEPT:
                on_force()
            else:
                on_wait()

        dialog.connect("response", respond)
        dialog.present()

    def _poll_shutdown(self) -> bool:
        """Inspect both workers and a monotonic deadline on GTK's main loop."""
        callback = self._shutdown_on_complete
        if callback is None:
            self._shutdown_timer_id = None
            return False

        ripping_done = self._ripping_shutdown.poll()
        ffmpeg_done = not self._recording_shutdown.requested or self._recording_shutdown.poll()
        has_error = (
            self._ripping_shutdown.error is not None or self._recording_shutdown.error is not None
        )
        if ripping_done and ffmpeg_done and not has_error and not self._shutdown_warning_open:
            self._shutdown_on_complete = None
            self._shutdown_timer_id = None
            self._shutdown_deadline = None
            self._shutdown_close_authorized = True
            callback()
            return False

        deadline = self._shutdown_deadline
        if not self._shutdown_warning_open and (deadline is not None and monotonic() >= deadline):
            self._shutdown_warning_open = True

            def keep_waiting() -> None:
                self._shutdown_warning_open = False
                self._shutdown_deadline = monotonic() + 12.0

            def quit_anyway() -> None:
                self._shutdown_warning_open = False
                self._shutdown_on_complete = None
                self._shutdown_timer_id = None
                self._shutdown_deadline = None
                self._shutdown_close_authorized = True
                callback()

            self._show_shutdown_warning(
                on_wait=keep_waiting,
                on_force=quit_anyway,
                has_error=has_error,
            )
        return True

    def on_close_request(self, _window: Gtk.Window) -> bool:
        """Hide to tray or defer destruction until ripping workers finish."""
        if getattr(self, "_shutdown_close_authorized", False):
            return False
        if getattr(self, "close_to_tray", False):
            self.set_visible(False)
            return True

        pending_completion = self._shutdown_on_complete
        if pending_completion is not None:
            if MainWindow.shutdown(self, on_complete=pending_completion):
                pending_completion()
            return True

        self.request_quit(on_complete=self.close)
        return True

    def update_data_usage(self) -> None:
        if hasattr(self, "data_usage_label"):
            self.data_usage_label.set_text(
                format_usage_line(self.usage_tracker.snapshot()).replace("Data: ", "")
            )
