from __future__ import annotations

import pytest

from fluxtuner.core import custom_stations, db, favorites, profiles, stations


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "fluxtuner.db"
    db.init_db(path)
    conn = db.connect(path)
    first = profiles.get_or_create_profile(conn, "first")
    second = profiles.get_or_create_profile(conn, "second")
    conn.commit()
    try:
        yield conn, first, second
    finally:
        conn.close()


def test_manual_station_uses_normal_library_model(library):
    conn, first, second = library
    url = "https://radio.example/live?channel=jazz&quality=high"

    added = custom_stations.add_custom_station(
        conn, profile_id=first, name="  Mi radio  ", url=f"  {url}  "
    )

    assert added is True
    saved = favorites.list_favorites(conn, first)
    assert len(saved) == 1
    assert favorites.favorite_display_name(saved[0]) == "Mi radio"
    assert stations.station_key(saved[0]) == url
    assert saved[0]["url"] == url
    assert saved[0]["url_resolved"] == url
    assert not saved[0].get("stationuuid")
    assert favorites.list_favorites(conn, second) == []


def test_duplicate_keeps_personalization_and_station_data(library):
    conn, first, _ = library
    url = "https://radio.example/live"
    original = {
        "name": "Directory name",
        "url": url,
        "stationuuid": "existing-directory-id",
        "country": "Spain",
        "codec": "MP3",
        "bitrate": 128,
        "tags": "jazz",
        "custom_name": "Mi nombre",
        "favorite_tags": ["Personal"],
    }
    favorites.add_favorite_record(conn, original, first)
    before = dict(conn.execute("SELECT * FROM stations").fetchone())

    added = custom_stations.add_custom_station(conn, profile_id=first, name="Replacement", url=url)

    assert added is False
    assert dict(conn.execute("SELECT * FROM stations").fetchone()) == before
    saved = favorites.list_favorites(conn, first)
    assert len(saved) == 1
    assert saved[0]["custom_name"] == "Mi nombre"
    assert saved[0]["favorite_tags"] == ["Personal"]


def test_same_url_can_have_different_names_in_each_profile(library):
    conn, first, second = library
    url = "https://radio.example/live"
    custom_stations.add_custom_station(conn, profile_id=first, name="Radio de casa", url=url)
    before = dict(conn.execute("SELECT * FROM stations").fetchone())

    assert (
        custom_stations.add_custom_station(
            conn, profile_id=second, name="Radio del trabajo", url=url
        )
        is True
    )

    assert dict(conn.execute("SELECT * FROM stations").fetchone()) == before
    assert (
        favorites.favorite_display_name(favorites.list_favorites(conn, first)[0]) == "Radio de casa"
    )
    assert (
        favorites.favorite_display_name(favorites.list_favorites(conn, second)[0])
        == "Radio del trabajo"
    )
    assert conn.execute("SELECT count(*) FROM stations").fetchone()[0] == 1


@pytest.mark.parametrize(
    "url",
    [
        "http://192.168.1.20:8000/live",
        "http://localhost:8000/live",
        "https://radio.example/live.m3u8?token=AbC%2F123",
        "https://radio.example/live?a=1&a=2",
    ],
)
def test_valid_urls_are_preserved_without_network_access(library, monkeypatch, url):
    import socket

    def unexpected_network(*args, **kwargs):
        pytest.fail("Saving a station must not resolve or contact the stream")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    monkeypatch.setattr(socket, "create_connection", unexpected_network)
    conn, first, _ = library

    assert (
        custom_stations.add_custom_station(conn, profile_id=first, name="Personal radio", url=url)
        is True
    )
    assert stations.station_key(favorites.list_favorites(conn, first)[0]) == url


@pytest.mark.parametrize(
    "url",
    [
        "",
        "radio.example/live",
        "file:///tmp/audio.mp3",
        "javascript:alert(1)",
        "https://",
        "https://radio.example:invalid/live",
        "https://radio.example:70000/live",
        "https://user:password@radio.example/live",
        "https://radio.example/li\nve",
        "https://radio.example/li\x00ve",
        "https://radio.example/live stream",
        "https://[broken/live",
        "https://radio.example/" + "x" * 2048,
    ],
)
def test_invalid_url_does_not_write_library(library, url):
    conn, first, _ = library
    with pytest.raises(ValueError):
        custom_stations.add_custom_station(conn, profile_id=first, name="Radio", url=url)
    assert conn.execute("SELECT count(*) FROM stations").fetchone()[0] == 0
    assert favorites.list_favorites(conn, first) == []


@pytest.mark.parametrize("name", ["", "   ", "x" * 201, "Radio\x00name", "Radio\nname"])
def test_invalid_name_does_not_write_library(library, name):
    conn, first, _ = library
    with pytest.raises(ValueError):
        custom_stations.add_custom_station(
            conn, profile_id=first, name=name, url="https://radio.example/live"
        )
    assert conn.execute("SELECT count(*) FROM stations").fetchone()[0] == 0


@pytest.mark.parametrize("profile_id", [0, -1, 999999, None, True])
def test_missing_profile_cannot_fall_back_to_default(library, profile_id):
    conn, _, _ = library
    with pytest.raises(ValueError):
        custom_stations.add_custom_station(
            conn,
            profile_id=profile_id,
            name="Radio",
            url="https://radio.example/live",
        )
    assert conn.execute("SELECT count(*) FROM stations").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM favorites").fetchone()[0] == 0


def test_manual_add_preserves_directory_metadata_for_other_profile(library):
    conn, first, second = library
    url = "https://radio.example/live"
    favorites.add_favorite_record(
        conn,
        {
            "name": "Directory radio",
            "url": url,
            "stationuuid": "directory-id",
            "codec": "AAC",
            "bitrate": 192,
            "country": "Spain",
            "custom_name": "First profile name",
            "favorite_tags": ["Keep"],
        },
        first,
    )
    before_station = dict(conn.execute("SELECT * FROM stations").fetchone())
    before_favorite = favorites.list_favorites(conn, first)

    assert (
        custom_stations.add_custom_station(
            conn, profile_id=second, name="Second profile name", url=url
        )
        is True
    )

    assert dict(conn.execute("SELECT * FROM stations").fetchone()) == before_station
    assert favorites.list_favorites(conn, first) == before_favorite
    saved = favorites.list_favorites(conn, second)[0]
    assert saved["stationuuid"] == "directory-id"
    assert saved["codec"] == "AAC"
    assert favorites.favorite_display_name(saved) == "Second profile name"


def test_caller_can_roll_back_successful_add(library):
    conn, first, _ = library
    assert not conn.in_transaction

    custom_stations.add_custom_station(
        conn, profile_id=first, name="Radio", url="https://radio.example/live"
    )
    conn.rollback()

    assert conn.execute("SELECT count(*) FROM stations").fetchone()[0] == 0
    assert favorites.list_favorites(conn, first) == []


def test_favorite_failure_rolls_back_station_and_keeps_outer_work(library):
    import sqlite3

    conn, first, _ = library
    conn.execute(
        """
        CREATE TEMP TRIGGER reject_custom_favorite
        BEFORE INSERT ON favorites
        BEGIN
            SELECT RAISE(ABORT, 'test favorite failure');
        END
        """
    )
    conn.execute(
        "UPDATE profiles SET display_name = ? WHERE id = ?",
        ("Keep outer change", first),
    )

    with pytest.raises(sqlite3.IntegrityError, match="test favorite failure"):
        custom_stations.add_custom_station(
            conn, profile_id=first, name="Radio", url="https://radio.example/live"
        )

    assert conn.execute("SELECT count(*) FROM stations").fetchone()[0] == 0
    assert favorites.list_favorites(conn, first) == []
    assert (
        conn.execute("SELECT display_name FROM profiles WHERE id = ?", (first,)).fetchone()[0]
        == "Keep outer change"
    )
    assert conn.in_transaction


@pytest.mark.parametrize(
    "second_url",
    [
        "http://radio.example/live",
        "https://radio.example/live?channel=other",
        "https://radio.example/live?token=ABC",
    ],
)
def test_different_stream_urls_remain_separate(library, second_url):
    conn, first, _ = library
    for url in ["https://radio.example/live", second_url]:
        assert (
            custom_stations.add_custom_station(conn, profile_id=first, name="Radio", url=url)
            is True
        )
    assert len(favorites.list_favorites(conn, first)) == 2
    assert conn.execute("SELECT count(*) FROM stations").fetchone()[0] == 2
