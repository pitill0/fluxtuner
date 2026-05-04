"""Experimental GTK GUI entrypoint for FluxTuner."""

from __future__ import annotations


def run_gui(player_name: str = "mpv") -> None:
    try:
        import gi
        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk
    except Exception as exc:  # pragma: no cover - depends on system GTK
        raise RuntimeError(
            "GTK GUI dependencies are not available. "
            "Install GTK4 and PyGObject first. On macOS: brew install pygobject3 gtk4"
        ) from exc

    from fluxtuner.gui.window import MainWindow

    app = Gtk.Application(application_id="io.github.pitill0.fluxtuner")

    def on_activate(app_: Gtk.Application) -> None:
        window = MainWindow(app_, player_name=player_name)
        window.present()

    app.connect("activate", on_activate)
    app.run()
