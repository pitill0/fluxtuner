from pathlib import Path

from fluxtuner.core import favorites, manual_playlists


def patch_data_files(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    favorites_file = tmp_path / "favorites.json"
    legacy_favorites_file = tmp_path / "legacy_favorites.json"
    playlists_file = tmp_path / "playlists.json"
    legacy_playlists_file = tmp_path / "legacy_playlists.json"

    monkeypatch.setattr(favorites, "FAVORITES_FILE", favorites_file)
    monkeypatch.setattr(favorites, "LEGACY_FAVORITES_FILE", legacy_favorites_file)
    monkeypatch.setattr(manual_playlists, "PLAYLISTS_FILE", playlists_file)
    monkeypatch.setattr(
        manual_playlists,
        "LEGACY_PLAYLISTS_FILE",
        legacy_playlists_file,
    )

    return favorites_file, playlists_file


def patch_playlists_file(
    tmp_path: Path,
    monkeypatch,
) -> Path:
    playlists_file = tmp_path / "playlists.json"
    legacy_playlists_file = tmp_path / "legacy_playlists.json"

    monkeypatch.setattr(manual_playlists, "PLAYLISTS_FILE", playlists_file)
    monkeypatch.setattr(
        manual_playlists,
        "LEGACY_PLAYLISTS_FILE",
        legacy_playlists_file,
    )

    return playlists_file


def test_normalize_playlist_removes_duplicate_station_keys() -> None:
    playlist = {
        "name": "My Playlist",
        "station_keys": [
            "https://example.com/a",
            "https://example.com/a",
            " https://example.com/b ",
            "",
        ],
    }

    result = manual_playlists.normalize_playlist(playlist)

    assert result == {
        "name": "My Playlist",
        "station_keys": [
            "https://example.com/a",
            "https://example.com/b",
        ],
    }


def test_normalize_playlist_ignores_invalid_station_keys_value() -> None:
    playlist = {
        "name": "Broken Playlist",
        "station_keys": "https://example.com/a",
    }

    result = manual_playlists.normalize_playlist(playlist)

    assert result == {
        "name": "Broken Playlist",
        "station_keys": [],
    }


def test_create_playlist(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_data_files(tmp_path, monkeypatch)

    assert manual_playlists.create_playlist("Morning") is True
    assert manual_playlists.create_playlist("morning") is False

    playlists = manual_playlists.load_playlists()

    assert len(playlists) == 1
    assert playlists[0]["name"] == "Morning"


def test_add_station_to_playlist_creates_playlist_if_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_data_files(tmp_path, monkeypatch)

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    assert manual_playlists.add_station_to_playlist("Morning", station) is True

    playlist = manual_playlists.get_playlist("morning")

    assert playlist is not None
    assert playlist["station_keys"] == ["https://example.com/stream"]


def test_add_station_to_playlist_avoids_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_data_files(tmp_path, monkeypatch)

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    assert manual_playlists.add_station_to_playlist("Morning", station) is True
    assert manual_playlists.add_station_to_playlist("Morning", station) is False


def test_get_playlist_stations_resolves_against_favorites(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_data_files(tmp_path, monkeypatch)

    favorites.save_favorites(
        [
            {
                "name": "Test Radio",
                "url": "https://example.com/stream",
            }
        ]
    )

    manual_playlists.create_playlist("Morning")
    manual_playlists.add_station_to_playlist(
        "Morning",
        {
            "name": "Test Radio",
            "url": "https://example.com/stream",
        },
    )

    stations = manual_playlists.get_playlist_stations("Morning")

    assert len(stations) == 1
    assert stations[0]["name"] == "Test Radio"


def test_remove_station_from_playlist(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_data_files(tmp_path, monkeypatch)

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    manual_playlists.add_station_to_playlist("Morning", station)

    assert manual_playlists.remove_station_from_playlist("Morning", station) is True
    assert manual_playlists.get_playlist_stations("Morning") == []


def test_playlist_counts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_data_files(tmp_path, monkeypatch)

    favorites.save_favorites(
        [
            {
                "name": "Test Radio",
                "url": "https://example.com/stream",
            }
        ]
    )

    manual_playlists.add_station_to_playlist(
        "Morning",
        {
            "name": "Test Radio",
            "url": "https://example.com/stream",
        },
    )

    assert manual_playlists.playlist_counts() == [("Morning", 1)]


def test_load_playlists_migrates_legacy_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _favorites_file, playlists_file = patch_data_files(tmp_path, monkeypatch)
    legacy_playlists_file = manual_playlists.LEGACY_PLAYLISTS_FILE

    legacy_playlists_file.write_text(
        """
        [
          {
            "name": "Legacy Playlist",
            "station_keys": ["https://example.com/legacy"]
          }
        ]
        """,
        encoding="utf-8",
    )

    loaded = manual_playlists.load_playlists()

    assert loaded == [
        {
            "name": "Legacy Playlist",
            "station_keys": ["https://example.com/legacy"],
        }
    ]
    assert playlists_file.exists()
    assert legacy_playlists_file.exists()


def test_load_playlists_does_not_overwrite_existing_file_with_legacy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _favorites_file, playlists_file = patch_data_files(tmp_path, monkeypatch)
    legacy_playlists_file = manual_playlists.LEGACY_PLAYLISTS_FILE

    legacy_playlists_file.write_text(
        """
        [
          {
            "name": "Legacy Playlist",
            "station_keys": ["https://example.com/legacy"]
          }
        ]
        """,
        encoding="utf-8",
    )
    playlists_file.write_text(
        """
        [
          {
            "name": "Current Playlist",
            "station_keys": ["https://example.com/current"]
          }
        ]
        """,
        encoding="utf-8",
    )

    loaded = manual_playlists.load_playlists()

    assert loaded == [
        {
            "name": "Current Playlist",
            "station_keys": ["https://example.com/current"],
        }
    ]


def test_playlists_are_isolated_by_profile_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    playlists_file = patch_playlists_file(tmp_path, monkeypatch)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", playlists_file.with_name("favorites.json"))

    default_station = {
        "name": "Default Radio",
        "url": "https://example.com/default",
    }
    work_station = {
        "name": "Work Radio",
        "url": "https://example.com/work",
    }

    favorites.add_favorite(default_station)
    favorites.add_favorite(work_station, profile_name="work")

    manual_playlists.add_station_to_playlist("Morning", default_station)
    manual_playlists.add_station_to_playlist("Morning", work_station, profile_name="work")

    assert manual_playlists.load_playlists() == [
        {
            "name": "Morning",
            "station_keys": ["https://example.com/default"],
        }
    ]
    assert manual_playlists.load_playlists(profile_name="work") == [
        {
            "name": "Morning",
            "station_keys": ["https://example.com/work"],
        }
    ]


def test_get_playlist_stations_uses_matching_profile_favorites(
    tmp_path: Path,
    monkeypatch,
) -> None:
    playlists_file = patch_playlists_file(tmp_path, monkeypatch)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", playlists_file.with_name("favorites.json"))

    default_station = {
        "name": "Default Radio",
        "url": "https://example.com/default",
    }
    work_station = {
        "name": "Work Radio",
        "url": "https://example.com/work",
        "custom_name": "Work Custom",
    }

    favorites.add_favorite(default_station)
    favorites.add_favorite(work_station, profile_name="work")

    manual_playlists.add_station_to_playlist("Shared", default_station)
    manual_playlists.add_station_to_playlist("Shared", work_station, profile_name="work")

    assert [item["name"] for item in manual_playlists.get_playlist_stations("Shared")] == [
        "Default Radio"
    ]
    assert [
        item.get("custom_name")
        for item in manual_playlists.get_playlist_stations("Shared", profile_name="work")
    ] == ["Work Custom"]


def test_save_playlists_replaces_only_requested_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    playlists_file = patch_playlists_file(tmp_path, monkeypatch)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", playlists_file.with_name("favorites.json"))

    manual_playlists.save_playlists(
        [
            {
                "name": "Default",
                "station_keys": ["https://example.com/default"],
            }
        ]
    )
    manual_playlists.save_playlists(
        [
            {
                "name": "Work",
                "station_keys": ["https://example.com/work"],
            }
        ],
        profile_name="work",
    )

    manual_playlists.save_playlists(
        [
            {
                "name": "Updated Work",
                "station_keys": ["https://example.com/updated-work"],
            }
        ],
        profile_name="work",
    )

    assert manual_playlists.load_playlists() == [
        {
            "name": "Default",
            "station_keys": ["https://example.com/default"],
        }
    ]
    assert manual_playlists.load_playlists(profile_name="work") == [
        {
            "name": "Updated Work",
            "station_keys": ["https://example.com/updated-work"],
        }
    ]


def test_delete_playlist_deletes_only_requested_profile(
    tmp_path: Path,
    monkeypatch,
) -> None:
    playlists_file = patch_playlists_file(tmp_path, monkeypatch)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", playlists_file.with_name("favorites.json"))

    assert manual_playlists.create_playlist("Shared") is True
    assert manual_playlists.create_playlist("Shared", profile_name="work") is True

    assert manual_playlists.delete_playlist("Shared", profile_name="work") is True

    assert manual_playlists.get_playlist("Shared") == {
        "name": "Shared",
        "station_keys": [],
    }
    assert manual_playlists.get_playlist("Shared", profile_name="work") is None


def test_playlist_counts_and_summary_are_scoped_by_profile_name(
    tmp_path: Path,
    monkeypatch,
) -> None:
    playlists_file = patch_playlists_file(tmp_path, monkeypatch)
    monkeypatch.setattr(favorites, "FAVORITES_FILE", playlists_file.with_name("favorites.json"))

    default_station = {
        "name": "Default Radio",
        "url": "https://example.com/default",
    }
    work_station = {
        "name": "Work Radio",
        "url": "https://example.com/work",
    }

    favorites.add_favorite(default_station)
    favorites.add_favorite(work_station, profile_name="work")

    manual_playlists.add_station_to_playlist("Morning", default_station)
    manual_playlists.add_station_to_playlist("Morning", work_station, profile_name="work")

    assert manual_playlists.playlist_counts() == [("Morning", 1)]
    assert manual_playlists.playlist_counts(profile_name="work") == [("Morning", 1)]

    assert manual_playlists.summarize_playlist("Morning") == "• Default Radio"
    assert manual_playlists.summarize_playlist("Morning", profile_name="work") == ("• Work Radio")
