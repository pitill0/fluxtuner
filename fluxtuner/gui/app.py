"""GTK application entrypoint for FluxTuner."""

from __future__ import annotations

import os

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
    from fluxtuner.gui.window import MainWindow

    app = Gtk.Application(
        application_id="io.github.pitill0.Fluxtuner",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    def on_activate(app_: Gtk.Application) -> None:
        display = Gdk.Display.get_default()
        if display is not None:
            appearance = GtkAppearanceManager(display)
            appearance.apply(get_config_value("gtk_appearance", "system"))
            app_._fluxtuner_appearance = appearance

        window = MainWindow(app_, player_name=player_name)
        window.present()

    app.connect("activate", on_activate)
    app.run()
