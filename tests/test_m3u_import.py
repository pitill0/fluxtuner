# SPDX-License-Identifier: MIT

from __future__ import annotations

import socket
import sqlite3

import pytest

from fluxtuner.core import db, m3u_import
from fluxtuner.core.custom_stations import add_custom_station
from fluxtuner.core.profiles import get_or_create_profile


@pytest.fixture
def storage(tmp_path):
    path = tmp_path / "fluxtuner.db"
    db.init_db(path)
    with db.connect(path) as conn:
        profile_id = db.ensure_default_profile(conn)
        other_id = get_or_create_profile(conn, "Other")
        conn.commit()
        yield conn, profile_id, other_id


def test_extended_m3u_supports_bom_accents_comments_and_hls_station_url(monkeypatch):
    def forbidden_network(*args, **kwargs):
        raise AssertionError("Parsing must not contact the network.")

    monkeypatch.setattr(socket, "getaddrinfo", forbidden_network)
    source = (
        "\ufeff#EXTM3U\r\n"
        "# Group: Jazz\r\n"
        "#EXTINF:-1,Ábaco Radio\r\n"
        "# Homepage: https://radio.example/\r\n"
        "https://radio.example/live\r\n"
        '#EXTINF:-1 tvg-name="Jazz, live",Jazz HLS\r\n'
        "https://other.example/live.m3u8\r\n"
    )
    preview = m3u_import.parse_m3u(source.encode("utf-8"))

    assert [(entry.name, entry.url) for entry in preview.entries] == [
        ("Ábaco Radio", "https://radio.example/live"),
        ("Jazz HLS", "https://other.example/live.m3u8"),
    ]
    assert preview.entries[0].line_number == 5
    assert not preview.issues
    assert preview.duplicates == 0


def test_plain_m3u_uses_hostname_when_name_is_missing():
    preview = m3u_import.parse_m3u(b"https://radio.example/live?token=private\n")
    assert len(preview.entries) == 1
    assert preview.entries[0].name == "radio.example"
    assert preview.entries[0].url == "https://radio.example/live?token=private"


def test_duplicate_urls_keep_first_name_and_preserve_distinct_urls():
    preview = m3u_import.parse_m3u(
        b"#EXTINF:-1,First\nhttps://radio.example/live\n"
        b"#EXTINF:-1,Replacement\nhttps://radio.example/live\n"
        b"http://radio.example/live\n"
        b"https://radio.example/live?channel=2\n"
    )
    assert len(preview.entries) == 3
    assert preview.entries[0].name == "First"
    assert preview.duplicates == 1


@pytest.mark.parametrize(
    "url",
    [
        "file:///tmp/audio.mp3",
        "ftp://radio.example/live",
        "relative/audio.mp3",
        "https://user:password@radio.example/live",
        "https://radio.example:0/live",
        "https://radio.example:99999/live",
        "https://radio.example/my stream",
        "https://radio.example/live\\bad",
        "https://",
    ],
)
def test_invalid_entries_are_reported_without_losing_valid_entries(url):
    source = f"#EXTINF:-1,Invalid\n{url}\nhttps://valid.example/live\n"
    preview = m3u_import.parse_m3u(source.encode())
    assert [entry.url for entry in preview.entries] == ["https://valid.example/live"]
    assert len(preview.issues) == 1
    assert preview.issues[0].line_number == 2


@pytest.mark.parametrize("name", ["x" * 201, "Bad\tname"])
def test_invalid_names_are_not_silently_truncated(name):
    preview = m3u_import.parse_m3u(f"#EXTINF:-1,{name}\nhttps://radio.example/live\n".encode())
    assert not preview.entries
    assert len(preview.issues) == 1


@pytest.mark.parametrize(
    "source",
    [
        b"#EXTM3U\n#EXT-X-TARGETDURATION:10\n#EXTINF:10,\nsegment.ts\n",
        b"#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=128000\nhttps://radio.example/a.m3u8\n",
    ],
)
def test_hls_manifests_are_rejected_as_station_collections(source):
    with pytest.raises(ValueError, match="HLS"):
        m3u_import.parse_m3u(source)


@pytest.mark.parametrize("source", [b"\xff\xfe", b"https://radio.example/\x00live"])
def test_binary_or_invalid_utf8_files_fail_clearly(source):
    with pytest.raises(ValueError):
        m3u_import.parse_m3u(source)


def test_empty_collection_has_no_entries():
    preview = m3u_import.parse_m3u(b"#EXTM3U\n# Empty collection\n")
    assert not preview.entries


def test_file_size_is_bounded_before_parsing(monkeypatch):
    monkeypatch.setattr(m3u_import, "MAX_FILE_BYTES", 8)
    with pytest.raises(ValueError):
        m3u_import.parse_m3u(b"x" * 9)


def test_station_limit_counts_duplicate_candidates_too(monkeypatch):
    monkeypatch.setattr(m3u_import, "MAX_STATIONS", 2)
    with pytest.raises(ValueError):
        m3u_import.parse_m3u(b"https://radio.example/live\n" * 3)


def test_local_file_loader_accepts_utf8_bom(tmp_path):
    path = tmp_path / "Jazz.m3u8"
    path.write_bytes("\ufeff#EXTINF:-1,Jazz\nhttps://radio.example/live\n".encode())
    preview = m3u_import.load_m3u_file(path)
    assert preview.entries[0].name == "Jazz"


def test_import_adds_favorites_and_playlist_in_input_order(storage):
    conn, profile_id, other_id = storage
    preview = m3u_import.parse_m3u(
        b"#EXTINF:-1,Second alphabetically\nhttps://two.example/live\n"
        b"#EXTINF:-1,First alphabetically\nhttps://one.example/live\n"
    )
    result = m3u_import.import_m3u(
        conn, profile_id=profile_id, playlist_name="Jazz", entries=preview.entries
    )
    assert result.added_favorites == 2
    assert result.existing_favorites == 0
    assert result.added_to_playlist == 2
    assert result.already_in_playlist == 0
    assert conn.in_transaction
    assert db.get_playlist_record(conn, "Jazz", profile_id=profile_id)["station_keys"] == [
        "https://two.example/live",
        "https://one.example/live",
    ]
    assert not db.list_playlists(conn, profile_id=other_id)


def test_reimport_preserves_metadata_names_tags_and_memberships(storage):
    conn, profile_id, _ = storage
    url = "https://radio.example/live"
    add_custom_station(conn, profile_id=profile_id, name="My name", url=url)
    conn.execute(
        "UPDATE favorites SET favorite_tags_json = ? WHERE profile_id = ?",
        ('["Personal"]', profile_id),
    )
    conn.commit()
    before_station = tuple(conn.execute("SELECT * FROM stations").fetchone())
    before_favorite = tuple(conn.execute("SELECT * FROM favorites").fetchone())

    preview = m3u_import.parse_m3u(f"#EXTINF:-1,Imported name\n{url}\n".encode())
    first = m3u_import.import_m3u(
        conn, profile_id=profile_id, playlist_name="Jazz", entries=preview.entries
    )
    second = m3u_import.import_m3u(
        conn, profile_id=profile_id, playlist_name="Jazz", entries=preview.entries
    )

    assert first.existing_favorites == 1
    assert first.added_to_playlist == 1
    assert second.added_favorites == 0
    assert second.added_to_playlist == 0
    assert second.already_in_playlist == 1
    assert tuple(conn.execute("SELECT * FROM stations").fetchone()) == before_station
    assert tuple(conn.execute("SELECT * FROM favorites").fetchone()) == before_favorite


def test_import_names_belong_to_each_profile(storage):
    conn, profile_id, other_id = storage
    url = "https://radio.example/live"
    add_custom_station(conn, profile_id=profile_id, name="Original", url=url)
    conn.commit()
    before = tuple(conn.execute("SELECT * FROM stations").fetchone())

    preview = m3u_import.parse_m3u(f"#EXTINF:-1,Other name\n{url}\n".encode())
    m3u_import.import_m3u(conn, profile_id=other_id, playlist_name="Jazz", entries=preview.entries)

    assert tuple(conn.execute("SELECT * FROM stations").fetchone()) == before
    assert (
        conn.execute(
            "SELECT custom_name FROM favorites WHERE profile_id = ?", (profile_id,)
        ).fetchone()[0]
        == "Original"
    )
    assert (
        conn.execute(
            "SELECT custom_name FROM favorites WHERE profile_id = ?", (other_id,)
        ).fetchone()[0]
        == "Other name"
    )


@pytest.mark.parametrize("profile_id", [0, -1, True, 999999])
def test_import_requires_an_existing_explicit_profile(storage, profile_id):
    conn, _, _ = storage
    preview = m3u_import.parse_m3u(b"https://radio.example/live\n")
    with pytest.raises(ValueError):
        m3u_import.import_m3u(
            conn, profile_id=profile_id, playlist_name="Jazz", entries=preview.entries
        )
    assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 0


@pytest.mark.parametrize("name", ["", "  ", "Bad\tname", "x" * 121])
def test_invalid_playlist_names_do_not_write(storage, name):
    conn, profile_id, _ = storage
    preview = m3u_import.parse_m3u(b"https://radio.example/live\n")
    with pytest.raises(ValueError):
        m3u_import.import_m3u(
            conn, profile_id=profile_id, playlist_name=name, entries=preview.entries
        )
    assert not db.list_playlists(conn, profile_id=profile_id)
    assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 0


def test_empty_import_does_not_create_playlist(storage):
    conn, profile_id, _ = storage
    with pytest.raises(ValueError):
        m3u_import.import_m3u(conn, profile_id=profile_id, playlist_name="Jazz", entries=())
    assert not db.list_playlists(conn, profile_id=profile_id)


def test_import_rolls_back_all_its_writes_but_preserves_callers_work(storage):
    conn, profile_id, _ = storage
    conn.execute("""
        CREATE TRIGGER reject_second_station
        BEFORE INSERT ON playlist_stations
        WHEN (SELECT url FROM stations WHERE id = NEW.station_id)
             = 'https://two.example/live'
        BEGIN
            SELECT RAISE(ABORT, 'simulated storage failure');
        END
    """)
    conn.commit()
    db.create_playlist_record(conn, "Earlier work", profile_id=profile_id)

    preview = m3u_import.parse_m3u(b"https://one.example/live\nhttps://two.example/live\n")
    with pytest.raises(sqlite3.IntegrityError, match="simulated"):
        m3u_import.import_m3u(
            conn, profile_id=profile_id, playlist_name="Jazz", entries=preview.entries
        )

    assert conn.in_transaction
    assert db.get_playlist_record(conn, "Earlier work", profile_id=profile_id)
    assert db.get_playlist_record(conn, "Jazz", profile_id=profile_id) is None
    assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0] == 0


def test_caller_can_rollback_a_successful_import(storage):
    conn, profile_id, _ = storage
    preview = m3u_import.parse_m3u(b"https://radio.example/live\n")
    m3u_import.import_m3u(
        conn, profile_id=profile_id, playlist_name="Jazz", entries=preview.entries
    )
    conn.rollback()
    assert not db.list_playlists(conn, profile_id=profile_id)
    assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 0
