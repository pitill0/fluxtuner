"""Independent GTK4 preferences dialog.

The dialog owns its widgets but does not own application configuration.
The caller supplies the current appearance and handles persisted changes.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
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


STORAGE_FIELDS = (
    ("recordings_directory", "Continuous recordings"),
    ("rips_directory", "Ripped tracks"),
)


def _storage_label(directory: Path | None, default: Path) -> str:
    if directory is None:
        return f"Default: {default}"
    return str(directory)


def _storage_apply(
    key: str,
    directory: Path | None,
    *,
    on_change: Callable[[str, Path | None], None],
    path_label: Any,
    error_label: Any,
    default: Path,
) -> None:
    try:
        on_change(key, directory)
    except (OSError, ValueError) as exc:
        error_label.set_text(str(exc))
        return
    path_label.set_text(_storage_label(directory, default))
    error_label.set_text("")


def _open_storage_directory(
    directory: Path,
    *,
    error_label: Any,
    launcher: Callable[[str], None] | None = None,
) -> None:
    """Open an existing storage directory using desktop URI handling."""
    if not directory.is_dir():
        error_label.set_text(f"Storage directory is not available: {directory}")
        return

    try:
        if launcher is None:
            from gi.repository import Gio

            def launch_default(uri: str) -> None:
                Gio.AppInfo.launch_default_for_uri(uri, None)

            launcher = launch_default

        launcher(directory.as_uri())
    except Exception as exc:  # noqa: BLE001 - contain desktop launcher failures.
        error_label.set_text(f"Could not open storage directory: {exc}")
        return

    error_label.set_text("")


def _storage_browse(
    _button: Any,
    *,
    gtk: Any,
    parent: Any,
    key: str,
    current: Path | None,
    default: Path,
    on_change: Callable[[str, Path | None], None],
    path_label: Any,
    error_label: Any,
) -> None:
    chooser = gtk.FileChooserNative.new(
        "Choose storage directory",
        parent,
        gtk.FileChooserAction.SELECT_FOLDER,
        "Select",
        "Cancel",
    )

    initial = current or default
    if initial.is_dir():
        from gi.repository import Gio

        chooser.set_current_folder(Gio.File.new_for_path(str(initial)))

    def on_response(native: Any, response: int) -> None:
        try:
            if response == gtk.ResponseType.ACCEPT:
                selected = native.get_file()
                selected_path = selected.get_path() if selected else None
                if selected_path is None:
                    error_label.set_text("Choose a local directory.")
                else:
                    _storage_apply(
                        key,
                        Path(selected_path),
                        on_change=on_change,
                        path_label=path_label,
                        error_label=error_label,
                        default=default,
                    )
        finally:
            native.destroy()

    chooser.connect("response", on_response)
    chooser.show()


def _append_storage_row(
    *,
    gtk: Any,
    page: Any,
    dialog: Any,
    key: str,
    title: str,
    current: Path | None,
    default: Path,
    on_change: Callable[[str, Path | None], None],
) -> None:
    heading = gtk.Label(label=title)
    heading.set_markup(f"<b>{title}</b>")
    heading.set_xalign(0)
    page.append(heading)

    row = gtk.Box(
        orientation=gtk.Orientation.VERTICAL,
        spacing=8,
    )

    path_label = gtk.Label(label=_storage_label(current, default))
    path_label.set_xalign(0)
    path_label.set_hexpand(True)
    path_label.set_wrap(True)
    path_label.set_selectable(False)
    row.append(path_label)

    buttons = gtk.Box(
        orientation=gtk.Orientation.HORIZONTAL,
        spacing=8,
    )
    buttons.set_hexpand(True)

    error_label = gtk.Label(label="")
    error_label.set_xalign(0)
    error_label.set_wrap(True)

    browse = gtk.Button(label="Browse…")
    browse.connect(
        "clicked",
        lambda button: _storage_browse(
            button,
            gtk=gtk,
            parent=dialog,
            key=key,
            current=on_current_path(),
            default=default,
            on_change=update_storage,
            path_label=path_label,
            error_label=error_label,
        ),
    )

    selected = current

    def on_current_path() -> Path | None:
        return selected

    def update_storage(field: str, directory: Path | None) -> None:
        nonlocal selected
        on_change(field, directory)
        selected = directory

    open_folder = gtk.Button(label="Open folder")
    open_folder.connect(
        "clicked",
        lambda _button: _open_storage_directory(
            on_current_path() or default,
            error_label=error_label,
        ),
    )

    reset = gtk.Button(label="Restore default")
    reset.connect(
        "clicked",
        lambda _button: _storage_apply(
            key,
            None,
            on_change=update_storage,
            path_label=path_label,
            error_label=error_label,
            default=default,
        ),
    )

    buttons.append(browse)
    buttons.append(open_folder)
    buttons.append(reset)
    row.append(buttons)
    page.append(row)
    page.append(error_label)


def create_preferences_dialog(
    parent: Any,
    *,
    appearance: AppearanceMode | str | None,
    on_appearance_changed: Callable[[AppearanceMode], None],
    storage_directories: dict[str, Path | None] | None = None,
    storage_defaults: dict[str, Path] | None = None,
    on_storage_changed: Callable[[str, Path | None], None] | None = None,
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

    action_close = dialog.add_button("Close", gtk.ResponseType.CLOSE)
    action_close.set_margin_end(12)
    action_close.set_margin_top(12)
    action_close.set_margin_bottom(12)
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

        elif section == "Storage" and on_storage_changed is not None:
            for key, title in STORAGE_FIELDS:
                _append_storage_row(
                    gtk=gtk,
                    page=page,
                    dialog=dialog,
                    key=key,
                    title=title,
                    current=(storage_directories or {}).get(key),
                    default=(storage_defaults or {}).get(key, Path.home()),
                    on_change=on_storage_changed,
                )
        else:
            label = gtk.Label(
                label="General preferences will appear here as features are added."
                if section == "General"
                else "Storage destinations are not available."
            )
            label.set_wrap(True)
            label.set_xalign(0)
            label.add_css_class("dim-label")
            page.append(label)

        notebook.append_page(page, gtk.Label(label=section))

    return dialog
