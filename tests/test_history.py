import json
from pathlib import Path

from fluxtuner.core import history


def patch_history_file(tmp_path: Path, monkeypatch) -> Path:
    history_file = tmp_path / "history.json"
    legacy_history_file = tmp_path / "legacy_history.json"

    monkeypatch.setattr(history, "HISTORY_FILE", history_file)
    monkeypatch.setattr(history, "LEGACY_HISTORY_FILE", legacy_history_file)

    return history_file


def test_load_history_returns_empty_list_for_missing_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    assert history.load_history() == []


def test_load_history_ignores_invalid_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    history_file = patch_history_file(tmp_path, monkeypatch)
    history_file.write_text("{not-json", encoding="utf-8")

    assert history.load_history() == []


def test_load_history_ignores_non_list_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    history_file = patch_history_file(tmp_path, monkeypatch)
    history_file.write_text(json.dumps({"name": "Broken"}), encoding="utf-8")

    assert history.load_history() == []


def test_load_history_filters_non_dict_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    history_file = patch_history_file(tmp_path, monkeypatch)
    history_file.write_text(
        json.dumps(
            [
                {"name": "Test Radio", "url": "https://example.com/stream"},
                "invalid",
            ]
        ),
        encoding="utf-8",
    )

    assert history.load_history() == [{"name": "Test Radio", "url": "https://example.com/stream"}]


def test_add_history_adds_station_at_top(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    history.add_history(
        {
            "name": "Test Radio",
            "url": "https://example.com/stream",
        }
    )

    loaded = history.load_history()

    assert len(loaded) == 1
    assert loaded[0]["name"] == "Test Radio"
    assert loaded[0]["url"] == "https://example.com/stream"
    assert loaded[0]["play_count"] == 1
    assert "last_played_at" in loaded[0]


def test_add_history_updates_existing_station_play_count(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    history.add_history(station)
    history.add_history(station)

    loaded = history.load_history()

    assert len(loaded) == 1
    assert loaded[0]["play_count"] == 2


def test_add_history_ignores_station_without_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    history.add_history({"name": "No URL Radio"})

    assert history.load_history() == []


def test_save_history_limits_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    history.save_history(
        [
            {
                "name": f"Radio {index}",
                "url": f"https://example.com/{index}",
            }
            for index in range(history.MAX_HISTORY_ITEMS + 5)
        ]
    )

    assert len(history.load_history()) == history.MAX_HISTORY_ITEMS


def test_clear_history_removes_saved_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    history.add_history(
        {
            "name": "Test Radio",
            "url": "https://example.com/stream",
        }
    )

    history.clear_history()

    assert history.load_history() == []
