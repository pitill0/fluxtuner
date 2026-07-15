from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any, Protocol

from fluxtuner.core.compatibility import unsupported_station_message
from fluxtuner.core.favorites import favorite_display_name


class Player(Protocol):
    def play(self, url: str) -> None: ...

    def stop(self) -> None: ...


class UsageTracker(Protocol):
    def stop(self) -> None: ...


@dataclass(frozen=True)
class PlaybackStartResult:
    success: bool
    status: str
    station: dict[str, Any] | None = None
    error_notification: str | None = None


@dataclass(frozen=True)
class PlaybackStopResult:
    status: str = "Playback stopped."


def coordinate_playback_start(
    station: dict[str, Any],
    *,
    player: Player,
    player_backend_name: str,
    profile_name: str | None,
    station_supported: Callable[[dict[str, Any]], bool],
    station_url: Callable[[dict[str, Any] | None], str | None],
    start_usage_tracking: Callable[[dict[str, Any]], None],
    add_history_entry: Callable[..., None],
    apply_restored_preferences: Callable[[], None],
    persist_playback_state: Callable[..., None],
) -> PlaybackStartResult:
    if not station_supported(station):
        return PlaybackStartResult(
            success=False,
            status=unsupported_station_message(station, player_backend_name),
        )

    url = station_url(station)
    if not url:
        return PlaybackStartResult(
            success=False,
            status="Selected station has no playable URL.",
        )

    try:
        player.play(url)
    except Exception as exc:  # noqa: BLE001
        message = f"Playback failed: {exc}"
        return PlaybackStartResult(
            success=False,
            status=message,
            error_notification=message,
        )

    start_usage_tracking(station)
    add_history_entry(station, profile_name=profile_name)
    apply_restored_preferences()
    persist_playback_state(last_station=station)
    return PlaybackStartResult(
        success=True,
        station=station,
        status=f"Playing: {favorite_display_name(station)}",
    )


def coordinate_playback_stop(
    *,
    player: Player,
    usage_tracker: UsageTracker,
) -> PlaybackStopResult:
    player.stop()
    with suppress(Exception):
        usage_tracker.stop()
    return PlaybackStopResult()
