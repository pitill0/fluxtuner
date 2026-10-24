# SPDX-License-Identifier: MIT
"""Manual provenance, explicit reuse and privacy integration."""

from __future__ import annotations

import pytest

from fluxtuner.core import db
from fluxtuner.core import station_provenance as provenance
from fluxtuner.core.custom_stations import add_custom_station
from fluxtuner.core.m3u_import import import_m3u, parse_station_collection
from fluxtuner.core.profiles import get_or_create_profile


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "manual-provenance.db")
    db.init_db()
    with db.connect() as conn:
        first = db.ensure_default_profile(conn)
        second = get_or_create_profile(conn, "Second")
        conn.commit()
    return first, second


def test_manual_creation_adds_one_source_and_observation(library):
    first, _ = library
    with db.connect() as conn:
        assert add_custom_station(
            conn,
            profile_id=first,
            name="Personal",
            url="https://radio.example/live?token=private",
            record_manual_provenance=True,
        )
        sources = provenance.list_sources(conn, profile_id=first)
        assert len(sources) == 1
        assert sources[0]["kind"] == "manual_entry"
        assert sources[0]["display_name"] is None
        stations = provenance.list_source_stations(
            conn, profile_id=first, source_id=sources[0]["id"]
        )
        assert len(stations) == 1
        assert "station_key" not in stations[0]
        assert "token=private" not in str(stations)
        conn.commit()


def test_duplicate_manual_entry_does_not_create_second_source(library):
    first, _ = library
    with db.connect() as conn:
        args = {
            "profile_id": first,
            "name": "Personal",
            "url": "https://radio.example/live",
            "record_manual_provenance": True,
        }
        assert add_custom_station(conn, **args)
        assert not add_custom_station(conn, **args)
        assert len(provenance.list_sources(conn, profile_id=first)) == 1
        assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 1


def test_manual_sources_are_isolated_by_profile(library):
    first, second = library
    with db.connect() as conn:
        for owner in (first, second):
            assert add_custom_station(
                conn,
                profile_id=owner,
                name="Radio",
                url="https://radio.example/live",
                record_manual_provenance=True,
            )
        assert len(provenance.list_sources(conn, profile_id=first)) == 1
        assert len(provenance.list_sources(conn, profile_id=second)) == 1
        assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 1


def test_failure_rolls_back_manual_station_and_source(library, monkeypatch):
    first, _ = library

    def fail(*args, **kwargs):
        raise RuntimeError("injected observation failure")

    monkeypatch.setattr(provenance, "record_observation", fail)

    with db.connect() as conn:
        with pytest.raises(RuntimeError, match="injected observation"):
            add_custom_station(
                conn,
                profile_id=first,
                name="Radio",
                url="https://radio.example/live",
                record_manual_provenance=True,
            )
        for table in ("stations", "favorites", "station_sources", "station_source_memberships"):
            assert conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0


def test_legacy_import_does_not_create_manual_source(library):
    first, _ = library
    entries = parse_station_collection(
        b"#EXTM3U\n#EXTINF:-1,Radio\nhttps://radio.example/live\n"
    ).entries
    with db.connect() as conn:
        result = import_m3u(conn, profile_id=first, playlist_name="Imported", entries=entries)
        assert result.added_to_playlist == 1
        assert provenance.list_sources(conn, profile_id=first) == []


def test_reuse_existing_source_retains_one_identity(library):
    first, _ = library
    entries = parse_station_collection(
        b"#EXTM3U\n#EXTINF:-1,Radio\nhttps://radio.example/live\n"
    ).entries
    with db.connect() as conn:
        source_id = provenance.create_source(conn, profile_id=first, kind="local_collection")
        for playlist_name in ("Morning", "Evening"):
            import_m3u(
                conn,
                profile_id=first,
                playlist_name=playlist_name,
                entries=entries,
                source_id=source_id,
            )
        assert [src["id"] for src in provenance.list_sources(conn, profile_id=first)] == [source_id]
        assert (
            len(provenance.list_source_stations(conn, profile_id=first, source_id=source_id)) == 1
        )


def test_foreign_source_cannot_be_reused(library):
    first, second = library
    entries = parse_station_collection(
        b"#EXTM3U\n#EXTINF:-1,Radio\nhttps://radio.example/live\n"
    ).entries
    with db.connect() as conn:
        foreign = provenance.create_source(conn, profile_id=second, kind="local_collection")
        with pytest.raises(ValueError, match="Source not found"):
            import_m3u(
                conn,
                profile_id=first,
                playlist_name="Denied",
                entries=entries,
                source_id=foreign,
            )
        assert provenance.list_sources(conn, profile_id=first) == []
