"""TUI collection import using the shared parser and atomic persistence."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from textual import on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static, TextArea

from fluxtuner.core import db
from fluxtuner.core.favorites import list_favorites
from fluxtuner.core.m3u_import import (
    MAX_PLAYLIST_NAME_LENGTH,
    M3UImportResult,
    M3UPreview,
    import_m3u,
    import_m3u_with_new_source,
    load_m3u_file,
    load_station_collection,
)
from fluxtuner.network.network_policy import SystemStreamTargetResolver
from fluxtuner.network.remote_station_collection import preview_remote_station_collection


@dataclass(frozen=True, slots=True)
class M3UImportOutcome:
    name: str
    result: M3UImportResult


def _load_preview(
    path: Path | str, profile_id: int
) -> tuple[M3UPreview, tuple[str, ...], frozenset[str]]:
    if isinstance(path, str) and path.lower().startswith(("http://", "https://")):
        _snapshot, preview = preview_remote_station_collection(path, SystemStreamTargetResolver())
    else:
        local_path = Path(path)
        preview = (
            load_station_collection(local_path)
            if local_path.suffix.lower() == ".pls"
            else load_m3u_file(local_path)
        )
    if not preview.entries:
        raise ValueError("The file contains no valid stations to import.")
    with closing(db.connect()) as conn:
        profile = conn.execute("SELECT id FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        if profile is None:
            raise ValueError("The selected profile is unavailable.")
        names = tuple(item["name"] for item in db.list_playlists(conn, profile_id=profile_id))
        urls = frozenset(item["url_resolved"] for item in list_favorites(conn, profile_id))
    return preview, names, urls


def _save_import(
    profile_id: int,
    preview: M3UPreview,
    name: str,
    existing: bool,
    profile_is_current: Callable[[], bool],
    *,
    local_source: bool = False,
    remote_source: bool = False,
) -> M3UImportOutcome:
    if not profile_is_current():
        raise ValueError("The profile changed. Reopen the import dialog.")

    with closing(db.connect()) as conn, conn:
        conn.execute("BEGIN IMMEDIATE")
        destination = db.get_playlist_record(conn, name, profile_id=profile_id)
        if existing and destination is None:
            raise ValueError("The selected playlist no longer exists. Preview the file again.")
        if not existing and destination is not None:
            raise ValueError(
                "A playlist with this name already exists. Choose it as an existing destination."
            )
        if local_source and remote_source:
            raise ValueError("Conflicting collection source context.")
        if local_source or remote_source:
            outcome = import_m3u_with_new_source(
                conn,
                profile_id=profile_id,
                playlist_name=name,
                entries=preview.entries,
                kind="remote_collection" if remote_source else "local_collection",
            )
            result = outcome.result
        else:
            result = import_m3u(
                conn,
                profile_id=profile_id,
                playlist_name=name,
                entries=preview.entries,
            )
        conn.commit()
    return M3UImportOutcome(name, result)


class M3UImportScreen(ModalScreen[M3UImportOutcome | None]):
    """Preview without writes, then confirm a captured file and profile."""

    BINDINGS = [Binding("escape", "cancel", "Cancel", priority=True)]

    DEFAULT_CSS = """
    M3UImportScreen {
        align: center middle;
        background: $background 80%;
    }
    M3UImportScreen #m3u-form {
        width: 90;
        max-width: 95%;
        height: auto;
        max-height: 95%;
        border: round $accent;
        padding: 1 2;
        background: $surface;
    }
    M3UImportScreen #m3u-review {
        height: auto;
        display: none;
    }
    M3UImportScreen #m3u-preview {
        height: 8;
        margin: 1 0;
    }
    M3UImportScreen #m3u-message {
        height: auto;
        min-height: 1;
        margin: 1 0;
    }
    M3UImportScreen #m3u-actions {
        height: 3;
        margin-top: 1;
    }
    M3UImportScreen Button {
        margin-right: 1;
    }
    M3UImportScreen Input, M3UImportScreen Select {
        margin-bottom: 1;
    }
    """

    def __init__(
        self,
        *,
        profile_id: int,
        profile_is_current: Callable[[], bool],
    ) -> None:
        super().__init__()
        self._profile_id = profile_id
        self._profile_is_current = profile_is_current
        self._preview: M3UPreview | None = None
        self._local_source = False
        self._remote_source = False
        self._names: tuple[str, ...] = ()
        self._generation = 0
        self._pending = ""
        self._import_closed = False

    def compose(self) -> ComposeResult:
        with VerticalScroll(id="m3u-form"):
            yield Label("Import stations")
            yield Static(
                "Local file or HTTP(S) URL, M3U/M3U8/PLS, up to 1 MiB. Preview before saving."
            )
            yield Label("File path or URL")
            yield Input(
                placeholder="~/Downloads/stations.m3u or https://example.org/stations.pls",
                id="m3u-path",
            )
            yield Button("Preview collection", id="m3u-load")
            with Vertical(id="m3u-review"):
                yield Static("", id="m3u-summary", markup=False)
                yield TextArea(
                    "",
                    read_only=True,
                    soft_wrap=True,
                    id="m3u-preview",
                )
                yield Label("Destination playlist")
                yield Select(
                    [("Create new playlist", "new")],
                    value="new",
                    allow_blank=False,
                    id="m3u-destination",
                )
                yield Label("New playlist name", id="m3u-name-label")
                yield Input(
                    max_length=MAX_PLAYLIST_NAME_LENGTH,
                    id="m3u-name",
                )
            yield Static("", id="m3u-message", markup=False)
            with Horizontal(id="m3u-actions"):
                yield Button("Import", id="m3u-save", variant="primary", disabled=True)
                yield Button("Cancel", id="m3u-cancel")

    def on_mount(self) -> None:
        self.query_one("#m3u-path", Input).focus()

    def on_unmount(self) -> None:
        self._import_closed = True
        self._generation += 1

    def _current(self, generation: int) -> bool:
        return not self._import_closed and self.is_mounted and generation == self._generation

    def _message(self, text: str) -> None:
        self.query_one("#m3u-message", Static).update(text)

    def _controls(self) -> None:
        busy = bool(self._pending)
        ready = self._preview is not None
        select = self.query_one("#m3u-destination", Select)
        new = select.value == "new"
        self.query_one("#m3u-path", Input).disabled = busy
        self.query_one("#m3u-load", Button).disabled = busy
        select.disabled = busy or not ready
        self.query_one("#m3u-name", Input).disabled = busy or not ready or not new
        self.query_one("#m3u-name", Input).display = new
        self.query_one("#m3u-name-label", Label).display = new
        self.query_one("#m3u-save", Button).disabled = busy or not ready
        self.query_one("#m3u-cancel", Button).disabled = self._pending == "save"
        self.query_one("#m3u-review", Vertical).display = ready

    @on(Select.Changed, "#m3u-destination")
    def destination_changed(self) -> None:
        self._controls()

    @on(Input.Changed, "#m3u-path")
    def path_changed(self) -> None:
        if self._pending == "save":
            return
        self._generation += 1
        self._preview = None
        self._local_source = False
        self._remote_source = False
        self._names = ()
        self._pending = ""
        self._message("")
        self._controls()

    def action_cancel(self) -> None:
        if self._pending == "save":
            return
        self._import_closed = True
        self._generation += 1
        self.dismiss(None)

    @on(Button.Pressed, "#m3u-cancel")
    def cancel_from_button(self) -> None:
        self.action_cancel()

    @on(Input.Submitted, "#m3u-path")
    def preview_from_input(self, event: Input.Submitted) -> None:
        event.stop()
        self.preview_file()

    @on(Button.Pressed, "#m3u-load")
    def preview_file(self) -> None:
        if self._pending or self._import_closed:
            return
        self._generation += 1
        self._preview = None
        self._local_source = False
        self._remote_source = False
        self._names = ()
        self._pending = "preview"
        self._controls()
        self._message("Reading playlist…")
        raw = self.query_one("#m3u-path", Input).value.strip()
        source: Path | str = (
            raw if raw.lower().startswith(("http://", "https://")) else Path(raw).expanduser()
        )
        self._read_file(source, self._generation)

    @work(exclusive=True, group="m3u-preview")
    async def _read_file(self, path: Path | str, generation: int) -> None:
        try:
            if not self._profile_is_current():
                raise ValueError("The profile changed. Reopen the import dialog.")
            preview, names, existing_urls = await asyncio.to_thread(
                _load_preview, path, self._profile_id
            )
            if not self._current(generation):
                return
            if not self._profile_is_current():
                raise ValueError("The profile changed. Reopen the import dialog.")
            self._preview, self._names = preview, names
            self._local_source = isinstance(path, Path)
            self._remote_source = isinstance(path, str)
            select = self.query_one("#m3u-destination", Select)
            select.set_options(
                [
                    ("Create new playlist", "new"),
                    *((name, str(index)) for index, name in enumerate(names)),
                ]
            )
            select.value = "new"
            if isinstance(path, str):
                target = urlsplit(path)
                source_name = Path(target.path).stem or target.hostname or "stations"
            else:
                source_name = path.stem
            self.query_one("#m3u-name", Input).value = source_name[:MAX_PLAYLIST_NAME_LENGTH]
            self.query_one("#m3u-summary", Static).update(
                f"{len(preview.entries)} valid stations; "
                f"{preview.duplicates} repeated URLs; "
                f"{len(preview.issues)} skipped entries."
            )
            lines = [
                f"{entry.name} — "
                f"{'already in favorites' if entry.url in existing_urls else 'new'}"
                f"\n{entry.url}"
                for entry in preview.entries[:200]
            ]
            if len(preview.entries) > 200:
                lines.append(
                    f"Showing the first 200 of {len(preview.entries)} stations. "
                    "All will be imported."
                )
            lines.extend(
                f"Line {issue.line_number}: {issue.reason}" for issue in preview.issues[:100]
            )
            if len(preview.issues) > 100:
                lines.append("Additional skipped entries omitted.")
            self.query_one("#m3u-preview", TextArea).load_text("\n\n".join(lines))
            self._message("Nothing saved yet. Existing favorite names and tags are preserved.")
        except Exception as exc:  # noqa: BLE001 - contained file/profile failure.
            if self._current(generation):
                self._preview = None
                self._local_source = False
                self._remote_source = False
                self._message(str(exc))
        finally:
            if self._current(generation):
                self._pending = ""
                self._controls()

    @on(Button.Pressed, "#m3u-save")
    def save_import(self) -> None:
        if self._pending or self._import_closed or self._preview is None:
            return
        value = self.query_one("#m3u-destination", Select).value
        existing = value != "new"
        try:
            if existing:
                if not isinstance(value, str) or not value.isdecimal():
                    raise ValueError("Invalid destination.")
                index = int(value)
                name = self._names[index]
            else:
                name = self.query_one("#m3u-name", Input).value.strip()
            if not name:
                raise ValueError("Enter a playlist name.")
        except (ValueError, IndexError):
            self._message("Choose a destination playlist and enter a name when creating one.")
            return
        self._pending = "save"
        self._controls()
        self._message("Importing stations…")
        self._save_file(
            self._preview,
            name,
            existing,
            self._generation,
            local_source=self._local_source,
            remote_source=self._remote_source,
        )

    @work(exclusive=True, group="m3u-save")
    async def _save_file(
        self,
        preview: M3UPreview,
        name: str,
        existing: bool,
        generation: int,
        *,
        local_source: bool = False,
        remote_source: bool = False,
    ) -> None:
        try:
            outcome = await asyncio.to_thread(
                _save_import,
                self._profile_id,
                preview,
                name,
                existing,
                self._profile_is_current,
                local_source=local_source,
                remote_source=remote_source,
            )
            if self._current(generation):
                self._import_closed = True
                self.dismiss(outcome)
        except Exception as exc:  # noqa: BLE001 - contained import/storage failure.
            if self._current(generation):
                self._message(str(exc))
        finally:
            if self._current(generation):
                self._pending = ""
                self._controls()
