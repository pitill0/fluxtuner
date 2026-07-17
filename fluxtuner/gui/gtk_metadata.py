from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetadataProjection:
    """Accepted stream metadata ready for GTK label projection."""

    artist: str
    track: str
    raw: str


class MetadataLifecycle:
    """Own GTK metadata request identity, activity and deduplication state."""

    def __init__(self) -> None:
        self.generation = 0
        self.fetch_in_progress = False
        self.last_raw: str | None = None

    def start(self) -> int:
        self.generation += 1
        self.fetch_in_progress = False
        return self.generation

    def stop(self) -> int:
        self.generation += 1
        self.fetch_in_progress = False
        self.last_raw = None
        return self.generation

    def begin_fetch(self) -> int | None:
        if self.fetch_in_progress:
            return None
        self.fetch_in_progress = True
        return self.generation

    def finish_fetch(self, generation: int) -> None:
        if generation == self.generation:
            self.fetch_in_progress = False

    def accept(
        self,
        generation: int,
        metadata: dict[str, Any] | None,
    ) -> MetadataProjection | None:
        if generation != self.generation or not metadata:
            return None

        artist = metadata.get("artist") or "—"
        track = metadata.get("title") or metadata.get("raw") or "—"
        raw = metadata.get("raw") or f"{artist} - {track}"
        if raw == self.last_raw:
            return None

        self.last_raw = raw
        return MetadataProjection(
            artist=artist,
            track=track,
            raw=raw,
        )
