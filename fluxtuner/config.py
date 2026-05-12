from __future__ import annotations

import json
from pathlib import Path
from fluxtuner.paths import config_file, migrate_legacy_file
from typing import Any

APP_NAME = "fluxtuner"
LEGACY_CONFIG_FILE = Path.home() / ".config" / APP_NAME / "config.json"
CONFIG_FILE = config_file("config.json")
migrate_legacy_file(LEGACY_CONFIG_FILE, CONFIG_FILE)
DEFAULT_CONFIG: dict[str, Any] = {
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
        return DEFAULT_CONFIG.copy()

    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_CONFIG.copy()

    config = DEFAULT_CONFIG.copy()
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


def get_playback_state() -> dict[str, Any]:
    """Return persisted playback preferences and last station metadata."""
    state = load_config().get("playback", {})
    return state if isinstance(state, dict) else {}


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
        playback["volume"] = int(round(volume))
    if muted is not None:
        playback["muted"] = bool(muted)

    config["playback"] = playback
    save_config(config)
