"""Experimental GTK desktop window for FluxTuner."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
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
from fluxtuner.core import db  # noqa: E402
from fluxtuner.core.compatibility import (  # noqa: E402
    station_is_supported,
    unsupported_station_message,
)
from fluxtuner.core.data_usage import DataUsageTracker, format_usage_line  # noqa: E402
from fluxtuner.core.discovery_execution import search_desktop_stations  # noqa: E402
from fluxtuner.core.favorites import (  # noqa: E402
    favorite_display_name,
)
from fluxtuner.core.history import add_history  # noqa: E402
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
    station_url,
)
from fluxtuner.core.stream_metadata import fetch_stream_metadata  # noqa: E402
from fluxtuner.gui.appearance import (  # noqa: E402
    AppearanceMode,
    GtkAppearanceManager,
    normalize_appearance,
)
from fluxtuner.gui.gtk_library import LibraryController, library_tags_text  # noqa: E402
from fluxtuner.gui.gtk_library_panel import LibraryPanel, LibraryViewPorts  # noqa: E402
from fluxtuner.gui.gtk_metadata import MetadataLifecycle  # noqa: E402
from fluxtuner.gui.gtk_playback import (  # noqa: E402
    coordinate_playback_start,
    coordinate_playback_stop,
)
from fluxtuner.gui.gtk_recording import RecordingController  # noqa: E402
from fluxtuner.gui.gtk_ripping import ripping_menu_action  # noqa: E402
from fluxtuner.gui.gtk_ripping_controller import RippingController  # noqa: E402
from fluxtuner.gui.gtk_search import SearchLifecycle  # noqa: E402
from fluxtuner.gui.gtk_shutdown import ShutdownController  # noqa: E402
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
        self._shutdown_controller = ShutdownController(
            recording_manager=self.recording_manager,
            ripping_service=self.ripping_service,
            stop_activity=self._stop_background_activity,
            stop_playback=self.player.stop,
            prepare_quit=self._prepare_quit,
            show_status=lambda message: self.status_label.set_text(message),
            show_confirmation=self._show_quit_confirmation,
            show_warning=self._show_shutdown_warning,
            schedule=GLib.timeout_add,
            remove_source=GLib.source_remove,
        )
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
        self._library_controller = LibraryController(profile_name=lambda: self.profile_name)
        self._library_controller.refresh_favorite_cache()
        self._library = LibraryPanel(
            parent=self,
            controller=self._library_controller,
            ports=LibraryViewPorts(
                get_stations=lambda: self.stations,
                set_stations=lambda stations: setattr(self, "stations", stations),
                get_selected=lambda: self.selected_station,
                set_selected=lambda station: setattr(self, "selected_station", station),
                get_current=lambda: self.current_station,
                get_capabilities=lambda: self.player_capabilities,
            ),
            view_state=self._view_state,
            invalidate_search=self._search_lifecycle.invalidate,
            render_results=self._render_results,
            play_selected=self.play_selected_station,
            update_now_playing=self.update_now_playing,
            set_status=lambda message: self.status_label.set_text(message),
            set_view_status=self._set_view_status,
            make_value_label=self._make_value_label,
            append_section_title=self._append_section_title,
            close_menu=lambda: self.application_menu_popover.popdown(),
        )
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
        self._library._refresh_saved_playlists()
        self._ripping_controller = RippingController(
            service=self.ripping_service,
            check_availability=ripping_backend.availability,
            profile_context=self._ripping_profile_context,
            data_directory=DATA_DIR,
            show_status=self.status_label.set_text,
            is_shutting_down=lambda: self._shutdown_controller.shutting_down,
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

        self._library._build_library_controls(side_panel)
        self._library._build_saved_playlist_controls(side_panel)

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

        self._library._build_favorite_controls(side_panel)
        self._library._build_playlist_controls(side_panel)

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
        add_station_button.connect("clicked", self._library.on_add_custom_station_clicked)
        content.append(add_station_button)

        import_button = Gtk.Button(label="Import stations…")
        import_button.connect("clicked", self._library.on_import_stations_clicked)
        content.append(import_button)

        remote_import_button = Gtk.Button(label="Import stations from URL…")
        remote_import_button.connect("clicked", self._library.on_import_stations_url_clicked)
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

    def _build_status_bar(self, root: Gtk.Box) -> None:
        self.status_label = Gtk.Label(label="Ready")
        self.status_label.set_hexpand(True)
        self.status_label.props.ellipsize = Pango.EllipsizeMode.END
        self.status_label.set_xalign(0)
        self.status_label.set_wrap(True)
        root.append(self.status_label)

    def _is_favorite_station(self, station: dict[str, Any]) -> bool:
        return self._library_controller.is_favorite_station(station)

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
        shutdown = getattr(self, "_shutdown_controller", None)
        if shutdown is not None and shutdown.shutting_down:
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
        shutdown = getattr(self, "_shutdown_controller", None)
        if shutdown is not None and shutdown.shutting_down:
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
        self.tags_detail_label.set_text(library_tags_text(station))

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

    def _update_favorite_buttons(self) -> None:
        self._library._update_favorite_buttons()

    def _update_playlist_status(self) -> None:
        self._library._update_playlist_status()

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
        """Delegate explicit application quit to the shared shutdown owner."""
        self._shutdown_controller.request_quit(on_complete=on_complete)

    def _prepare_quit(self) -> None:
        """Make an accepted quit exit instead of hiding to the tray."""
        self.close_to_tray = False

    def _stop_background_activity(self) -> None:
        """Cancel window-owned activity after shutdown has blocked new work."""
        self._ripping_controller.stop_monitoring()
        self._stop_usage_timer()
        self._stop_player_state_timer()
        self._stop_metadata_polling()
        self.usage_tracker.stop()

    def shutdown(self, *, on_complete: Callable[[], None] | None = None) -> bool:
        """Request nonblocking finalization through the shutdown controller."""
        return self._shutdown_controller.shutdown(on_complete=on_complete)

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

    def on_close_request(self, _window: Gtk.Window) -> bool:
        """Hide to tray or defer destruction until ripping workers finish."""
        if self._shutdown_controller.close_authorized:
            return False
        if getattr(self, "close_to_tray", False):
            self.set_visible(False)
            return True

        pending_completion = self._shutdown_controller.pending_completion
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
