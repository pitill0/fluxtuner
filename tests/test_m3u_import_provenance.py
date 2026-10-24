# SPDX-License-Identifier: MIT
"""Atomic station provenance during M3U imports."""

from __future__ import annotations

import pytest

from fluxtuner.core import db, m3u_import
from fluxtuner.core import station_provenance as provenance
from fluxtuner.core.profiles import get_or_create_profile


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "import-provenance.db"
    db.init_db(path)
    with db.connect(path) as conn:
        first = db.ensure_default_profile(conn)
        second = get_or_create_profile(conn, "Other")
        conn.commit()
        yield conn, first, second


def _entries():
    return m3u_import.parse_m3u(
        b"#EXTM3U\n"
        b"#EXTINF:-1,One\nhttps://one.example/live\n"
        b"#EXTINF:-1,Two\nhttps://two.example/live\n"
    ).entries


def _count(conn, table):
    assert table in {
        "stations",
        "favorites",
        "playlists",
        "playlist_stations",
        "station_sources",
        "station_source_memberships",
    }
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_legacy_import_records_no_provenance(library):
    conn, first, _ = library
    result = m3u_import.import_m3u(
        conn, profile_id=first, playlist_name="Legacy", entries=_entries()
    )
    assert result.added_favorites == 2
    assert _count(conn, "stations") == 2
    assert _count(conn, "station_sources") == 0
    assert _count(conn, "station_source_memberships") == 0


def test_import_observes_all_stations_for_owned_source(library):
    conn, first, _ = library
    source_id = provenance.create_source(conn, profile_id=first, kind="local_collection")
    result = m3u_import.import_m3u(
        conn,
        profile_id=first,
        playlist_name="Jazz",
        entries=_entries(),
        source_id=source_id,
    )
    assert result.added_favorites == 2
    assert _count(conn, "station_source_memberships") == 2
    assert len(provenance.list_source_stations(conn, profile_id=first, source_id=source_id)) == 2


def test_reimport_into_another_playlist_reuses_observations(library):
    conn, first, _ = library
    source_id = provenance.create_source(conn, profile_id=first, kind="remote_collection")
    m3u_import.import_m3u(
        conn,
        profile_id=first,
        playlist_name="First",
        entries=_entries(),
        source_id=source_id,
    )
    before = {
        row["station_id"]: row["first_observed_at"]
        for row in conn.execute(
            "SELECT station_id, first_observed_at FROM station_source_memberships"
        )
    }
    result = m3u_import.import_m3u(
        conn,
        profile_id=first,
        playlist_name="Second",
        entries=_entries(),
        source_id=source_id,
    )
    assert result.added_favorites == 0
    assert result.added_to_playlist == 2
    assert _count(conn, "station_source_memberships") == 2
    assert {
        row["station_id"]: row["first_observed_at"]
        for row in conn.execute(
            "SELECT station_id, first_observed_at FROM station_source_memberships"
        )
    } == before


def test_foreign_source_is_rejected_before_library_writes(library):
    conn, first, second = library
    foreign_source = provenance.create_source(conn, profile_id=second, kind="local_collection")
    with pytest.raises(ValueError, match="Source not found"):
        m3u_import.import_m3u(
            conn,
            profile_id=first,
            playlist_name="Denied",
            entries=_entries(),
            source_id=foreign_source,
        )
    assert _count(conn, "stations") == 0
    assert _count(conn, "favorites") == 0
    assert _count(conn, "playlists") == 0
    assert _count(conn, "station_source_memberships") == 0


@pytest.mark.parametrize("invalid_source", [0, -1, True, 999999])
def test_invalid_source_cannot_write_library(library, invalid_source):
    conn, first, _ = library
    with pytest.raises(ValueError):
        m3u_import.import_m3u(
            conn,
            profile_id=first,
            playlist_name="Denied",
            entries=_entries(),
            source_id=invalid_source,
        )
    assert _count(conn, "stations") == 0
    assert _count(conn, "playlists") == 0


def test_failed_provenance_write_rolls_back_entire_import(library, monkeypatch):
    conn, first, _ = library
    source_id = provenance.create_source(conn, profile_id=first, kind="local_collection")
    db.create_playlist_record(conn, "Earlier work", profile_id=first)
    conn.commit()

    original = provenance.record_observation
    calls = 0

    def fail_on_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected provenance failure")
        return original(*args, **kwargs)

    monkeypatch.setattr(m3u_import.provenance, "record_observation", fail_on_second)

    with pytest.raises(RuntimeError, match="injected provenance failure"):
        m3u_import.import_m3u(
            conn,
            profile_id=first,
            playlist_name="New",
            entries=_entries(),
            source_id=source_id,
        )

    assert db.get_playlist_record(conn, "Earlier work", profile_id=first) is not None
    assert db.get_playlist_record(conn, "New", profile_id=first) is None
    assert _count(conn, "stations") == 0
    assert _count(conn, "favorites") == 0
    assert _count(conn, "playlist_stations") == 0
    assert _count(conn, "station_source_memberships") == 0
    assert _count(conn, "station_sources") == 1


def test_caller_rollback_includes_library_and_provenance(library):
    conn, first, _ = library
    source_id = provenance.create_source(conn, profile_id=first, kind="remote_collection")
    conn.commit()

    m3u_import.import_m3u(
        conn,
        profile_id=first,
        playlist_name="New",
        entries=_entries(),
        source_id=source_id,
    )
    assert _count(conn, "station_source_memberships") == 2
    conn.rollback()

    assert _count(conn, "station_source_memberships") == 0
    assert _count(conn, "stations") == 0
    assert _count(conn, "playlists") == 0
    assert _count(conn, "station_sources") == 1
