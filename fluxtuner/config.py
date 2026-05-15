from __future__ import annotations

import json
from typing import Any

from fluxtuner.paths import config_file

CONFIG_FILE = config_file("config.json")


def default_config() -> dict[str, Any]:
    return {
        "theme": "default",
        "playback": {
            "last_station": None,
            "volume": None,
            "muted": False,
        },
    }


def load_config() -> dict[str, Any]:
    """Load user configuration from ~/.config/fluxtuner/config.json."""
    if not CONFIG_FILE.exists():
        return default_config()

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default_config()

    config = default_config()
    if isinstance(data, dict):
        config.update(data)
    return config


def save_config(config: dict[str, Any]) -> None:
    """Persist user configuration."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def get_config_value(key: str, default: Any = None) -> Any:
    """Return a single configuration value."""
    return load_config().get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set and persist a single configuration value."""
    config = load_config()
    config[key] = value
    save_config(config)


def _normalize_volume(value: Any) -> int | None:
    if value is None:
        return None

    try:
        return max(0, min(100, int(round(float(value)))))
    except (TypeError, ValueError):
        return None


def _normalize_muted(value: Any) -> bool:
    return bool(value)


def get_playback_state() -> dict[str, Any]:
    """Return normalized persisted playback preferences and last station metadata."""
    state = load_config().get("playback", {})
    if not isinstance(state, dict):
        return {}

    return {
        "last_station": state.get("last_station"),
        "volume": _normalize_volume(state.get("volume")),
        "muted": _normalize_muted(state.get("muted", False)),
    }


def save_playback_state(
    *,
    last_station: dict[str, Any] | None = None,
    volume: int | float | None = None,
    muted: bool | None = None,
) -> None:
    """Persist playback state without overwriting omitted values."""
    config = load_config()
    playback = config.get("playback", {})
    if not isinstance(playback, dict):
        playback = {}

    if last_station is not None:
        playback["last_station"] = last_station
    if volume is not None:
        clean_volume = _normalize_volume(volume)
        if clean_volume is not None:
            playback["volume"] = clean_volume
    if muted is not None:
        playback["muted"] = _normalize_muted(muted)

    config["playback"] = playback
    save_config(config)
