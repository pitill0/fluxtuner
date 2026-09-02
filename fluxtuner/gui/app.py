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

    from fluxtuner.config import get_config_value
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

    if sys.platform.startswith("linux"):
        candidate = LinuxStatusNotifierItem(
            application_id=application_id,
            on_show=show_window,
            on_stop=stop_playback,
            on_quit=quit_application,
            get_now_playing=now_playing,
            can_stop=can_stop_playback,
        )
        if candidate.start():
            tray = candidate
            app.hold()
            app_held_for_tray = True

    def on_activate(app_: Gtk.Application) -> None:
        nonlocal window
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
            )
            window.close_to_tray = tray is not None

        window.present()

    app.connect("activate", on_activate)
    try:
        app.run()
    finally:
        if tray is not None:
            tray.stop()
