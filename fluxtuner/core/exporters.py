"""Pure, bounded M3U and PLS station collection exporters."""

from __future__ import annotations

from collections.abc import Sequence

from fluxtuner.core.custom_stations import _validate_name, _validate_url
from fluxtuner.core.m3u_import import MAX_FILE_BYTES, MAX_STATIONS, M3UEntry


def _validate_entries(entries: Sequence[M3UEntry]) -> tuple[M3UEntry, ...]:
    """Validate every entry without silently dropping or rewriting stations."""
    if not isinstance(entries, (list, tuple)):
        raise ValueError("Station collection must be a list or tuple.")
    if not entries:
        raise ValueError("Station collection cannot be empty.")
    if len(entries) > MAX_STATIONS:
        raise ValueError(f"Collection exceeds the {MAX_STATIONS} station limit.")

    validated: list[M3UEntry] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, M3UEntry):
            raise ValueError("Invalid station entry.")
        name = _validate_name(entry.name)
        if any(character in name for character in ("\u2028", "\u2029")):
            raise ValueError("Station name contains a Unicode line separator.")
        url = _validate_url(entry.url)
        if url in seen:
            raise ValueError("Duplicate station URL.")
        seen.add(url)
        validated.append(M3UEntry(name=name, url=url))

    return tuple(validated)


def _encode_bounded(lines: list[str]) -> bytes:
    """Generate UTF-8 content accepted by the existing bounded importers."""
    content = ("\n".join(lines) + "\n").encode("utf-8")
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"Export exceeds the {MAX_FILE_BYTES} byte limit.")
    return content


def export_m3u(entries: Sequence[M3UEntry]) -> bytes:
    """Export ordered stations as extended M3U without filesystem access."""
    validated = _validate_entries(entries)
    lines = ["#EXTM3U"]
    for entry in validated:
        lines.append(f"#EXTINF:-1,{entry.name}")
        lines.append(entry.url)
    return _encode_bounded(lines)


def export_pls(entries: Sequence[M3UEntry]) -> bytes:
    """Export ordered stations as PLS v2 without filesystem access."""
    validated = _validate_entries(entries)
    lines = ["[playlist]", f"NumberOfEntries={len(validated)}"]
    for index, entry in enumerate(validated, start=1):
        lines.append(f"File{index}={entry.url}")
        lines.append(f"Title{index}={entry.name}")
        lines.append(f"Length{index}=-1")
    lines.append("Version=2")
    return _encode_bounded(lines)
