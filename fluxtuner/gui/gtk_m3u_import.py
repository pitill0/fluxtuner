# SPDX-License-Identifier: MIT

"""GTK station import workflow with a testable persistence session."""

from __future__ import annotations

import threading
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from fluxtuner.core import db
from fluxtuner.core.m3u_import import (
    MAX_PLAYLIST_NAME_LENGTH,
    M3UImportResult,
    M3UPreview,
    import_m3u,
    load_station_collection,
)
from fluxtuner.network.network_policy import SystemStreamTargetResolver
from fluxtuner.network.remote_station_collection import preview_remote_station_collection


@dataclass
class M3UImportSession:
    profile_id: int
    preview: M3UPreview
    playlist_names: tuple[str, ...]
    existing_urls: frozenset[str]
    source_name: str
    profile_is_current: Callable[[], bool]
    _closed: bool = False

    def cancel(self) -> None:
        self._closed = True

    def commit(self, name: str, *, existing: bool) -> M3UImportResult:
        if self._closed:
            raise ValueError("This import session is closed.")
        if not self.profile_is_current():
            raise ValueError("The profile changed. Reopen the import dialog.")
        clean_name = name.strip()
        if existing and clean_name not in self.playlist_names:
            raise ValueError("Choose one of the offered playlists.")

        with closing(db.connect()) as conn, conn:
            # Serialize destination validation and writes so a deleted playlist
            # cannot be recreated between the existence check and the import.
            conn.execute("BEGIN IMMEDIATE")
            destination = conn.execute(
                "SELECT id FROM playlists WHERE profile_id = ? AND lower(name) = lower(?)",
                (self.profile_id, clean_name),
            ).fetchone()
            if existing and destination is None:
                raise ValueError("The selected playlist no longer exists.")
            if not existing and destination is not None:
                raise ValueError("This playlist already exists. Select it from the list.")
            result = import_m3u(
                conn,
                profile_id=self.profile_id,
                playlist_name=name,
                entries=self.preview.entries,
            )
            conn.commit()
        self._closed = True
        return result


def prepare_m3u_import(
    path: Path,
    *,
    profile_id: int,
    profile_is_current: Callable[[], bool],
) -> M3UImportSession:
    if not profile_is_current():
        raise ValueError("The profile changed. Reopen the import dialog.")
    preview = load_station_collection(path)
    return prepare_m3u_preview(
        preview,
        source_name=Path(path).name,
        profile_id=profile_id,
        profile_is_current=profile_is_current,
    )


def prepare_remote_m3u_import(
    url: str,
    *,
    profile_id: int,
    profile_is_current: Callable[[], bool],
) -> M3UImportSession:
    """Download once, then retain a parsed snapshot for confirmation."""
    if not profile_is_current():
        raise ValueError("The profile changed. Reopen the import dialog.")
    _data, preview = preview_remote_station_collection(url, SystemStreamTargetResolver())
    source = urlsplit(url)
    source_name = Path(source.path).name or source.hostname or "stations"
    return prepare_m3u_preview(
        preview,
        source_name=source_name,
        profile_id=profile_id,
        profile_is_current=profile_is_current,
    )


def prepare_m3u_preview(
    preview: M3UPreview,
    *,
    source_name: str,
    profile_id: int,
    profile_is_current: Callable[[], bool],
) -> M3UImportSession:
    """Create a session from an already loaded local or remote preview."""
    if not profile_is_current():
        raise ValueError("The profile changed. Reopen the import dialog.")
    if not preview.entries:
        raise ValueError("The file contains no valid stations to import.")
    if type(profile_id) is not int or profile_id <= 0:
        raise ValueError("An existing profile is required.")
    with closing(db.connect()) as conn:
        if conn.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone() is None:
            raise ValueError("The selected profile no longer exists.")
        names = tuple(str(item["name"]) for item in db.list_playlists(conn, profile_id=profile_id))
        urls = frozenset(
            str(row[0])
            for row in conn.execute(
                """
                SELECT s.station_key
                FROM favorites AS f
                JOIN stations AS s ON s.id = f.station_id
                WHERE f.profile_id = ?
                """,
                (profile_id,),
            )
        )
    return M3UImportSession(
        profile_id=profile_id,
        preview=preview,
        playlist_names=names,
        existing_urls=urls,
        source_name=source_name,
        profile_is_current=profile_is_current,
    )


def _show_preview(
    parent: Any,
    session: M3UImportSession,
    *,
    on_saved: Callable[[str, M3UImportResult], None],
) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    dialog = Gtk.Dialog(title="Import stations", transient_for=parent, modal=True)
    dialog.set_default_size(680, 560)
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    dialog.add_button("Import", Gtk.ResponseType.ACCEPT)
    dialog.set_default_response(Gtk.ResponseType.ACCEPT)
    parent._m3u_import_dialog = dialog
    content = dialog.get_content_area()
    content.set_spacing(10)
    for side in ("top", "bottom", "start", "end"):
        getattr(content, f"set_margin_{side}")(16)

    def label(text: str) -> Any:
        widget = Gtk.Label(label=text, xalign=0)
        widget.set_wrap(True)
        widget.set_selectable(True)
        return widget

    content.append(label(session.source_name))
    preview = session.preview
    content.append(
        label(
            f"{len(preview.entries)} valid stations · "
            f"{preview.duplicates} repeated URLs · {len(preview.issues)} issues"
        )
    )
    content.append(label("Destination playlist"))
    destination = Gtk.DropDown.new_from_strings(["Create new playlist…", *session.playlist_names])
    content.append(destination)
    name_entry = Gtk.Entry()
    name_entry.set_placeholder_text("New playlist name")
    name_entry.set_max_length(MAX_PLAYLIST_NAME_LENGTH)
    name_entry.set_text(Path(session.source_name).stem[:MAX_PLAYLIST_NAME_LENGTH])
    name_entry.set_activates_default(True)
    content.append(name_entry)

    def destination_changed(*_args: Any) -> None:
        name_entry.set_visible(destination.get_selected() == 0)

    destination.connect("notify::selected", destination_changed)

    lines: list[str] = []
    for entry in preview.entries:
        state = "Already in favorites" if entry.url in session.existing_urls else "New favorite"
        lines.append(f"{entry.name} — {state}\n{entry.url}")
    if preview.issues:
        lines.append("Skipped entries:")
        lines.extend(f"Line {issue.line_number}: {issue.reason}" for issue in preview.issues[:100])
        if len(preview.issues) > 100:
            lines.append(f"… and {len(preview.issues) - 100} more issues.")

    view = Gtk.TextView()
    view.set_editable(False)
    view.set_cursor_visible(False)
    view.set_monospace(True)
    view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
    view.get_buffer().set_text("\n\n".join(lines))
    scroll = Gtk.ScrolledWindow()
    scroll.set_min_content_height(220)
    scroll.set_vexpand(True)
    scroll.set_child(view)
    content.append(scroll)
    content.append(label("Existing names and tags are kept. Import saves valid stations only."))
    error = label("")
    content.append(error)

    def respond(current: Any, response: int) -> None:
        if response != Gtk.ResponseType.ACCEPT:
            session.cancel()
            parent._m3u_import_dialog = None
            current.destroy()
            return
        selected = destination.get_selected()
        existing = selected != 0
        name = session.playlist_names[selected - 1] if existing else name_entry.get_text().strip()
        try:
            result = session.commit(name, existing=existing)
        except Exception as exc:  # noqa: BLE001 - contained GTK import failure.
            error.set_text(str(exc))
            return
        parent._m3u_import_dialog = None
        current.destroy()
        on_saved(name, result)

    dialog.connect("response", respond)
    dialog.present()
    name_entry.grab_focus()


def open_remote_m3u_import(
    parent: Any,
    *,
    profile_id: int,
    profile_is_current: Callable[[], bool],
    on_saved: Callable[[str, M3UImportResult], None],
    on_error: Callable[[str], None],
) -> None:
    """Download outside GTK main loop; discard late results after dismissal."""
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import GLib, Gtk

    active = getattr(parent, "_m3u_import_dialog", None)
    if active is not None:
        active.present()
        return
    active = getattr(parent, "_m3u_import_remote_dialog", None)
    if active is not None:
        active.present()
        return

    dialog: Any = Gtk.Dialog(title="Import stations from URL", transient_for=parent, modal=True)
    dialog.set_default_size(560, 160)
    dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
    preview_button = dialog.add_button("Preview", Gtk.ResponseType.ACCEPT)
    content = dialog.get_content_area()
    content.set_spacing(10)
    for side in ("top", "bottom", "start", "end"):
        getattr(content, f"set_margin_{side}")(16)
    entry = Gtk.Entry()
    entry.set_placeholder_text("https://example.org/stations.m3u")
    content.append(entry)
    status = Gtk.Label(label="No stations are saved before confirmation.", xalign=0)
    status.set_wrap(True)
    content.append(status)
    parent._m3u_import_remote_dialog = dialog
    state = {"closed": False, "busy": False}

    def dispose() -> None:
        state["closed"] = True
        if getattr(parent, "_m3u_import_remote_dialog", None) is dialog:
            parent._m3u_import_remote_dialog = None

    def destroyed(_widget: Any) -> None:
        dispose()

    def finish(session: M3UImportSession | None, error: str | None) -> bool:
        if state["closed"] or getattr(parent, "_m3u_import_remote_dialog", None) is not dialog:
            return False
        state["busy"] = False
        if not profile_is_current():
            dispose()
            cast(Any, dialog).destroy()
            return False
        if error is not None:
            status.set_text(error)
            preview_button.set_sensitive(True)
            entry.set_sensitive(True)
            return False
        if session is None:
            return False
        dispose()
        cast(Any, dialog).destroy()
        _show_preview(parent, session, on_saved=on_saved)
        return False

    def respond(_dialog: Any, response: int) -> None:
        if response != Gtk.ResponseType.ACCEPT:
            dispose()
            dialog.destroy()
            return
        if state["busy"] or state["closed"]:
            return
        url = entry.get_text().strip()
        if not url:
            status.set_text("Enter an HTTP/HTTPS collection URL.")
            return
        if not profile_is_current():
            dispose()
            dialog.destroy()
            return
        state["busy"] = True
        preview_button.set_sensitive(False)
        entry.set_sensitive(False)
        status.set_text("Downloading collection…")

        def worker() -> None:
            try:
                session = prepare_remote_m3u_import(
                    url, profile_id=profile_id, profile_is_current=profile_is_current
                )
            except Exception as exc:  # noqa: BLE001 - report download failures on GTK thread.
                GLib.idle_add(finish, None, str(exc))
            else:
                GLib.idle_add(finish, session, None)

        try:
            threading.Thread(target=worker, name="fluxtuner-remote-import", daemon=True).start()
        except Exception as exc:  # noqa: BLE001 - thread launch failure.
            state["busy"] = False
            preview_button.set_sensitive(True)
            entry.set_sensitive(True)
            on_error(f"Could not start remote import: {exc}")

    dialog.connect("destroy", destroyed)
    dialog.connect("response", respond)
    dialog.present()
    entry.grab_focus()


def open_m3u_import(
    parent: Any,
    *,
    profile_id: int,
    profile_is_current: Callable[[], bool],
    on_saved: Callable[[str, M3UImportResult], None],
    on_error: Callable[[str], None],
) -> None:
    import gi

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    active = getattr(parent, "_m3u_import_dialog", None)
    if active is not None:
        active.present()
        return
    chooser = getattr(parent, "_m3u_import_chooser", None)
    if chooser is not None:
        chooser.show()
        return
    chooser = Gtk.FileChooserNative.new(
        "Import stations", parent, Gtk.FileChooserAction.OPEN, "Open", "Cancel"
    )
    chooser.set_modal(True)
    file_filter = Gtk.FileFilter()
    file_filter.set_name("M3U / M3U8 / PLS station collections")
    for pattern in ("*.m3u", "*.m3u8", "*.pls", "*.M3U", "*.M3U8", "*.PLS"):
        file_filter.add_pattern(pattern)
    chooser.add_filter(file_filter)
    parent._m3u_import_chooser = chooser

    def chosen(current: Any, response: int) -> None:
        selected = current.get_file() if response == Gtk.ResponseType.ACCEPT else None
        parent._m3u_import_chooser = None
        current.destroy()
        if selected is None:
            return
        path = selected.get_path()
        if path is None:
            on_error("Choose a local M3U, M3U8 or PLS file.")
            return
        try:
            session = prepare_m3u_import(
                Path(path),
                profile_id=profile_id,
                profile_is_current=profile_is_current,
            )
        except Exception as exc:  # noqa: BLE001 - contained file/profile failure.
            on_error(f"Could not import stations: {exc}")
            return
        _show_preview(parent, session, on_saved=on_saved)

    chooser.connect("response", chosen)
    chooser.show()
