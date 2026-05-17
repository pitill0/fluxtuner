import json
from pathlib import Path

from fluxtuner.core import data_usage


def patch_usage_file(tmp_path: Path, monkeypatch) -> Path:
    usage_file = tmp_path / "usage.json"
    legacy_usage_file = tmp_path / "legacy_usage.json"

    monkeypatch.setattr(data_usage, "USAGE_FILE", usage_file)
    monkeypatch.setattr(data_usage, "LEGACY_USAGE_FILE", legacy_usage_file)

    return usage_file


def test_estimate_mb_handles_invalid_values() -> None:
    assert data_usage.estimate_mb(None, 3600) == 0.0
    assert data_usage.estimate_mb(0, 3600) == 0.0
    assert data_usage.estimate_mb(128, 0) == 0.0
    assert data_usage.estimate_mb(128, -1) == 0.0


def test_estimate_mb_calculates_megabytes() -> None:
    assert data_usage.estimate_mb(128, 3600) == 57.6
    assert data_usage.estimate_mb_per_hour(128) == 57.6


def test_load_raw_returns_empty_structure_for_missing_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_usage_file(tmp_path, monkeypatch)

    assert data_usage._load_raw() == {"days": {}, "months": {}}


def test_load_raw_ignores_invalid_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    usage_file = patch_usage_file(tmp_path, monkeypatch)
    usage_file.write_text("{not-json", encoding="utf-8")

    assert data_usage._load_raw() == {"days": {}, "months": {}}


def test_save_raw_creates_parent_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    usage_file = tmp_path / "nested" / "usage.json"
    monkeypatch.setattr(data_usage, "USAGE_FILE", usage_file)
    monkeypatch.setattr(data_usage, "LEGACY_USAGE_FILE", tmp_path / "legacy_usage.json")

    data_usage._save_raw({"days": {}, "months": {}})

    assert usage_file.exists()


def test_tracker_parses_invalid_bitrate_as_zero() -> None:
    assert data_usage.DataUsageTracker._parse_bitrate({"bitrate": "nope"}) == 0
    assert data_usage.DataUsageTracker._parse_bitrate({}) == 0
    assert data_usage.DataUsageTracker._parse_bitrate(None) == 0


def test_tracker_stop_persists_usage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    usage_file = patch_usage_file(tmp_path, monkeypatch)
    tracker = data_usage.DataUsageTracker()

    times = iter([100.0, 110.0])
    monkeypatch.setattr(data_usage.time, "monotonic", lambda: next(times))

    tracker.start({"name": "Test Radio", "bitrate": 128})
    tracker.stop()

    saved = json.loads(usage_file.read_text(encoding="utf-8"))
    day = saved["days"][data_usage._today_key()]
    month = saved["months"][data_usage._month_key()]

    assert day["mb"] == 0.16
    assert day["seconds"] == 10.0
    assert month["mb"] == 0.16
    assert month["seconds"] == 10.0


def test_format_mb_uses_gb_for_large_values() -> None:
    assert data_usage.format_mb(10.0) == "10.0 MB"
    assert data_usage.format_mb(2048.0) == "2.00 GB"


def test_format_usage_line() -> None:
    assert (
        data_usage.format_usage_line(
            {
                "session_mb": 1.5,
                "today_mb": 2.5,
                "mb_per_hour": 57.6,
            }
        )
        == "Data: 1.5 MB session · 2.5 MB today · 57.6 MB/h est."
    )
