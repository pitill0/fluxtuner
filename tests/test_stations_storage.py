# SPDX-License-Identifier: MIT

from pathlib import Path

from fluxtuner.core import db, stations


def patch_db_file(tmp_path: Path, monkeypatch) -> Path:
    db_file = tmp_path / "fluxtuner.db"
    monkeypatch.setattr(db, "DB_FILE", db_file)
    return db_file


def test_upsert_station_creates_station(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Test Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
        "country": "Spain",
        "codec": "MP3",
        "bitrate": "128",
        "tags": "test, radio",
    }

    with db.connect() as conn:
        station_id = stations.upsert_station(conn, station)
        loaded = stations.get_station_by_key(
            conn,
            "https://example.com/resolved",
        )

    assert station_id == 1
    assert loaded is not None
    assert loaded["name"] == "Test Radio"
    assert loaded["url"] == "https://example.com/stream"
    assert loaded["url_resolved"] == "https://example.com/resolved"
    assert loaded["country"] == "Spain"
    assert loaded["codec"] == "MP3"
    assert loaded["bitrate"] == 128
    assert loaded["tags"] == "test, radio"


def test_upsert_station_updates_existing_station(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    original = {
        "name": "Original Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
        "country": "Spain",
        "codec": "MP3",
        "bitrate": 128,
    }
    updated = {
        "name": "Updated Radio",
        "url": "https://example.com/stream",
        "url_resolved": "https://example.com/resolved",
        "country": "France",
        "codec": "AAC",
        "bitrate": 192,
    }

    with db.connect() as conn:
        first_id = stations.upsert_station(conn, original)
        second_id = stations.upsert_station(conn, updated)
        loaded = stations.get_station_by_key(
            conn,
            "https://example.com/resolved",
        )

    assert first_id == second_id
    assert loaded is not None
    assert loaded["name"] == "Updated Radio"
    assert loaded["country"] == "France"
    assert loaded["codec"] == "AAC"
    assert loaded["bitrate"] == 192


def test_upsert_station_preserves_extra_metadata(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    station = {
        "name": "Metadata Radio",
        "url": "https://example.com/stream",
        "homepage": "https://example.com",
        "custom_field": "kept",
    }

    with db.connect() as conn:
        stations.upsert_station(conn, station)
        loaded = stations.get_station_by_key(
            conn,
            "https://example.com/stream",
        )

    assert loaded is not None
    assert loaded["custom_field"] == "kept"
    assert loaded["homepage"] == "https://example.com"


def test_upsert_station_rejects_station_without_url(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_db_file(tmp_path, monkeypatch)
    db.init_db()

    with db.connect() as conn:
        try:
            stations.upsert_station(conn, {"name": "No URL Radio"})
        except ValueError as exc:
            assert str(exc) == "Station URL is required."
        else:
            raise AssertionError("Expected ValueError")
