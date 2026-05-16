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
    test_file = patch_favorites_file(tmp_path, monkeypatch)

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
    test_file = patch_favorites_file(tmp_path, monkeypatch)

    assert favorites.load_favorites() == []


def test_load_favorites_ignores_invalid_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_file = patch_favorites_file(tmp_path, monkeypatch)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", test_file)

    assert favorites.load_favorites() == []


def test_save_and_load_favorites_roundtrip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_file = patch_favorites_file(tmp_path, monkeypatch)

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


def test_add_favorite_avoids_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    test_file = patch_favorites_file(tmp_path, monkeypatch)

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
    test_file = patch_favorites_file(tmp_path, monkeypatch)

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
    test_file = patch_favorites_file(tmp_path, monkeypatch)

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
