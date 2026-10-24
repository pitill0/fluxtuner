# SPDX-License-Identifier: MIT
"""Remote provenance dispatch and profile-owned source catalog."""

import pytest

from fluxtuner import tui_m3u_import as importer
from fluxtuner.core import db
from fluxtuner.core import station_provenance as provenance
from fluxtuner.core.m3u_import import (
    import_m3u_with_new_source,
    parse_station_collection,
)
from fluxtuner.core.profiles import get_or_create_profile


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "remote-provenance.db")
    db.init_db()
    with db.connect() as conn:
        first = db.ensure_default_profile(conn)
        second = get_or_create_profile(conn, "Second")
        conn.commit()
    return first, second


def _preview():
    return parse_station_collection(b"#EXTM3U\n#EXTINF:-1,Radio\nhttps://radio.example/live\n")


def test_tui_remote_dispatch_records_remote_source(library):
    first, second = library
    outcome = importer._save_import(
        first,
        _preview(),
        "Remote collection",
        False,
        lambda: True,
        remote_source=True,
    )
    assert outcome.result.added_to_playlist == 1

    with db.connect() as conn:
        sources = provenance.list_sources(conn, profile_id=first)
        assert len(sources) == 1
        assert sources[0]["kind"] == "remote_collection"
        assert sources[0]["display_name"] is None
        assert (
            len(provenance.list_source_stations(conn, profile_id=first, source_id=sources[0]["id"]))
            == 1
        )
        assert provenance.list_sources(conn, profile_id=second) == []


def test_catalog_is_profile_scoped_and_hides_refs(library):
    first, second = library
    with db.connect() as conn:
        first_id = provenance.create_source(conn, profile_id=first, kind="local_collection")
        second_id = provenance.create_source(conn, profile_id=second, kind="remote_collection")
        conn.commit()

        first_sources = provenance.list_sources(conn, profile_id=first)
        second_sources = provenance.list_sources(conn, profile_id=second)
        assert [row["id"] for row in first_sources] == [first_id]
        assert [row["id"] for row in second_sources] == [second_id]
        assert "source_ref" not in first_sources[0]
        assert "station_key" not in first_sources[0]


def test_conflicting_source_context_rejected(library):
    first, _ = library
    with pytest.raises(ValueError, match="Conflicting"):
        importer._save_import(
            first,
            _preview(),
            "Conflict",
            False,
            lambda: True,
            local_source=True,
            remote_source=True,
        )
    with db.connect() as conn:
        assert provenance.list_sources(conn, profile_id=first) == []


def test_remote_source_creation_obeys_caller_rollback(library):
    first, _ = library
    with db.connect() as conn:
        outcome = import_m3u_with_new_source(
            conn,
            profile_id=first,
            playlist_name="Rollback",
            entries=_preview().entries,
            kind="remote_collection",
        )
        assert outcome.result.added_to_playlist == 1
        conn.rollback()
        assert provenance.list_sources(conn, profile_id=first) == []
