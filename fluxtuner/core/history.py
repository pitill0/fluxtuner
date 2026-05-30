from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fluxtuner.core.storage import write_json_atomic
from fluxtuner.logging_config import get_logger
from fluxtuner.paths import data_file, migrate_legacy_file

logger = get_logger(__name__)
LEGACY_HISTORY_FILE = Path.home() / ".fluxtuner_history.json"
HISTORY_FILE = data_file("history.json")
MAX_HISTORY_ITEMS = 100


def _station_key(station: dict[str, Any]) -> str:
    return str(station.get("url") or station.get("name") or "")


def load_history() -> list[dict[str, Any]]:
    migrate_legacy_file(LEGACY_HISTORY_FILE, HISTORY_FILE)

    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except OSError:
        logger.warning("Could not read history data; returning empty history", exc_info=True)
        return []
    except json.JSONDecodeError:
        logger.warning("Invalid history JSON; returning empty history", exc_info=True)
        return []

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def save_history(history: list[dict[str, Any]]) -> None:
    migrate_legacy_file(LEGACY_HISTORY_FILE, HISTORY_FILE)

    try:
        write_json_atomic(HISTORY_FILE, history[:MAX_HISTORY_ITEMS])
    except OSError:
        logger.error("Could not write history data", exc_info=True)
        raise


def add_history(station: dict[str, Any]) -> None:
    if not station.get("url"):
        return

    now = datetime.now(UTC).isoformat()
    key = _station_key(station)
    history = load_history()

    previous = next((item for item in history if _station_key(item) == key), None)
    play_count = int(previous.get("play_count", 0)) + 1 if previous else 1

    entry = dict(station)
    entry["last_played_at"] = now
    entry["play_count"] = play_count

    history = [item for item in history if _station_key(item) != key]
    history.insert(0, entry)
    save_history(history)


def clear_history() -> None:
    save_history([])
