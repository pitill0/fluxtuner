from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

from fluxtuner.players.base import PlayerAdapter, PlayerError
from fluxtuner.players.ffplay import FfplayController
from fluxtuner.players.mpv import MpvController

if TYPE_CHECKING:
    from collections.abc import Callable


PLAYER_PRIORITY = ["mpv", "ffplay"]

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
    return [
        name
        for name in PLAYER_PRIORITY
        if name in PLAYER_REGISTRY and _backend_is_available(name, PLAYER_REGISTRY[name])
    ]


def selected_player_name(name: str | None = None) -> str:
    available = available_players()

    if not available:
        supported = ", ".join(sorted(PLAYER_REGISTRY))
        raise PlayerError(f"No supported player backend available. Install one of: {supported}")

    normalized = (name or available[0]).lower().strip()

    if normalized not in PLAYER_REGISTRY:
        supported = ", ".join(sorted(PLAYER_REGISTRY))
        raise PlayerError(f"Unsupported player backend: {name}. Supported: {supported}")

    if not _backend_is_available(normalized, PLAYER_REGISTRY[normalized]):
        raise PlayerError(
            f"Player backend '{normalized}' is not available. "
            f"Available backends: {', '.join(available)}"
        )

    return normalized

def create_player(name: str | None = None) -> PlayerAdapter:
    selected = selected_player_name(name)
    return PLAYER_REGISTRY[selected]()

