# SPDX-License-Identifier: MIT

import json
from pathlib import Path

from fluxtuner.core import db, history


def patch_history_file(tmp_path: Path, monkeypatch) -> Path:
    history_file = tmp_path / "history.json"
    legacy_history_file = tmp_path / "legacy_history.json"

    monkeypatch.setattr(history, "HISTORY_FILE", history_file)
    monkeypatch.setattr(history, "LEGACY_HISTORY_FILE", legacy_history_file)

    return history_file


def test_load_history_migrates_legacy_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    history_file = patch_history_file(tmp_path, monkeypatch)
    legacy_history_file = history.LEGACY_HISTORY_FILE

    legacy_history_file.write_text(
        json.dumps(
            [
                {
                    "name": "Legacy Radio",
                    "url": "https://example.com/legacy",
                }
            ]
        ),
        encoding="utf-8",
    )

    loaded = history.load_history()

    assert loaded == [
        {
            "name": "Legacy Radio",
            "url": "https://example.com/legacy",
        }
    ]
    assert history_file.exists()
    assert legacy_history_file.exists()


def test_load_history_does_not_overwrite_existing_file_with_legacy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    history_file = patch_history_file(tmp_path, monkeypatch)
    legacy_history_file = history.LEGACY_HISTORY_FILE

    legacy_history_file.write_text(
        json.dumps(
            [
                {
                    "name": "Legacy Radio",
                    "url": "https://example.com/legacy",
                }
            ]
        ),
        encoding="utf-8",
    )
    history_file.write_text(
        json.dumps(
            [
                {
                    "name": "Current Radio",
                    "url": "https://example.com/current",
                }
            ]
        ),
        encoding="utf-8",
    )

    loaded = history.load_history()

    assert loaded == [
        {
            "name": "Current Radio",
            "url": "https://example.com/current",
        }
    ]


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


def test_history_is_isolated_by_profile_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    default_station = {
        "name": "Default Radio",
        "url": "https://example.com/default",
    }
    work_station = {
        "name": "Work Radio",
        "url": "https://example.com/work",
    }

    history.add_history(default_station)
    history.add_history(work_station, profile_name="work")

    assert [item["name"] for item in history.load_history()] == ["Default Radio"]
    assert [item["name"] for item in history.load_history(profile_name="work")] == ["Work Radio"]


def test_history_play_count_is_scoped_by_profile_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    station = {
        "name": "Shared Radio",
        "url": "https://example.com/shared",
    }

    history.add_history(station)
    history.add_history(station, profile_name="work")
    history.add_history(station, profile_name="work")

    assert history.load_history()[0]["play_count"] == 1
    assert history.load_history(profile_name="work")[0]["play_count"] == 2


def test_save_history_replaces_only_requested_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    history.save_history(
        [
            {
                "name": "Default Radio",
                "url": "https://example.com/default",
                "last_played_at": "2026-01-01T10:00:00+00:00",
                "play_count": 1,
            }
        ]
    )
    history.save_history(
        [
            {
                "name": "Work Radio",
                "url": "https://example.com/work",
                "last_played_at": "2026-01-01T11:00:00+00:00",
                "play_count": 1,
            }
        ],
        profile_name="work",
    )

    history.save_history(
        [
            {
                "name": "Updated Work Radio",
                "url": "https://example.com/updated-work",
                "last_played_at": "2026-01-01T12:00:00+00:00",
                "play_count": 3,
            }
        ],
        profile_name="work",
    )

    assert [item["name"] for item in history.load_history()] == ["Default Radio"]
    assert [item["name"] for item in history.load_history(profile_name="work")] == [
        "Updated Work Radio"
    ]


def test_clear_history_clears_only_requested_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    default_station = {
        "name": "Default Radio",
        "url": "https://example.com/default",
    }
    work_station = {
        "name": "Work Radio",
        "url": "https://example.com/work",
    }

    history.add_history(default_station)
    history.add_history(work_station, profile_name="work")

    history.clear_history(profile_name="work")

    assert [item["name"] for item in history.load_history()] == ["Default Radio"]
    assert history.load_history(profile_name="work") == []


def test_history_is_isolated_by_user_id(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_history_file(tmp_path, monkeypatch)

    db.init_db(history._db_path())

    with db.connect(history._db_path()) as conn:
        laura_id = db.get_or_create_user(conn, "laura")
        guest_id = db.get_or_create_user(conn, "guest")
        conn.commit()

    history.add_history(
        {
            "name": "Laura Radio",
            "url": "https://example.com/laura",
        },
        user_id=laura_id,
    )

    assert [item["name"] for item in history.load_history(user_id=laura_id)] == ["Laura Radio"]
    assert history.load_history(user_id=guest_id) == []

    history.clear_history(user_id=guest_id)
    assert [item["name"] for item in history.load_history(user_id=laura_id)] == ["Laura Radio"]

    history.clear_history(user_id=laura_id)
    assert history.load_history(user_id=laura_id) == []
