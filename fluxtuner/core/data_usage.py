from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fluxtuner.paths import data_file, migrate_legacy_file

LEGACY_USAGE_FILE = Path.home() / ".fluxtuner_usage.json"
USAGE_FILE = data_file("usage.json")


def _today_key() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _month_key() -> str:
    return datetime.now().strftime("%Y-%m")


def _load_raw() -> dict[str, Any]:
    migrate_legacy_file(LEGACY_USAGE_FILE, USAGE_FILE)

    if not USAGE_FILE.exists():
        return {"days": {}, "months": {}}

    try:
        return json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"days": {}, "months": {}}


def _save_raw(data: dict[str, Any]) -> None:
    migrate_legacy_file(LEGACY_USAGE_FILE, USAGE_FILE)
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def estimate_mb(bitrate_kbps: int | float | None, seconds: int | float) -> float:
    if not bitrate_kbps or bitrate_kbps <= 0 or seconds <= 0:
        return 0.0
    return float(bitrate_kbps) * float(seconds) / 8.0 / 1000.0


def estimate_mb_per_hour(bitrate_kbps: int | float | None) -> float:
    return estimate_mb(bitrate_kbps, 3600)


class DataUsageTracker:
    def __init__(self) -> None:
        self._current_station: dict[str, Any] | None = None
        self._current_bitrate: int = 0
        self._started_at: float | None = None
        self._session_mb: float = 0.0
        self._session_seconds: float = 0.0

    @property
    def current_station(self) -> dict[str, Any] | None:
        return self._current_station

    @property
    def current_bitrate(self) -> int:
        return self._current_bitrate

    def start(self, station: dict[str, Any] | None) -> None:
        self.stop()
        self._current_station = station or {}
        self._current_bitrate = self._parse_bitrate(self._current_station)
        self._started_at = time.monotonic()

    def pause(self) -> None:
        self._flush_current_interval()
        self._started_at = None

    def resume(self) -> None:
        if self._current_station is not None and self._started_at is None:
            self._started_at = time.monotonic()

    def stop(self) -> None:
        self._flush_current_interval()
        self._current_station = None
        self._current_bitrate = 0
        self._started_at = None

    def snapshot(self) -> dict[str, Any]:
        current_extra_mb = 0.0
        current_extra_seconds = 0.0

        if self._started_at is not None:
            current_extra_seconds = time.monotonic() - self._started_at
            current_extra_mb = estimate_mb(self._current_bitrate, current_extra_seconds)

        persisted = _load_raw()
        today = persisted.get("days", {}).get(_today_key(), {})
        month = persisted.get("months", {}).get(_month_key(), {})

        session_mb = self._session_mb + current_extra_mb
        session_seconds = self._session_seconds + current_extra_seconds

        return {
            "session_mb": session_mb,
            "session_seconds": session_seconds,
            "today_mb": float(today.get("mb", 0.0)) + current_extra_mb,
            "month_mb": float(month.get("mb", 0.0)) + current_extra_mb,
            "mb_per_hour": estimate_mb_per_hour(self._current_bitrate),
            "bitrate_kbps": self._current_bitrate,
        }

    def reset_session(self) -> None:
        self._session_mb = 0.0
        self._session_seconds = 0.0

    def _flush_current_interval(self) -> None:
        if self._started_at is None:
            return

        elapsed = time.monotonic() - self._started_at
        mb = estimate_mb(self._current_bitrate, elapsed)

        self._session_seconds += elapsed
        self._session_mb += mb

        if mb > 0:
            self._persist(mb, elapsed)

        self._started_at = None

    def _persist(self, mb: float, seconds: float) -> None:
        data = _load_raw()
        data.setdefault("days", {})
        data.setdefault("months", {})

        day_key = _today_key()
        month_key = _month_key()

        day = data["days"].setdefault(day_key, {"mb": 0.0, "seconds": 0.0})
        month = data["months"].setdefault(month_key, {"mb": 0.0, "seconds": 0.0})

        day["mb"] = float(day.get("mb", 0.0)) + mb
        day["seconds"] = float(day.get("seconds", 0.0)) + seconds

        month["mb"] = float(month.get("mb", 0.0)) + mb
        month["seconds"] = float(month.get("seconds", 0.0)) + seconds

        _save_raw(data)

    @staticmethod
    def _parse_bitrate(station: dict[str, Any] | None) -> int:
        if not station:
            return 0

        value = station.get("bitrate", 0)

        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0


def format_mb(value: float) -> str:
    if value >= 1024:
        return f"{value / 1024:.2f} GB"
    return f"{value:.1f} MB"


def format_usage_line(snapshot: dict[str, Any]) -> str:
    return (
        f"Data: {format_mb(snapshot['session_mb'])} session · "
        f"{format_mb(snapshot['today_mb'])} today · "
        f"{format_mb(snapshot['mb_per_hour'])}/h est."
    )
