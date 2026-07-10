# SPDX-License-Identifier: MIT

from pathlib import Path

from fluxtuner.core import db, favorites, history, playlists, stations


def patch_db_file(tmp_path: Path, monkeypatch) -> Path:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    return db_file


def test_station_domain_and_db_wrapper_share_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Boundary Radio",
        "url": "https://example.com/boundary",
        "url_resolved": "https://stream.example.com/boundary",
    }

    with db.connect() as conn:
        station_id = stations.upsert_station(conn, station)
        loaded_through_wrapper = db.get_station_by_key(
            conn,
            "https://stream.example.com/boundary",
        )

    assert station_id == 1
    assert loaded_through_wrapper is not None
    assert loaded_through_wrapper["name"] == "Boundary Radio"


def test_favorites_domain_and_db_wrapper_share_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Favorite Boundary Radio",
        "url": "https://example.com/favorite-boundary",
        "custom_name": "My Boundary Radio",
        "favorite_tags": [" boundary ", "test", "boundary"],
    }

    with db.connect() as conn:
        added = favorites.add_favorite_record(conn, station)
        loaded_through_wrapper = db.list_favorites(conn)

    assert added is True
    assert len(loaded_through_wrapper) == 1
    assert loaded_through_wrapper[0]["custom_name"] == "My Boundary Radio"
    assert loaded_through_wrapper[0]["favorite_tags"] == ["boundary", "test"]


def test_history_wrapper_and_domain_module_share_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "History Boundary Radio",
        "url": "https://example.com/history-boundary",
    }

    with db.connect() as conn:
        db.add_history_record(
            conn,
            station,
            played_at="2026-07-10T08:00:00+00:00",
        )
        loaded_through_domain = history.list_history(conn)

    assert len(loaded_through_domain) == 1
    assert loaded_through_domain[0]["name"] == "History Boundary Radio"
    assert loaded_through_domain[0]["play_count"] == 1


def test_playlists_domain_and_db_wrapper_share_storage(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Playlist Boundary Radio",
        "url": "https://example.com/playlist-boundary",
    }

    with db.connect() as conn:
        added = playlists.add_station_to_playlist_record(
            conn,
            "Boundary",
            station,
        )
        loaded_through_wrapper = db.get_playlist_record(conn, "boundary")

    assert added is True
    assert loaded_through_wrapper == {
        "name": "Boundary",
        "station_keys": ["https://example.com/playlist-boundary"],
    }
