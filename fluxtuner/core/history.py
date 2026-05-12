from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from fluxtuner.paths import data_file, migrate_legacy_file
from typing import Any

LEGACY_HISTORY_FILE = Path.home() / ".fluxtuner_history.json"
HISTORY_FILE = data_file("history.json")
migrate_legacy_file(LEGACY_HISTORY_FILE, HISTORY_FILE)
MAX_HISTORY_ITEMS = 100


def _station_key(station: dict[str, Any]) -> str:
    return str(station.get("url") or station.get("name") or "")


def load_history() -> list[dict[str, Any]]:
    if not HISTORY_FILE.exists():
        return []

    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if not isinstance(data, list):
        return []

    return [item for item in data if isinstance(item, dict)]


def save_history(history: list[dict[str, Any]]) -> None:
    HISTORY_FILE.write_text(
        json.dumps(history[:MAX_HISTORY_ITEMS], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def add_history(station: dict[str, Any]) -> None:
    if not station.get("url"):
        return

    now = datetime.now(timezone.utc).isoformat()
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
