# SPDX-License-Identifier: MIT

from pathlib import Path

from fluxtuner.core import db, favorites


def patch_db_file(tmp_path: Path, monkeypatch) -> Path:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    return db_file


def test_favorite_record_roundtrip(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
        "custom_name": "My Test Radio",
        "favorite_tags": [" radio ", "test", "radio"],
    }

    with db.connect() as conn:
        added = favorites.add_favorite_record(conn, station)
        loaded = favorites.list_favorites(conn)

    assert added is True
    assert len(loaded) == 1
    assert loaded[0]["name"] == "Test Radio"
    assert loaded[0]["url"] == "https://example.com/stream"
    assert loaded[0]["url_resolved"] == "https://example.com/resolved"
    assert loaded[0]["custom_name"] == "My Test Radio"
    assert loaded[0]["favorite_tags"] == ["radio", "test"]


def test_add_favorite_record_avoids_duplicates(
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
        first_added = favorites.add_favorite_record(conn, station)
        second_added = favorites.add_favorite_record(conn, station)
        loaded = favorites.list_favorites(conn)

    assert first_added is True
    assert second_added is False
    assert len(loaded) == 1


def test_remove_favorite_record_accepts_station_key_or_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
    }

    with db.connect() as conn:
        favorites.add_favorite_record(conn, station)
        removed = favorites.remove_favorite_record(
            conn,
            "https://example.com/resolved",
        )
        loaded = favorites.list_favorites(conn)

    assert removed is True
    assert loaded == []


def test_update_favorite_record_changes_name_and_tags(
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
        favorites.add_favorite_record(conn, station)
        changed = favorites.update_favorite_record(
            conn,
            "https://example.com/stream",
            custom_name="Custom Radio",
            favorite_tags=["news", " morning "],
        )
        loaded = favorites.list_favorites(conn)

    assert changed is True
    assert loaded[0]["custom_name"] == "Custom Radio"
    assert loaded[0]["favorite_tags"] == ["morning", "news"]


def test_replace_favorites_replaces_existing_favorites(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    original = {
        "name": "Original Radio",
        "url": "https://example.com/original",
    }
    replacement = {
        "name": "Replacement Radio",
        "url": "https://example.com/replacement",
    }

    with db.connect() as conn:
        favorites.add_favorite_record(conn, original)
        favorites.replace_favorites(conn, [replacement])
        loaded = favorites.list_favorites(conn)

    assert len(loaded) == 1
    assert loaded[0]["name"] == "Replacement Radio"
    assert loaded[0]["url"] == "https://example.com/replacement"


def test_replace_favorites_ignores_items_without_station_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        favorites.replace_favorites(
            conn,
            [
                {"name": "No URL"},
                {
                    "name": "Valid Radio",
                    "url": "https://example.com/valid",
                },
            ],
        )
        loaded = favorites.list_favorites(conn)

    assert len(loaded) == 1
    assert loaded[0]["name"] == "Valid Radio"


def test_favorite_tags_to_json_normalizes_tags() -> None:
    assert favorites.favorite_tags_to_json([" rock ", "jazz", "rock", ""]) == '["jazz", "rock"]'
