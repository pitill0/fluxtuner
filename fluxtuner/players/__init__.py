from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from fluxtuner.players.base import PlayerAdapter, PlayerError
from fluxtuner.players.ffplay import FfplayController
from fluxtuner.players.mpv import MpvController

if TYPE_CHECKING:
    from collections.abc import Callable


PLAYER_REGISTRY: dict[str, type[PlayerAdapter]] = {
    "mpv": MpvController,
    "ffplay": FfplayController,
}


def _backend_is_available(name: str, controller_class: type[PlayerAdapter]) -> bool:
    is_available = getattr(controller_class, "is_available", None)
    if callable(is_available):
        return bool(is_available())

    return shutil.which(name) is not None


def available_players() -> list[str]:
    """Return available player backend names for this system."""
    return [
        name
        for name, controller_class in PLAYER_REGISTRY.items()
        if _backend_is_available(name, controller_class)
    ]


def create_player(name: str | None = None) -> PlayerAdapter:
    """Create a playback backend by name, or auto-detect one if omitted."""
    available = available_players()

    if not available:
        supported = ", ".join(sorted(PLAYER_REGISTRY))
        raise PlayerError(f"No supported player backend available. Install one of: {supported}")

    normalized = (name or available[0]).lower().strip()

    controller_class = PLAYER_REGISTRY.get(normalized)
    if controller_class is None:
        supported = ", ".join(sorted(PLAYER_REGISTRY))
        raise PlayerError(f"Unsupported player backend: {name}. Supported: {supported}")

    if not _backend_is_available(normalized, controller_class):
        raise PlayerError(
            f"Player backend '{normalized}' is not available. "
            f"Available backends: {', '.join(available)}"
        )

    return controller_class()
