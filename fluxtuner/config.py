from __future__ import annotations

import json
from pathlib import Path
from typing import Any

APP_NAME = "fluxtuner"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_CONFIG: dict[str, Any] = {
    "theme": "default",
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
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(config, indent=2, sort_keys=True), encoding="utf-8")


def get_config_value(key: str, default: Any = None) -> Any:
    """Return a single configuration value."""
    return load_config().get(key, default)


def set_config_value(key: str, value: Any) -> None:
    """Set and persist a single configuration value."""
    config = load_config()
    config[key] = value
    save_config(config)
