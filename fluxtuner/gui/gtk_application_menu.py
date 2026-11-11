"""GTK application menu structure.

The model owns menu presentation only. Window and application actions
remain responsible for their existing behavior.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any


def build_application_menu_model(gio: Any) -> Any:
    """Build a native GTK-compatible application menu hierarchy."""
    stations = gio.Menu()
    stations.append("Add station…", "win.station-add")
    stations.append("Import stations…", "win.station-import")
    stations.append("Import stations from URL…", "win.station-import-url")

    application = gio.Menu()
    application.append("Preferences…", "win.preferences")
    application.append("About FluxTuner", "win.about")

    root = gio.Menu()
    root.append_submenu("Stations", stations)
    root.append_section(None, application)
    root.append("Quit", "app.quit")

    return root


def create_application_menu(
    owner: Any,
    *,
    callbacks: Mapping[str, Callable[[Any], None]],
    gtk: Any,
    gio: Any,
) -> tuple[Any, Any]:
    """Create the menu button and register its window-scoped actions.

    All station operations and lifecycle decisions remain in their
    existing controllers. The callbacks receive the menu button as
    their GTK signal argument.
    """
    required = {
        "station-add",
        "station-import",
        "station-import-url",
        "preferences",
        "about",
    }
    if set(callbacks) != required:
        raise ValueError("Invalid GTK application menu action mapping")

    button = gtk.MenuButton(icon_name="open-menu-symbolic")
    button.set_tooltip_text("Application menu")
    button.set_halign(gtk.Align.END)
    button.set_valign(gtk.Align.CENTER)

    for name, callback in callbacks.items():
        action = gio.SimpleAction.new(name, None)

        def activated(
            _action: Any,
            _parameter: Any,
            handler: Callable[[Any], None] = callback,
        ) -> None:
            handler(button)

        action.connect("activate", activated)
        owner.add_action(action)

    button.set_menu_model(build_application_menu_model(gio))
    popover = button.get_popover()

    if popover is None:
        raise RuntimeError("GTK did not create the application menu popover")

    return button, popover
