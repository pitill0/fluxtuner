from __future__ import annotations

from fluxtuner.players.base import PlayerAdapter, PlayerError
from fluxtuner.players.ffplay import FfplayController
from fluxtuner.players.mpv import MpvController

PLAYER_BACKENDS = {
    "mpv": MpvController,
    "ffplay": FfplayController,
}


def available_players() -> list[str]:
    """Return available playback backend names."""
    return [
        backend_name
        for backend_name, controller_class in PLAYER_BACKENDS.items()
        if controller_class.is_available()
    ]


def selected_player_name(name: str | None = None) -> str:
    """Resolve the requested player name into an available backend."""
    normalized = (name or "auto").lower().strip()

    if normalized == "auto":
        for backend_name, controller_class in PLAYER_BACKENDS.items():
            if controller_class.is_available():
                return backend_name

        supported = ", ".join(PLAYER_BACKENDS)
        raise PlayerError(f"No supported player backend available. Install one of: {supported}")

    if normalized not in PLAYER_BACKENDS:
        supported = ", ".join(PLAYER_BACKENDS)
        raise PlayerError(f"Unsupported player backend: {name}. Supported: auto, {supported}")

    controller_class = PLAYER_BACKENDS[normalized]
    if not controller_class.is_available():
        available = available_players()
        available_text = ", ".join(available) if available else "none"
        raise PlayerError(
            f"Player backend '{normalized}' is not available. Available backends: {available_text}"
        )

    return normalized


def create_player(name: str | None = None) -> PlayerAdapter:
    """Create a playback backend by name or auto-detect one."""
    selected = selected_player_name(name)
    return PLAYER_BACKENDS[selected]()
