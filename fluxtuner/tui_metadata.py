from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MetadataProjection:
    """Accepted stream metadata ready for UI projection."""

    artist: str
    track: str
    raw: str


class MetadataLifecycle:
    """Own TUI metadata request state without depending on Textual."""

    def __init__(self, *, poll_interval: float = 15.0) -> None:
        self.poll_interval = poll_interval
        self.task: asyncio.Task[None] | None = None
        self.request_id = 0
        self.last_raw: str | None = None
        self.last_fetch_at = 0.0

    def reset_projection(self) -> None:
        self.last_raw = None

    def allow_immediate_poll(self) -> None:
        self.last_fetch_at = 0.0

    def cancel(self) -> None:
        self.request_id += 1
        task = self.task
        self.task = None
        if task and not task.done():
            task.cancel()

    def can_schedule(self, stream_url: str | None, *, now: float) -> bool:
        if not stream_url:
            return False
        if now - self.last_fetch_at < self.poll_interval:
            return False
        return not self.task or self.task.done()

    def begin_request(self, *, now: float) -> int:
        self.last_fetch_at = now
        self.request_id += 1
        return self.request_id

    def attach_task(self, task: asyncio.Task[None]) -> None:
        self.task = task

    def complete_task(self, task: asyncio.Task[Any] | None) -> None:
        if task is self.task:
            self.task = None

    def request_is_current(
        self,
        request_id: int,
        stream_url: str,
        *,
        current_stream_url: str | None,
    ) -> bool:
        return request_id == self.request_id and current_stream_url == stream_url

    def accept(
        self,
        request_id: int,
        stream_url: str,
        metadata: dict[str, Any] | None,
        *,
        current_stream_url: str | None,
    ) -> MetadataProjection | None:
        if not self.request_is_current(
            request_id,
            stream_url,
            current_stream_url=current_stream_url,
        ):
            return None
        if not metadata:
            return None

        raw = metadata.get("raw") or ""
        if raw and raw == self.last_raw:
            return None

        self.last_raw = raw
        return MetadataProjection(
            artist=metadata.get("artist") or "—",
            track=metadata.get("title") or metadata.get("raw") or "—",
            raw=raw,
        )
