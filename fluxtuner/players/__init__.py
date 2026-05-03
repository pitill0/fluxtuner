from __future__ import annotations

from fluxtuner.players.base import PlayerAdapter, PlayerError
from fluxtuner.players.mpv import MpvController


def create_player(name: str = "mpv") -> PlayerAdapter:
    """Create a playback backend by name."""
    normalized = name.lower().strip()

    if normalized == "mpv":
        return MpvController()

    raise PlayerError(f"Unsupported player backend: {name}")


def available_players() -> list[str]:
    """Return supported player backend names."""
    return ["mpv"]
