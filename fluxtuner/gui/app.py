"""GTK application entrypoint for FluxTuner."""

from __future__ import annotations

import os
import sys

os.environ.setdefault("GSK_RENDERER", "cairo")


def run_gui(player_name: str = "mpv") -> None:
    try:
        import gi

        gi.require_version("Gdk", "4.0")
        gi.require_version("Gtk", "4.0")

        from gi.repository import Gdk, Gio, Gtk
    except Exception as exc:  # pragma: no cover - depends on system GTK
        raise RuntimeError(
            "GTK GUI dependencies are not available. "
            "Install GTK4 and PyGObject first. On macOS: brew install pygobject3 gtk4"
        ) from exc

    from fluxtuner.config import get_config_value, set_config_value
    from fluxtuner.gui.appearance import GtkAppearanceManager
    from fluxtuner.gui.tray.linux_sni import LinuxStatusNotifierItem
    from fluxtuner.gui.window import MainWindow

    application_id = "io.github.pitill0.Fluxtuner"
    app = Gtk.Application(
        application_id=application_id,
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    window: MainWindow | None = None
    tray: LinuxStatusNotifierItem | None = None
    app_held_for_tray = False
    tray_supported = sys.platform.startswith("linux")

    def show_window() -> None:
        if window is not None:
            window.present()
            return
        app.activate()

    def stop_playback() -> None:
        if window is not None:
            window.tray_stop()

    def now_playing() -> str:
        if window is None:
            return "Nothing playing"
        return window.tray_now_playing_text()

    def can_stop_playback() -> bool:
        return bool(window is not None and window.tray_can_stop())

    def quit_application() -> None:
        nonlocal app_held_for_tray
        if window is not None:
            window.close_to_tray = False
            window.shutdown()
        if app_held_for_tray:
            app.release()
            app_held_for_tray = False
        app.quit()

    def set_close_to_tray(enabled: bool) -> None:
        nonlocal app_held_for_tray

        actual = bool(enabled and tray is not None)
        if window is not None:
            window.close_to_tray = actual

        if actual and not app_held_for_tray:
            app.hold()
            app_held_for_tray = True
        elif not actual and app_held_for_tray:
            app.release()
            app_held_for_tray = False

    def set_tray_enabled(enabled: bool) -> bool:
        nonlocal tray

        if not tray_supported:
            return False

        if enabled:
            if tray is not None:
                return True

            candidate = LinuxStatusNotifierItem(
                application_id=application_id,
                on_show=show_window,
                on_stop=stop_playback,
                on_quit=quit_application,
                get_now_playing=now_playing,
                can_stop=can_stop_playback,
            )
            if not candidate.start():
                return False
            tray = candidate
            return True

        set_close_to_tray(False)
        if tray is not None:
            tray.stop()
            tray = None
        return False

    if (
        tray_supported
        and bool(get_config_value("tray_enabled", False))
        and not set_tray_enabled(True)
    ):
        set_config_value("tray_enabled", False)
        set_config_value("close_to_tray", False)

    def on_activate(app_: Gtk.Application) -> None:
        nonlocal window, app_held_for_tray
        appearance_manager: GtkAppearanceManager | None = None

        display = Gdk.Display.get_default()
        if display is not None:
            appearance_manager = GtkAppearanceManager(display)
            appearance_manager.apply(get_config_value("gtk_appearance", "system"))

        if window is None:
            window = MainWindow(
                app_,
                player_name=player_name,
                appearance_manager=appearance_manager,
                tray_supported=tray_supported,
                on_tray_enabled_changed=set_tray_enabled,
                on_close_to_tray_changed=set_close_to_tray,
            )
            set_close_to_tray(bool(tray is not None and get_config_value("close_to_tray", False)))

        window.present()

    app.connect("activate", on_activate)
    try:
        app.run()
    finally:
        if tray is not None:
            tray.stop()
