# SPDX-License-Identifier: MIT
"""Pure catalog refresh comparison; no database or network operations."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from fluxtuner.core.m3u_import import (
    MAX_STATIONS,
    M3UEntry,
    _validated_entries,
)


@dataclass(frozen=True, slots=True)
class StationChange:
    before: M3UEntry
    after: M3UEntry


@dataclass(frozen=True, slots=True)
class CatalogDiff:
    added: tuple[M3UEntry, ...]
    removed: tuple[M3UEntry, ...]
    changed: tuple[StationChange, ...]
    unchanged: int


def compare_catalogs(
    previous: Sequence[M3UEntry],
    incoming: Sequence[M3UEntry],
) -> CatalogDiff:
    """Compare validated snapshots using exact stream URL identity.

    No changes are persisted by this function. URL changes are represented
    as a removal and addition, never as an inferred station identity.
    """
    if len(previous) > MAX_STATIONS or len(incoming) > MAX_STATIONS:
        raise ValueError("Catalog exceeds the station limit.")

    def validate(
        entries: Sequence[M3UEntry],
        *,
        allow_empty: bool,
    ) -> tuple[M3UEntry, ...]:
        if not entries and allow_empty:
            return ()
        validated = _validated_entries(entries)
        if len(validated) != len(entries):
            raise ValueError("Catalog contains duplicate station URLs.")
        return validated

    old = validate(previous, allow_empty=True)
    new = validate(incoming, allow_empty=False)

    old_by_url = {entry.url: entry for entry in old}
    new_by_url = {entry.url: entry for entry in new}

    added = tuple(
        entry for entry in new if entry.url not in old_by_url
    )
    removed = tuple(
        entry for entry in old if entry.url not in new_by_url
    )
    changed = tuple(
        StationChange(old_by_url[entry.url], entry)
        for entry in new
        if entry.url in old_by_url
        and entry.name != old_by_url[entry.url].name
    )
    unchanged = sum(
        entry.url in old_by_url
        and entry.name == old_by_url[entry.url].name
        for entry in new
    )

    return CatalogDiff(added, removed, changed, unchanged)
