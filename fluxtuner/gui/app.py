"""GTK application entrypoint for FluxTuner."""

from __future__ import annotations

import os

from pathlib import Path

os.environ.setdefault("GSK_RENDERER", "cairo")

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")

from gi.repository import Gdk, Gtk

from fluxtuner.gui.window import MainWindow

def load_stylesheet() -> None:
    css_path = Path(__file__).with_name("style.css")
    if not css_path.exists():
        return

    provider = Gtk.CssProvider()
    provider.load_from_path(str(css_path))

    display = Gdk.Display.get_default()
    if display is None:
        return

    Gtk.StyleContext.add_provider_for_display(
        display,
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
def run_gui(player_name: str = "mpv") -> None:
    try:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gio, Gtk, Gdk
    except Exception as exc:  # pragma: no cover - depends on system GTK
        raise RuntimeError(
            "GTK GUI dependencies are not available. "
            "Install GTK4 and PyGObject first. On macOS: brew install pygobject3 gtk4"
        ) from exc

    from fluxtuner.gui.window import MainWindow

    app = Gtk.Application(
        application_id="io.github.pitill0.Fluxtuner",
        flags=Gio.ApplicationFlags.NON_UNIQUE,
    )

    def on_activate(app_: Gtk.Application) -> None:
        load_stylesheet()
        window = MainWindow(app_, player_name=player_name)
        window.present()

    app.connect("activate", on_activate)
    app.run()
