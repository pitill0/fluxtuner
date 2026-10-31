# SPDX-License-Identifier: MIT

"""Bounded local station-collection parsing and atomic library import."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from fluxtuner.core import db
from fluxtuner.core import station_provenance as provenance
from fluxtuner.core.custom_stations import (
    MAX_NAME_LENGTH,
    _has_controls,
    _has_unsafe_bidi_controls,
    _validate_name,
    _validate_url,
    add_custom_station,
)

MAX_FILE_BYTES = 1024 * 1024
MAX_STATIONS = 5000
MAX_LINES = 25000
MAX_PLAYLIST_NAME_LENGTH = 120


@dataclass(frozen=True, slots=True)
class M3UEntry:
    name: str
    url: str
    line_number: int = 0


@dataclass(frozen=True, slots=True)
class M3UIssue:
    line_number: int
    reason: str


@dataclass(frozen=True, slots=True)
class M3UPreview:
    entries: tuple[M3UEntry, ...]
    issues: tuple[M3UIssue, ...]
    duplicates: int


@dataclass(frozen=True, slots=True)
class M3UImportResult:
    added_favorites: int
    existing_favorites: int
    added_to_playlist: int
    already_in_playlist: int


@dataclass(frozen=True, slots=True)
class M3UImportWithSourceResult:
    """A newly created provenance source and the unchanged import result."""

    result: M3UImportResult
    source_id: int


def _extinf_name(line: str) -> str:
    """Find the title separator without splitting quoted attribute values."""
    quoted = False
    for index, character in enumerate(line):
        if character == '"':
            quoted = not quoted
        elif character == "," and not quoted:
            return line[index + 1 :]
    raise ValueError("Malformed EXTINF entry: station name separator is missing.")


def parse_m3u(data: bytes) -> M3UPreview:  # noqa: C901 - reviewed ceiling 19; see docs/complexity-baseline.json
    """Parse UTF-8 station collections without database or network access."""
    if not isinstance(data, bytes):
        raise ValueError("Playlist content must be bytes.")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"Playlist exceeds the {MAX_FILE_BYTES} byte limit.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Playlist must be UTF-8 text.") from None
    if "\x00" in text:
        raise ValueError("Playlist contains binary data.")

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    if len(lines) > MAX_LINES:
        raise ValueError(f"Playlist exceeds the {MAX_LINES} line limit.")
    if any(line.strip().upper().startswith("#EXT-X-") for line in lines):
        raise ValueError("This is an HLS manifest, not a station collection.")

    entries: list[M3UEntry] = []
    issues: list[M3UIssue] = []
    seen: set[str] = set()
    duplicates = 0
    candidates = 0
    pending_name: str | None = None
    pending_line: int | None = None
    pending_error = False

    for number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        if line.upper().startswith("#EXTINF:"):
            if pending_line is not None and not pending_error:
                issues.append(M3UIssue(pending_line, "Station entry has no stream URL."))
            pending_line = number
            pending_name = None
            pending_error = False
            try:
                pending_name = _extinf_name(line)
            except ValueError as exc:
                issues.append(M3UIssue(number, str(exc)))
                pending_error = True
            continue
        if line.startswith("#"):
            continue

        candidates += 1
        if candidates > MAX_STATIONS:
            raise ValueError(f"Playlist exceeds the {MAX_STATIONS} station limit.")

        name = pending_name
        skip_entry = pending_error
        pending_name = None
        pending_line = None
        pending_error = False
        if skip_entry:
            continue

        try:
            url = _validate_url(line)
            if name is None or not name.strip():
                name = (urlsplit(url).hostname or "Unknown station")[:MAX_NAME_LENGTH]
            name = _validate_name(name)
        except ValueError as exc:
            issues.append(M3UIssue(number, str(exc)))
            continue
        if url in seen:
            duplicates += 1
            continue
        seen.add(url)
        entries.append(M3UEntry(name=name, url=url, line_number=number))

    if pending_line is not None and not pending_error:
        issues.append(M3UIssue(pending_line, "Station entry has no stream URL."))

    return M3UPreview(tuple(entries), tuple(issues), duplicates)


_PLSAttributes = dict[int, dict[str, tuple[str, int]]]


def _pls_lines(data: bytes) -> list[str]:
    """Validate byte, encoding and line bounds before interpreting PLS fields."""
    if not isinstance(data, bytes):
        raise ValueError("Playlist content must be bytes.")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"Playlist exceeds the {MAX_FILE_BYTES} byte limit.")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Playlist must be UTF-8 text.") from None
    if "\x00" in text:
        raise ValueError("Playlist contains binary data.")
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError(f"Playlist exceeds the {MAX_LINES} line limit.")
    return lines


def _pls_records(lines: list[str], issues: list[M3UIssue]) -> Iterator[tuple[int, str, str]]:
    """Yield first occurrences of keys, preserving syntax issues and line numbers."""
    header = False
    seen_keys: set[str] = set()
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith((";", "#")):
            continue
        if not header:
            if line.casefold() != "[playlist]":
                raise ValueError("PLS playlist must begin with [playlist].")
            header = True
            continue
        if line.startswith("["):
            issues.append(M3UIssue(number, "Unexpected PLS section."))
            continue
        if "=" not in line:
            issues.append(M3UIssue(number, "Malformed PLS key/value line."))
            continue
        key, value = line.split("=", 1)
        key = key.strip().casefold()
        value = value.strip()
        if key in seen_keys:
            issues.append(M3UIssue(number, f"Duplicate PLS key: {key}."))
            continue
        seen_keys.add(key)
        yield number, key, value
    if not header:
        raise ValueError("PLS playlist must begin with [playlist].")


def _pls_fields(lines: list[str], issues: list[M3UIssue]) -> tuple[_PLSAttributes, int | None]:
    """Interpret bounded PLS v2 metadata and indexed station attributes."""
    attributes: _PLSAttributes = {}
    declared: int | None = None
    for number, key, value in _pls_records(lines, issues):
        if key == "numberofentries":
            if not value.isascii() or not value.isdecimal() or len(value) > 6:
                issues.append(M3UIssue(number, "Invalid NumberOfEntries."))
            else:
                declared = int(value)
                if declared > MAX_STATIONS:
                    raise ValueError(f"Playlist exceeds the {MAX_STATIONS} station limit.")
            continue
        if key == "version":
            if value != "2":
                issues.append(M3UIssue(number, "Unsupported PLS version."))
            continue
        match = re.fullmatch(r"(file|title|length)([1-9][0-9]*)", key)
        if match is None:
            issues.append(M3UIssue(number, f"Unrecognized PLS field: {key}."))
            continue
        kind, raw_index = match.groups()
        if len(raw_index) > 6:
            raise ValueError(f"Playlist exceeds the {MAX_STATIONS} station limit.")
        index = int(raw_index)
        if index > MAX_STATIONS:
            raise ValueError(f"Playlist exceeds the {MAX_STATIONS} station limit.")
        attributes.setdefault(index, {})[kind] = (value, number)

    return attributes, declared


def _pls_entry(
    fields: dict[str, tuple[str, int]], index: int, issues: list[M3UIssue]
) -> M3UEntry | None:
    """Validate one station using the existing URL and display-name policy."""
    file_record = fields.get("file")
    if file_record is None:
        number = next(iter(fields.values()))[1]
        issues.append(M3UIssue(number, f"PLS entry {index} has no File field."))
        return None
    raw_url, number = file_record
    try:
        url = _validate_url(raw_url)
        title = fields.get("title", ("", number))[0]
        if not title.strip():
            title = (urlsplit(url).hostname or "Unknown station")[:MAX_NAME_LENGTH]
        name = _validate_name(title)
    except ValueError as exc:
        issues.append(M3UIssue(number, str(exc)))
        return None
    return M3UEntry(name, url, number)


def _pls_preview(
    attributes: _PLSAttributes, issues: list[M3UIssue], declared: int | None
) -> M3UPreview:
    """Build the ordered preview, preserving diagnostics and URL deduplication."""
    file_count = sum("file" in fields for fields in attributes.values())
    if declared is not None and declared != file_count:
        issues.append(M3UIssue(1, "NumberOfEntries does not match File entries."))

    entries: list[M3UEntry] = []
    urls: set[str] = set()
    duplicates = 0
    for index in sorted(attributes):
        entry = _pls_entry(attributes[index], index, issues)
        if entry is None:
            continue
        if entry.url in urls:
            duplicates += 1
            continue
        urls.add(entry.url)
        entries.append(entry)
    return M3UPreview(tuple(entries), tuple(issues), duplicates)


def parse_pls(data: bytes) -> M3UPreview:
    """Parse bounded PLS v2 station collections without any I/O."""
    lines = _pls_lines(data)
    issues: list[M3UIssue] = []
    attributes, declared = _pls_fields(lines, issues)
    if len(attributes) > MAX_STATIONS:
        raise ValueError(f"Playlist exceeds the {MAX_STATIONS} station limit.")
    return _pls_preview(attributes, issues, declared)


def parse_station_collection(data: bytes) -> M3UPreview:
    """Dispatch PLS by its header, preserving existing M3U behavior."""
    if not isinstance(data, bytes):
        raise ValueError("Playlist content must be bytes.")
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f"Playlist exceeds the {MAX_FILE_BYTES} byte limit.")
    if data.decode("utf-8-sig", errors="replace").lstrip().lower().startswith("[playlist]"):
        return parse_pls(data)
    return parse_m3u(data)


def load_station_collection(path: Path) -> M3UPreview:
    """Bound file reading and select PLS according to the local extension."""
    path = Path(path)
    if not path.is_file():
        raise ValueError("Choose a local playlist file.")
    with path.open("rb") as source:
        data = source.read(MAX_FILE_BYTES + 1)
    if path.suffix.lower() == ".pls":
        return parse_pls(data)
    return parse_station_collection(data)


def load_m3u_file(path: Path) -> M3UPreview:
    """Read at most the configured byte limit plus one detection byte."""
    path = Path(path)
    if not path.is_file():
        raise ValueError("Choose a local playlist file.")
    with path.open("rb") as source:
        data = source.read(MAX_FILE_BYTES + 1)
    return parse_m3u(data)


def _validated_entries(entries: Sequence[M3UEntry]) -> tuple[M3UEntry, ...]:
    """Revalidate selections so persistence does not trust preview objects."""
    if not entries:
        raise ValueError("There are no valid stations to import.")
    if len(entries) > MAX_STATIONS:
        raise ValueError(f"Import exceeds the {MAX_STATIONS} station limit.")
    accepted: list[M3UEntry] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, M3UEntry):
            raise ValueError("Invalid station selection.")
        name = _validate_name(entry.name)
        url = _validate_url(entry.url)
        if url not in seen:
            accepted.append(M3UEntry(name, url, entry.line_number))
            seen.add(url)
    return tuple(accepted)


def import_m3u(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    playlist_name: str,
    entries: Sequence[M3UEntry],
    source_id: int | None = None,
) -> M3UImportResult:
    """Import stations into favorites and one playlist without committing.

    The caller owns the connection and transaction. All writes made by this
    operation are rolled back together on failure. Earlier caller writes survive.
    Existing station records, favorite names, tags and memberships are preserved.
    """
    if (
        not isinstance(playlist_name, str)
        or _has_controls(playlist_name)
        or _has_unsafe_bidi_controls(playlist_name)
    ):
        raise ValueError("Playlist name contains invalid characters.")
    clean_name = playlist_name.strip()
    if not clean_name:
        raise ValueError("Playlist name is required.")
    if len(clean_name) > MAX_PLAYLIST_NAME_LENGTH:
        raise ValueError(f"Playlist name must not exceed {MAX_PLAYLIST_NAME_LENGTH} characters.")
    if type(profile_id) is not int or profile_id <= 0:
        raise ValueError("An existing profile is required.")
    if conn.execute("SELECT 1 FROM profiles WHERE id = ?", (profile_id,)).fetchone() is None:
        raise ValueError("The selected profile no longer exists.")
    accepted = _validated_entries(entries)
    if source_id is not None:
        provenance.get_source(conn, profile_id=profile_id, source_id=source_id)

    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute("SAVEPOINT m3u_import")
    try:
        playlist = conn.execute(
            "SELECT id FROM playlists WHERE profile_id = ? AND lower(name) = lower(?)",
            (profile_id, clean_name),
        ).fetchone()
        if playlist is None:
            db.create_playlist_record(conn, clean_name, profile_id=profile_id)
            playlist = conn.execute(
                "SELECT id FROM playlists WHERE profile_id = ? AND lower(name) = lower(?)",
                (profile_id, clean_name),
            ).fetchone()
        if playlist is None:
            raise RuntimeError("Could not create the destination playlist.")
        playlist_id = int(playlist["id"])
        position = int(
            conn.execute(
                "SELECT COALESCE(MAX(position), -1) + 1 "
                "FROM playlist_stations WHERE playlist_id = ?",
                (playlist_id,),
            ).fetchone()[0]
        )
        added_favorites = 0
        added_to_playlist = 0
        for entry in accepted:
            added_favorites += int(
                add_custom_station(
                    conn,
                    profile_id=profile_id,
                    name=entry.name,
                    url=entry.url,
                )
            )
            station = conn.execute(
                "SELECT id FROM stations WHERE station_key = ?", (entry.url,)
            ).fetchone()
            if station is None:
                raise RuntimeError("Could not find the imported station.")

            if source_id is not None:
                provenance.record_observation(
                    conn,
                    profile_id=profile_id,
                    source_id=source_id,
                    station_id=int(station["id"]),
                )

            # Link the existing row directly: the normal playlist helper
            # upserts station metadata, which imports must preserve.
            cursor = conn.execute(
                """
                INSERT OR IGNORE INTO playlist_stations (
                    playlist_id, station_id, position, created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (playlist_id, int(station["id"]), position, db.utc_now()),
            )
            if cursor.rowcount > 0:
                added_to_playlist += 1
                position += 1

        result = M3UImportResult(
            added_favorites=added_favorites,
            existing_favorites=len(accepted) - added_favorites,
            added_to_playlist=added_to_playlist,
            already_in_playlist=len(accepted) - added_to_playlist,
        )
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT m3u_import")
        conn.execute("RELEASE SAVEPOINT m3u_import")
        raise
    conn.execute("RELEASE SAVEPOINT m3u_import")
    return result


def import_m3u_with_new_source(
    conn: sqlite3.Connection,
    *,
    profile_id: int,
    playlist_name: str,
    entries: Sequence[M3UEntry],
    display_name: str | None = None,
    kind: str = "local_collection",
) -> M3UImportWithSourceResult:
    """Atomically create a collection source and import its stations.

    The caller controls commit/rollback. Remote kind is reserved for
    callers that have obtained a validated remote collection snapshot.
    """
    if not conn.in_transaction:
        conn.execute("BEGIN")
    conn.execute("SAVEPOINT m3u_import_new_source")
    try:
        source_id = provenance.create_source(
            conn,
            profile_id=profile_id,
            kind=kind,
            display_name=display_name,
        )
        result = import_m3u(
            conn,
            profile_id=profile_id,
            playlist_name=playlist_name,
            entries=entries,
            source_id=source_id,
        )
    except Exception:
        conn.execute("ROLLBACK TO SAVEPOINT m3u_import_new_source")
        conn.execute("RELEASE SAVEPOINT m3u_import_new_source")
        raise
    conn.execute("RELEASE SAVEPOINT m3u_import_new_source")
    return M3UImportWithSourceResult(result=result, source_id=source_id)
