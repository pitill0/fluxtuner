from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from fluxtuner.players.capabilities import PlayerCapabilities


class Player(Protocol):
    def play(self, url: str) -> None: ...

    def stop(self) -> None: ...

    def supports_mute(self) -> bool: ...


class UsageTracker(Protocol):
    def start(self, station: dict[str, Any]) -> None: ...

    def stop(self) -> None: ...


@dataclass(frozen=True)
class PlaybackStartResult:
    success: bool
    status: str
    station: dict[str, Any] | None = None


@dataclass(frozen=True)
class PlaybackStopResult:
    status: str = "Stopped"


def coordinate_playback_start(
    station: dict[str, Any],
    *,
    player: Player,
    player_backend_name: str,
    player_capabilities: PlayerCapabilities,
    profile_name: str | None,
    restored_muted: bool,
    station_supported: Callable[
        [dict[str, Any] | None, PlayerCapabilities],
        bool,
    ],
    unsupported_message: Callable[[dict[str, Any], str], str],
    station_url: Callable[[dict[str, Any] | None], str | None],
    announce_buffering: Callable[[], None],
    apply_preferences_before_start: Callable[[], None],
    apply_volume_after_start: Callable[[], None],
    apply_mute_after_start: Callable[[bool], None],
    usage_tracker: UsageTracker,
    add_history_entry: Callable[..., None],
) -> PlaybackStartResult:
    if not station_supported(station, player_capabilities):
        return PlaybackStartResult(
            success=False,
            status=unsupported_message(station, player_backend_name),
        )

    url = station_url(station)
    if not url:
        return PlaybackStartResult(
            success=False,
            status="Selected station has no playable URL.",
        )

    try:
        announce_buffering()
        apply_preferences_before_start()
        player.play(url)
        apply_volume_after_start()
        if player.supports_mute():
            apply_mute_after_start(restored_muted)
    except Exception as exc:  # noqa: BLE001
        return PlaybackStartResult(
            success=False,
            status=f"Playback failed: {exc}",
        )

    usage_tracker.start(station)
    add_history_entry(station, profile_name=profile_name)
    return PlaybackStartResult(
        success=True,
        status="Playing",
        station=station,
    )


def coordinate_playback_stop(
    *,
    player: Player,
    usage_tracker: UsageTracker,
) -> PlaybackStopResult:
    player.stop()
    usage_tracker.stop()
    return PlaybackStopResult()
