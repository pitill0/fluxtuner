from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "fluxtuner"


def _xdg_dir(env_name: str, fallback: Path) -> Path:
    raw_value = os.environ.get(env_name)
    if raw_value:
        return Path(raw_value).expanduser()
    return fallback


CONFIG_DIR = _xdg_dir("XDG_CONFIG_HOME", Path.home() / ".config") / APP_NAME
DATA_DIR = _xdg_dir("XDG_DATA_HOME", Path.home() / ".local" / "share") / APP_NAME
CACHE_DIR = _xdg_dir("XDG_CACHE_HOME", Path.home() / ".cache") / APP_NAME


def ensure_app_dirs() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def config_file(name: str) -> Path:
    ensure_app_dirs()
    return CONFIG_DIR / name


def data_file(name: str) -> Path:
    ensure_app_dirs()
    return DATA_DIR / name


def cache_file(name: str) -> Path:
    ensure_app_dirs()
    return CACHE_DIR / name


def migrate_legacy_file(legacy_path: Path, new_path: Path) -> None:
    """Copy a legacy user file into the current XDG location if needed.

    The legacy file is intentionally kept in place. User data migrations should
    be conservative: copying avoids data loss if the new location later turns
    out to be wrong, sandboxed or incomplete.
    """
    if new_path.exists() or not legacy_path.exists():
        return

    new_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        new_path.write_bytes(legacy_path.read_bytes())
    except OSError:
        return
