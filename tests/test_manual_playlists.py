from pathlib import Path

from fluxtuner.core import favorites, manual_playlists


def patch_data_files(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    favorites_file = tmp_path / "favorites.json"
    playlists_file = tmp_path / "playlists.json"

    monkeypatch.setattr(favorites, "FAVORITES_FILE", favorites_file)
    monkeypatch.setattr(manual_playlists, "PLAYLISTS_FILE", playlists_file)

    return favorites_file, playlists_file


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
