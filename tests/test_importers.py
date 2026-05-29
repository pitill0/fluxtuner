from fluxtuner.core.importers import (
    validate_imported_favorite,
    validate_imported_favorites,
    validate_imported_playlist,
    validate_imported_playlists,
)


def test_validate_imported_favorite_accepts_valid_http_url() -> None:
    favorite = validate_imported_favorite(
        {
            "name": "Test Radio",
            "url": "https://example.com/stream",
            "country": "Spain",
            "codec": "MP3",
            "tags": "rock,pop",
            "favorite_tags": ["Morning", "morning", "Work"],
            "custom_name": "My Radio",
        }
    )

    assert favorite is not None
    assert favorite["name"] == "Test Radio"
    assert favorite["url"] == "https://example.com/stream"
    assert favorite["url_resolved"] == "https://example.com/stream"
    assert favorite["favorite_tags"] == ["Morning", "Work"]


def test_validate_imported_favorite_prefers_url_resolved() -> None:
    favorite = validate_imported_favorite(
        {
            "name": "Resolved Radio",
            "url": "https://example.com/original",
            "url_resolved": "https://example.com/resolved",
        }
    )

    assert favorite is not None
    assert favorite["url"] == "https://example.com/resolved"
    assert favorite["url_resolved"] == "https://example.com/resolved"


def test_validate_imported_favorite_rejects_invalid_url_scheme() -> None:
    assert validate_imported_favorite({"name": "Local", "url": "file:///tmp/test.mp3"}) is None


def test_validate_imported_favorite_rejects_non_dict() -> None:
    assert validate_imported_favorite("not a dict") is None


def test_validate_imported_favorites_returns_valid_items_and_skipped_count() -> None:
    result = validate_imported_favorites(
        [
            {"name": "Valid", "url": "https://example.com/stream"},
            {"name": "Invalid", "url": "file:///tmp/test.mp3"},
            "not a dict",
        ]
    )

    assert len(result.items) == 1
    assert result.skipped == 2


def test_validate_imported_playlist_accepts_valid_urls() -> None:
    playlist = validate_imported_playlist(
        {
            "name": "Morning",
            "station_keys": [
                "https://example.com/one",
                "https://example.com/two",
                "https://example.com/one",
            ],
        }
    )

    assert playlist is not None
    assert playlist["name"] == "Morning"
    assert playlist["station_keys"] == [
        "https://example.com/one",
        "https://example.com/two",
    ]


def test_validate_imported_playlist_rejects_empty_name() -> None:
    assert validate_imported_playlist({"name": " ", "station_keys": ["https://x.test"]}) is None


def test_validate_imported_playlist_rejects_invalid_station_keys() -> None:
    assert (
        validate_imported_playlist(
            {
                "name": "Bad playlist",
                "station_keys": ["file:///tmp/test.mp3", "javascript:alert(1)"],
            }
        )
        is None
    )


def test_validate_imported_playlist_rejects_non_list_station_keys() -> None:
    assert validate_imported_playlist({"name": "Bad", "station_keys": "https://x.test"}) is None


def test_validate_imported_playlists_returns_valid_items_and_skipped_count() -> None:
    result = validate_imported_playlists(
        [
            {"name": "Valid", "station_keys": ["https://example.com/stream"]},
            {"name": "Invalid", "station_keys": ["file:///tmp/test.mp3"]},
            "not a dict",
        ]
    )

    assert len(result.items) == 1
    assert result.skipped == 2
