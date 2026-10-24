# SPDX-License-Identifier: MIT
"""Atomic creation of a local provenance source during import."""

from dataclasses import asdict

import pytest

from fluxtuner.core import db, m3u_import
from fluxtuner.core import station_provenance as provenance


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "new-source.db"
    db.init_db(path)
    with db.connect(path) as conn:
        profile_id = db.ensure_default_profile(conn)
        conn.commit()
        yield conn, profile_id


def _entries():
    return m3u_import.parse_m3u(
        b"#EXTM3U\n"
        b"#EXTINF:-1,One\nhttps://one.example/live\n"
        b"#EXTINF:-1,Two\nhttps://two.example/live\n"
    ).entries


def _count(conn, table):
    assert table in {
        "station_sources",
        "station_source_memberships",
        "stations",
        "favorites",
        "playlists",
        "playlist_stations",
    }
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_new_source_and_station_import_are_atomic(library):
    conn, profile_id = library
    outcome = m3u_import.import_m3u_with_new_source(
        conn,
        profile_id=profile_id,
        playlist_name="Jazz",
        entries=_entries(),
        display_name="Jazz collection",
    )
    assert outcome.result.added_favorites == 2
    assert outcome.result.added_to_playlist == 2
    assert _count(conn, "station_sources") == 1
    assert _count(conn, "station_source_memberships") == 2
    assert (
        provenance.get_source(conn, profile_id=profile_id, source_id=outcome.source_id)["kind"]
        == "local_collection"
    )
    assert (
        len(
            provenance.list_source_stations(
                conn, profile_id=profile_id, source_id=outcome.source_id
            )
        )
        == 2
    )
    assert conn.in_transaction


def test_legacy_result_contract_remains_four_fields(library):
    conn, profile_id = library
    outcome = m3u_import.import_m3u_with_new_source(
        conn,
        profile_id=profile_id,
        playlist_name="Jazz",
        entries=_entries(),
    )
    assert set(asdict(outcome.result)) == {
        "added_favorites",
        "existing_favorites",
        "added_to_playlist",
        "already_in_playlist",
    }
    assert asdict(outcome.result)["added_favorites"] == 2


def test_invalid_import_does_not_leave_an_empty_source(library):
    conn, profile_id = library
    with pytest.raises(ValueError, match="no valid stations"):
        m3u_import.import_m3u_with_new_source(
            conn,
            profile_id=profile_id,
            playlist_name="Jazz",
            entries=(),
        )
    assert _count(conn, "station_sources") == 0
    assert _count(conn, "playlists") == 0
    assert _count(conn, "stations") == 0


def test_failure_after_first_observation_reverts_source_and_library(library, monkeypatch):
    conn, profile_id = library
    db.create_playlist_record(conn, "Earlier work", profile_id=profile_id)
    conn.commit()

    original = provenance.record_observation
    calls = 0

    def fail_on_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected source import failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(m3u_import.provenance, "record_observation", fail_on_second)

    with pytest.raises(RuntimeError, match="injected source import failure"):
        m3u_import.import_m3u_with_new_source(
            conn,
            profile_id=profile_id,
            playlist_name="Jazz",
            entries=_entries(),
        )

    assert db.get_playlist_record(conn, "Earlier work", profile_id=profile_id) is not None
    assert db.get_playlist_record(conn, "Jazz", profile_id=profile_id) is None
    for table in (
        "station_sources",
        "station_source_memberships",
        "stations",
        "favorites",
        "playlist_stations",
    ):
        assert _count(conn, table) == 0


def test_caller_rollback_removes_new_source_and_stations(library):
    conn, profile_id = library
    m3u_import.import_m3u_with_new_source(
        conn,
        profile_id=profile_id,
        playlist_name="Jazz",
        entries=_entries(),
    )
    conn.rollback()
    for table in (
        "station_sources",
        "station_source_memberships",
        "stations",
        "favorites",
        "playlists",
    ):
        assert _count(conn, table) == 0


def test_invalid_profile_cannot_leave_source(library):
    conn, _ = library
    with pytest.raises(ValueError):
        m3u_import.import_m3u_with_new_source(
            conn,
            profile_id=999999,
            playlist_name="Jazz",
            entries=_entries(),
        )
    assert _count(conn, "station_sources") == 0
    assert _count(conn, "stations") == 0
