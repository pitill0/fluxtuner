# SPDX-License-Identifier: MIT
"""Bounded, minimal station and playlist recommendation snapshots."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from urllib.parse import unquote, urlsplit

from fluxtuner.core.custom_stations import _validate_name, _validate_url
from fluxtuner.core.m3u_import import M3UEntry

SNAPSHOT_VERSION = 1
MAX_SHARE_STATIONS = 100
MAX_SHARE_BYTES = 1_048_576
MAX_SHARE_TITLE_LENGTH = 120


def validate_share_title(title: str) -> str:
    """Validate a recommendation title without silently truncating it."""
    clean = _validate_name(title)
    if len(clean) > MAX_SHARE_TITLE_LENGTH:
        raise ValueError("Recommendation title is too long.")
    return clean


_SENSITIVE_PATH_PATTERN = re.compile(
    r"(?:^|/)(?:token|access_token|api_key|apikey|"
    r"password|secret|bearer)(?:/|=)[^/]+",
    re.IGNORECASE,
)


def _has_sensitive_path(path: str) -> bool:
    """Detect clear credential markers and encoded query delimiters.

    This is a conservative sharing policy, not a guarantee that an
    arbitrary stream URL contains no secrets.
    """
    decoded = path

    # Cover both direct encoding and one additional encoding layer.
    for _ in range(3):
        if "?" in decoded or "#" in decoded:
            return True

        if _SENSITIVE_PATH_PATTERN.search(decoded):
            return True

        next_decoded = unquote(decoded)
        if next_decoded == decoded:
            break
        decoded = next_decoded

    return False


def _shareable_station(entry: M3UEntry) -> dict[str, str]:
    if not isinstance(entry, M3UEntry):
        raise ValueError("Invalid recommendation station.")

    name = _validate_name(entry.name)
    url = _validate_url(entry.url)
    parsed = urlsplit(url)

    # Conservative initial policy: these components commonly carry secrets.
    # URL paths are preserved because they can be essential to playback.
    if (
        parsed.query
        or parsed.fragment
        or "?" in url
        or "#" in url
        or _has_sensitive_path(parsed.path)
    ):
        raise ValueError("Stream URL cannot be shared safely.")

    return {"name": name, "url": url}


def build_share_snapshot(
    *,
    kind: str,
    entries: Sequence[M3UEntry],
) -> str:
    """Create a versioned, bounded snapshot for server-side persistence.

    Ownership and recipient authorization belong to the calling service.
    Nothing is written to the database by this function.
    """
    if kind not in ("station", "playlist"):
        raise ValueError("Invalid recommendation kind.")

    if not isinstance(entries, (tuple, list)):
        raise ValueError("Invalid recommendation entries.")

    if not 1 <= len(entries) <= MAX_SHARE_STATIONS:
        raise ValueError("Invalid recommendation station count.")

    if kind == "station" and len(entries) != 1:
        raise ValueError("A station recommendation requires one station.")

    stations = [_shareable_station(entry) for entry in entries]

    snapshot = json.dumps(
        {"version": SNAPSHOT_VERSION, "stations": stations},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if len(snapshot.encode("utf-8")) > MAX_SHARE_BYTES:
        raise ValueError("Recommendation snapshot exceeds storage limit.")

    return snapshot
