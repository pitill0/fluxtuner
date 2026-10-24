# SPDX-License-Identifier: MIT
"""Profile isolation and transaction tests for station provenance."""

import pytest

from fluxtuner.core import db
from fluxtuner.core import station_provenance as provenance
from fluxtuner.core.custom_stations import add_custom_station
from fluxtuner.core.profiles import get_or_create_profile


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "provenance.db"
    db.init_db(path)
    with db.connect(path) as conn:
        first = db.ensure_default_profile(conn)
        second = get_or_create_profile(conn, "Other")
        add_custom_station(conn, profile_id=first, name="Radio", url="https://example.test/live")
        station = conn.execute("SELECT id FROM stations").fetchone()["id"]
        conn.commit()
        yield conn, first, second, station


def test_sources_are_profile_scoped(library):
    conn, first, second, station = library
    source = provenance.create_source(
        conn, profile_id=first, kind="local_collection", display_name="Jazz.m3u"
    )
    provenance.record_observation(conn, profile_id=first, source_id=source, station_id=station)
    assert len(provenance.list_station_sources(conn, profile_id=first, station_id=station)) == 1
    assert provenance.list_station_sources(conn, profile_id=second, station_id=station) == []
    for operation in (
        lambda: provenance.get_source(conn, profile_id=second, source_id=source),
        lambda: provenance.list_source_stations(conn, profile_id=second, source_id=source),
        lambda: provenance.record_observation(
            conn, profile_id=second, source_id=source, station_id=station
        ),
        lambda: provenance.delete_source(conn, profile_id=second, source_id=source),
    ):
        with pytest.raises(ValueError, match="Source not found"):
            operation()
    assert len(provenance.list_source_stations(conn, profile_id=first, source_id=source)) == 1


def test_repeated_observation_does_not_duplicate_membership(library):
    conn, first, _, station = library
    source = provenance.create_source(conn, profile_id=first, kind="remote_collection")
    before = dict(conn.execute("SELECT * FROM stations WHERE id = ?", (station,)).fetchone())
    provenance.record_observation(conn, profile_id=first, source_id=source, station_id=station)
    first_date = conn.execute(
        "SELECT first_observed_at FROM station_source_memberships"
    ).fetchone()[0]
    provenance.record_observation(conn, profile_id=first, source_id=source, station_id=station)
    assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 1
    assert (
        conn.execute("SELECT first_observed_at FROM station_source_memberships").fetchone()[0]
        == first_date
    )
    assert (
        dict(conn.execute("SELECT * FROM stations WHERE id = ?", (station,)).fetchone()) == before
    )


def test_source_deletion_preserves_station_and_favorite(library):
    conn, first, _, station = library
    source = provenance.create_source(conn, profile_id=first, kind="local_collection")
    provenance.record_observation(conn, profile_id=first, source_id=source, station_id=station)
    assert provenance.delete_source(conn, profile_id=first, source_id=source)
    assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 0


def test_caller_rollback_removes_source_and_observation(library):
    conn, first, _, station = library
    conn.execute("SAVEPOINT provenance_test")
    source = provenance.create_source(conn, profile_id=first, kind="local_collection")
    provenance.record_observation(conn, profile_id=first, source_id=source, station_id=station)
    conn.execute("ROLLBACK TO SAVEPOINT provenance_test")
    conn.execute("RELEASE SAVEPOINT provenance_test")
    assert conn.execute("SELECT COUNT(*) FROM station_sources").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 0


@pytest.mark.parametrize("bad_profile", [None, 0, -1, True, 999999])
def test_invalid_profile_never_creates_a_source(library, bad_profile):
    conn, _, _, _ = library
    with pytest.raises(ValueError):
        provenance.create_source(conn, profile_id=bad_profile, kind="local_collection")
    assert conn.execute("SELECT COUNT(*) FROM station_sources").fetchone()[0] == 0


@pytest.mark.parametrize(
    "bad_name",
    ["https://private.example/feed", "/home/private/list.m3u", "Secret?token=value", "x" * 121],
)
def test_display_name_rejects_paths_and_urls(library, bad_name):
    conn, first, _, _ = library
    with pytest.raises(ValueError):
        provenance.create_source(
            conn, profile_id=first, kind="remote_collection", display_name=bad_name
        )
    assert conn.execute("SELECT COUNT(*) FROM station_sources").fetchone()[0] == 0


def test_caller_controls_commit(library):
    conn, first, _, _ = library
    provenance.create_source(conn, profile_id=first, kind="local_collection")
    assert conn.in_transaction
