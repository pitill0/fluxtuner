"""Independent GTK4 preferences dialog.

The dialog owns its widgets but does not own application configuration.
The caller supplies the current appearance and handles persisted changes.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fluxtuner.gui.appearance import AppearanceMode, normalize_appearance

APPEARANCE_MODES = (
    AppearanceMode.SYSTEM,
    AppearanceMode.DARK,
    AppearanceMode.LIGHT,
)


def appearance_index(mode: AppearanceMode | str | None) -> int:
    """Resolve a configured appearance to its selector index."""
    return APPEARANCE_MODES.index(normalize_appearance(mode))


def appearance_from_index(index: int) -> AppearanceMode | None:
    """Ignore invalid or unselected GTK dropdown indices."""
    if 0 <= index < len(APPEARANCE_MODES):
        return APPEARANCE_MODES[index]
    return None


def _appearance_selected(
    dropdown: Any,
    _pspec: object,
    on_change: Callable[[AppearanceMode], None],
) -> None:
    mode = appearance_from_index(dropdown.get_selected())
    if mode is not None:
        on_change(mode)


def _close_button_clicked(_button: Any, dialog: Any) -> None:
    """Hide the reusable preferences window."""
    dialog.hide()


def _dialog_response(dialog: Any, _response: int) -> None:
    """Keep the preferences window reusable after Close."""
    dialog.hide()


def _dialog_close_request(dialog: Any) -> bool:
    """Intercept the titlebar close action before GTK destroys the window."""
    dialog.hide()
    return True


def create_preferences_dialog(
    parent: Any,
    *,
    appearance: AppearanceMode | str | None,
    on_appearance_changed: Callable[[AppearanceMode], None],
    gtk: Any | None = None,
) -> Any:
    """Build a GTK4 preferences dialog without modifying persistent state."""
    if gtk is None:
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        gtk = Gtk

    dialog = gtk.Dialog(
        title="Preferences",
        transient_for=parent,
        modal=False,
    )
    dialog.set_destroy_with_parent(True)
    dialog.add_css_class("fluxtuner-preferences")
    dialog.set_default_size(520, 340)

    # Use a predictable text close control instead of the native
    # theme-dependent window-close icon.
    header = gtk.HeaderBar()
    header.set_show_title_buttons(False)
    header.set_title_widget(gtk.Label(label="Preferences"))

    close_button = gtk.Button(label="×")
    close_button.add_css_class("fluxtuner-preferences-close")
    close_button.set_tooltip_text("Close preferences")
    close_button.connect("clicked", _close_button_clicked, dialog)
    header.pack_end(close_button)
    dialog.set_titlebar(header)

    dialog.add_button("Close", gtk.ResponseType.CLOSE)
    dialog.connect("response", _dialog_response)
    dialog.connect("close-request", _dialog_close_request)

    notebook = gtk.Notebook()
    notebook.set_hexpand(True)
    notebook.set_vexpand(True)
    dialog.get_content_area().append(notebook)

    for section in ("General", "Appearance", "Storage"):
        page = gtk.Box(
            orientation=gtk.Orientation.VERTICAL,
            spacing=12,
        )
        page.set_margin_top(18)
        page.set_margin_bottom(18)
        page.set_margin_start(18)
        page.set_margin_end(18)

        if section == "Appearance":
            row = gtk.Box(
                orientation=gtk.Orientation.HORIZONTAL,
                spacing=12,
            )

            label = gtk.Label(label="Appearance")
            label.set_xalign(0)
            label.set_hexpand(True)
            row.append(label)

            dropdown = gtk.DropDown.new_from_strings(["System", "Dark", "Light"])
            dropdown.set_selected(appearance_index(appearance))
            dropdown.connect(
                "notify::selected",
                _appearance_selected,
                on_appearance_changed,
            )
            row.append(dropdown)
            page.append(row)

        else:
            message = (
                "General preferences will appear here as features are added."
                if section == "General"
                else "Storage destinations will be configurable in a future update."
            )
            label = gtk.Label(label=message)
            label.set_wrap(True)
            label.set_xalign(0)
            label.add_css_class("dim-label")
            page.append(label)

        notebook.append_page(page, gtk.Label(label=section))

    return dialog
