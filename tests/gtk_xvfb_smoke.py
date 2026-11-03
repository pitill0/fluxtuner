"""Real GTK4/Xvfb smoke for FluxTuner appearance resources (system Python only).

Run with: xvfb-run -a /usr/bin/python3 tests/gtk_xvfb_smoke.py
This file is intentionally not auto-collected by pytest's regular matrix.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("GSK_RENDERER", "cairo")

import gi  # noqa: E402

gi.require_version("Gdk", "4.0")
gi.require_version("Gtk", "4.0")
from gi.repository import Gdk, GLib, Gtk  # noqa: E402

from fluxtuner.gui.appearance import (  # noqa: E402
    COMMON_STYLESHEET,
    THEMES_DIR,
    AppearanceMode,
    GtkAppearanceManager,
)


def main() -> None:
    assert os.environ.get("DISPLAY"), "An isolated Xvfb DISPLAY is required"
    Gtk.init()
    display = Gdk.Display.get_default()
    assert display is not None, "GTK4 could not initialize a Gdk display"

    assert COMMON_STYLESHEET.is_file(), COMMON_STYLESHEET
    assert (THEMES_DIR / "dark.css").is_file()
    assert (THEMES_DIR / "light.css").is_file()

    appearance = GtkAppearanceManager(display)
    assert appearance.apply(AppearanceMode.DARK) is AppearanceMode.DARK
    assert appearance._common_provider is not None
    dark_provider = appearance._palette_provider
    assert dark_provider is not None, "Dark palette CSS did not load"

    assert appearance.apply(AppearanceMode.LIGHT) is AppearanceMode.LIGHT
    assert appearance._common_provider is not None
    assert appearance._palette_provider is not None
    assert appearance._palette_provider is not dark_provider

    window = Gtk.Window(title="FluxTuner GTK4 smoke")
    window.set_child(Gtk.Label(label="FluxTuner appearance resources"))
    try:
        window.present()
        context = GLib.MainContext.default()
        for _ in range(25):
            if not context.pending():
                break
            context.iteration(False)
        assert window.get_visible(), "FluxTuner GTK4 window did not become visible"
        assert window.get_child() is not None
    finally:
        window.destroy()

    print("PASS: FluxTuner shared CSS, dark/light palette, and GTK4 window under Xvfb")


if __name__ == "__main__":
    main()
