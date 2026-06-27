import logging
from pathlib import Path

from fluxtuner.core import favorites


def patch_favorites_file(tmp_path: Path, monkeypatch) -> Path:
    test_file = tmp_path / "favorites.json"
    legacy_file = tmp_path / "legacy_favorites.json"

    monkeypatch.setattr(favorites, "FAVORITES_FILE", test_file)
    monkeypatch.setattr(favorites, "LEGACY_FAVORITES_FILE", legacy_file)

    return test_file


def test_normalize_favorite_adds_expected_fields() -> None:
    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    result = favorites.normalize_favorite(station)

    assert result["custom_name"] is None
    assert result["favorite_tags"] == []
    assert result["url_resolved"] == "https://example.com/stream"


def test_normalize_favorite_normalizes_favorite_tags() -> None:
    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
        "favorite_tags": [" rock ", "jazz", "rock", ""],
    }

    result = favorites.normalize_favorite(station)

    assert result["favorite_tags"] == ["jazz", "rock"]


def test_all_favorite_tags_normalizes_and_deduplicates_tags(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    favorites.save_favorites(
        [
            {
                "name": "Rock Radio",
                "url": "https://example.com/rock",
                "favorite_tags": [" rock ", "jazz", ""],
            },
            {
                "name": "News Radio",
                "url": "https://example.com/news",
                "favorite_tags": ["rock", " news "],
            },
        ]
    )

    assert favorites.all_favorite_tags() == ["jazz", "news", "rock"]


def test_favorite_display_name_prefers_custom_name() -> None:
    station = {
        "name": "Original Name",
        "custom_name": "My Radio",
    }

    assert favorites.favorite_display_name(station) == "My Radio"


def test_favorite_display_name_falls_back_to_station_name() -> None:
    station = {
        "name": "Original Name",
        "custom_name": "",
    }

    assert favorites.favorite_display_name(station) == "Original Name"


def test_load_favorites_returns_empty_list_for_missing_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    assert favorites.load_favorites() == []


def test_load_favorites_ignores_invalid_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    assert favorites.load_favorites() == []


def test_load_favorites_migrates_legacy_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    favorites_file = patch_favorites_file(tmp_path, monkeypatch)
    legacy_file = favorites.LEGACY_FAVORITES_FILE

    legacy_file.write_text(
        """
        [
          {
            "name": "Legacy Radio",
            "url": "https://example.com/legacy"
          }
        ]
        """,
        encoding="utf-8",
    )

    loaded = favorites.load_favorites()

    assert loaded[0]["name"] == "Legacy Radio"
    assert favorites_file.exists()
    assert legacy_file.exists()


def test_load_favorites_does_not_overwrite_existing_file_with_legacy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    favorites_file = patch_favorites_file(tmp_path, monkeypatch)
    legacy_file = favorites.LEGACY_FAVORITES_FILE

    legacy_file.write_text(
        """
        [
          {
            "name": "Legacy Radio",
            "url": "https://example.com/legacy"
          }
        ]
        """,
        encoding="utf-8",
    )
    favorites_file.write_text(
        """
        [
          {
            "name": "Current Radio",
            "url": "https://example.com/current"
          }
        ]
        """,
        encoding="utf-8",
    )

    loaded = favorites.load_favorites()

    assert loaded[0]["name"] == "Current Radio"


def test_save_and_load_favorites_roundtrip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    favorites.save_favorites(
        [
            {
                "name": "Test Radio",
                "url": "https://example.com/stream",
                "favorite_tags": ["test"],
            }
        ]
    )

    loaded = favorites.load_favorites()

    assert len(loaded) == 1
    assert loaded[0]["name"] == "Test Radio"
    assert loaded[0]["url_resolved"] == "https://example.com/stream"


def test_load_favorites_logs_invalid_json(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    favorites_file = tmp_path / "favorites.json"
    favorites_file.write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr(favorites, "FAVORITES_FILE", favorites_file)
    monkeypatch.setattr(favorites, "LEGACY_FAVORITES_FILE", tmp_path / "legacy.json")

    with caplog.at_level(logging.WARNING):
        assert favorites.load_favorites() == []

    assert "Invalid favorites JSON" in caplog.text


def test_add_favorite_avoids_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    assert favorites.add_favorite(station) is True
    assert favorites.add_favorite(station) is False
    assert len(favorites.load_favorites()) == 1


def test_update_favorite_changes_name_and_tags(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    favorites.add_favorite(station)

    changed = favorites.update_favorite(
        "https://example.com/stream",
        custom_name="Custom Radio",
        favorite_tags=["news", " morning "],
    )

    loaded = favorites.load_favorites()

    assert changed is True
    assert loaded[0]["custom_name"] == "Custom Radio"
    assert loaded[0]["favorite_tags"] == ["morning", "news"]


def test_filter_favorites_by_tag_uses_user_favorite_tags_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    favorites.save_favorites(
        [
            {
                "name": "Rock Station",
                "url": "https://example.com/rock",
                "tags": "rock",
                "favorite_tags": ["custom"],
            },
            {
                "name": "News Station",
                "url": "https://example.com/news",
                "tags": "news",
                "favorite_tags": ["morning"],
            },
        ]
    )

    result = favorites.filter_favorites_by_tag("morning")

    assert [item["name"] for item in result] == ["News Station"]


def test_favorites_are_isolated_by_profile_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    default_station = {
        "name": "Default Radio",
        "url": "https://example.com/default",
    }
    work_station = {
        "name": "Work Radio",
        "url": "https://example.com/work",
    }

    assert favorites.add_favorite(default_station) is True
    assert favorites.add_favorite(work_station, profile_name="work") is True

    assert [item["name"] for item in favorites.load_favorites()] == ["Default Radio"]
    assert [item["name"] for item in favorites.load_favorites(profile_name="work")] == [
        "Work Radio"
    ]


def test_save_favorites_replaces_only_requested_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    favorites.save_favorites(
        [
            {
                "name": "Default Radio",
                "url": "https://example.com/default",
            }
        ]
    )
    favorites.save_favorites(
        [
            {
                "name": "Work Radio",
                "url": "https://example.com/work",
            }
        ],
        profile_name="work",
    )

    favorites.save_favorites(
        [
            {
                "name": "Updated Work Radio",
                "url": "https://example.com/updated-work",
            }
        ],
        profile_name="work",
    )

    assert [item["name"] for item in favorites.load_favorites()] == ["Default Radio"]
    assert [item["name"] for item in favorites.load_favorites(profile_name="work")] == [
        "Updated Work Radio"
    ]


def test_update_favorite_updates_only_requested_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    station = {
        "name": "Shared URL Radio",
        "url": "https://example.com/shared",
    }

    favorites.add_favorite(station)
    favorites.add_favorite(station, profile_name="work")

    changed = favorites.update_favorite(
        "https://example.com/shared",
        custom_name="Work Custom",
        profile_name="work",
    )

    assert changed is True
    assert favorites.load_favorites()[0]["custom_name"] is None
    assert favorites.load_favorites(profile_name="work")[0]["custom_name"] == "Work Custom"


def test_remove_favorite_removes_only_requested_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    station = {
        "name": "Shared URL Radio",
        "url": "https://example.com/shared",
    }

    favorites.add_favorite(station)
    favorites.add_favorite(station, profile_name="work")

    removed = favorites.remove_favorite(station, profile_name="work")

    assert removed is True
    assert len(favorites.load_favorites()) == 1
    assert favorites.load_favorites(profile_name="work") == []


def test_favorite_tags_can_be_scoped_by_profile_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_favorites_file(tmp_path, monkeypatch)

    favorites.add_favorite(
        {
            "name": "Home Radio",
            "url": "https://example.com/home",
            "favorite_tags": ["home"],
        }
    )
    favorites.add_favorite(
        {
            "name": "Work Radio",
            "url": "https://example.com/work",
            "favorite_tags": ["office"],
        },
        profile_name="work",
    )

    assert favorites.all_favorite_tags() == ["home"]
    assert favorites.all_favorite_tags(profile_name="work") == ["office"]
    assert [item["name"] for item in favorites.filter_favorites_by_tag("office")] == []
    assert [
        item["name"] for item in favorites.filter_favorites_by_tag("office", profile_name="work")
    ] == ["Work Radio"]
