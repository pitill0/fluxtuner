# SPDX-License-Identifier: MIT

from pathlib import Path

from fluxtuner.core import db, playlists


def patch_db_file(tmp_path: Path, monkeypatch) -> Path:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    return db_file


def test_create_playlist_record_avoids_case_insensitive_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        created = playlists.create_playlist_record(conn, "Morning")
        duplicated = playlists.create_playlist_record(conn, "morning")
        loaded = playlists.list_playlists(conn)

    assert created is True
    assert duplicated is False
    assert loaded == [{"name": "Morning", "station_keys": []}]


def test_add_station_to_playlist_record_creates_playlist_if_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    with db.connect() as conn:
        added = playlists.add_station_to_playlist_record(
            conn,
            "Morning",
            station,
        )
        loaded = playlists.get_playlist_record(conn, "morning")

    assert added is True
    assert loaded == {
        "name": "Morning",
        "station_keys": ["https://example.com/stream"],
    }


def test_add_station_to_playlist_record_avoids_duplicates(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    with db.connect() as conn:
        first_added = playlists.add_station_to_playlist_record(
            conn,
            "Morning",
            station,
        )
        second_added = playlists.add_station_to_playlist_record(
            conn,
            "Morning",
            station,
        )
        loaded = playlists.get_playlist_record(conn, "Morning")

    assert first_added is True
    assert second_added is False
    assert loaded == {
        "name": "Morning",
        "station_keys": ["https://example.com/stream"],
    }


def test_remove_station_from_playlist_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
    }

    with db.connect() as conn:
        playlists.add_station_to_playlist_record(conn, "Morning", station)
        removed = playlists.remove_station_from_playlist_record(
            conn,
            "Morning",
            station,
        )
        loaded = playlists.get_playlist_record(conn, "Morning")

    assert removed is True
    assert loaded == {"name": "Morning", "station_keys": []}


def test_delete_playlist_record(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        playlists.create_playlist_record(conn, "Morning")
        deleted = playlists.delete_playlist_record(conn, "morning")
        loaded = playlists.list_playlists(conn)

    assert deleted is True
    assert loaded == []


def test_replace_playlists_replaces_existing_playlists(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        playlists.create_playlist_record(conn, "Old")
        playlists.replace_playlists(
            conn,
            [
                {
                    "name": "Morning",
                    "station_keys": [
                        "https://example.com/a",
                        "https://example.com/b",
                    ],
                }
            ],
        )
        loaded = playlists.list_playlists(conn)

    assert loaded == [
        {
            "name": "Morning",
            "station_keys": [
                "https://example.com/a",
                "https://example.com/b",
            ],
        }
    ]


def test_replace_playlists_ignores_invalid_items(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        playlists.replace_playlists(
            conn,
            [
                {"name": ""},
                {
                    "name": "Valid",
                    "station_keys": "https://example.com/not-a-list",
                },
                {
                    "name": "Also Valid",
                    "station_keys": [
                        "",
                        "https://example.com/valid",
                    ],
                },
            ],
        )
        loaded = playlists.list_playlists(conn)

    assert loaded == [
        {"name": "Valid", "station_keys": []},
        {"name": "Also Valid", "station_keys": ["https://example.com/valid"]},
    ]


def test_playlist_station_order_is_preserved(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        playlists.add_station_to_playlist_record(
            conn,
            "Morning",
            {"name": "A", "url": "https://example.com/a"},
        )
        playlists.add_station_to_playlist_record(
            conn,
            "Morning",
            {"name": "B", "url": "https://example.com/b"},
        )
        loaded = playlists.get_playlist_record(conn, "Morning")

    assert loaded == {
        "name": "Morning",
        "station_keys": [
            "https://example.com/a",
            "https://example.com/b",
        ],
    }
