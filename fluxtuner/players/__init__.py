# Player backend registry for FluxTuner.

from __future__ import annotations

import shutil
from typing import Any

from fluxtuner.players.base import PlayerError
from fluxtuner.players.ffplay import FfplayController
from fluxtuner.players.mpv import MpvController


PLAYER_REGISTRY: dict[str, type[Any]] = {
    "mpv": MpvController,
    "ffplay": FfplayController,
}


def _backend_is_available(name: str, controller_class: type[Any]) -> bool:
    """Return whether a backend can be used on this system.

    Newer backends may expose is_available(); older backends, such as the
    existing mpv controller, are checked by executable name.
    """
    is_available = getattr(controller_class, "is_available", None)
    if callable(is_available):
        return bool(is_available())

    return shutil.which(name) is not None


def available_players() -> list[str]:
    return [
        name
        for name, controller_class in PLAYER_REGISTRY.items()
        if _backend_is_available(name, controller_class)
    ]


def create_player(name: str = "mpv"):
    normalized_name = (name or "mpv").strip().lower()

    controller_class = PLAYER_REGISTRY.get(normalized_name)
    if controller_class is None:
        supported = ", ".join(sorted(PLAYER_REGISTRY))
        raise PlayerError(f"Unsupported player backend: {name}. Supported: {supported}")

    if not _backend_is_available(normalized_name, controller_class):
        available = ", ".join(available_players()) or "none"
        raise PlayerError(
            f"Player backend '{normalized_name}' is not available. "
            f"Install '{normalized_name}' or choose one of: {available}"
        )

    return controller_class()
