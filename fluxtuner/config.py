from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fluxtuner.core.storage import write_json_atomic
from fluxtuner.logging_config import get_logger
from fluxtuner.paths import config_file

logger = get_logger(__name__)

CONFIG_FILE = config_file("config.json")


def default_config() -> dict[str, Any]:
    return {
        "theme": "default",
        "gtk_appearance": "system",
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
    except OSError:
        logger.warning("Could not read config file; using default config", exc_info=True)
        return default_config()
    except json.JSONDecodeError:
        logger.warning("Invalid config JSON; using default config", exc_info=True)
        return default_config()

    config = default_config()
    if isinstance(data, dict):
        config.update(data)
    return config


def save_config(config: dict[str, Any]) -> None:
    """Persist user configuration."""
    try:
        write_json_atomic(CONFIG_FILE, config, sort_keys=True)
    except OSError:
        logger.error("Could not write config file", exc_info=True)
        raise


def get_config_value(key: str, default: Any = None) -> Any:
    """Return a single configuration value."""
    return load_config().get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set and persist a single configuration value."""
    config = load_config()
    config[key] = value
    save_config(config)


_STORAGE_KEYS = frozenset({"recordings_directory", "rips_directory"})


def get_storage_directory(key: str) -> Path | None:
    """Return a configured absolute storage root, or the default sentinel."""
    if key not in _STORAGE_KEYS:
        raise ValueError(f"Unknown storage directory setting: {key}")

    value = get_config_value(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"Invalid storage directory setting: {key}")

    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"Storage directory must be absolute: {key}")

    return path


def set_storage_directory(key: str, directory: str | Path | None) -> None:
    """Persist a storage root without creating or moving any files."""
    if key not in _STORAGE_KEYS:
        raise ValueError(f"Unknown storage directory setting: {key}")

    if directory is None:
        normalized = None
    else:
        if not isinstance(directory, (str, Path)):
            raise ValueError("Storage directory must be a path or None")
        if not str(directory).strip():
            raise ValueError("Storage directory cannot be empty")

        path = Path(directory).expanduser()
        if not path.is_absolute():
            raise ValueError("Storage directory must be absolute")
        normalized = str(path)

    set_config_value(key, normalized)


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
