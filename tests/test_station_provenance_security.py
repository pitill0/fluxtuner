# SPDX-License-Identifier: MIT
"""Security and ownership regressions for station provenance."""

from __future__ import annotations

import pytest

from fluxtuner.core import db
from fluxtuner.core import station_provenance as provenance
from fluxtuner.core.custom_stations import add_custom_station
from fluxtuner.core.profiles import get_or_create_profile


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "provenance-security.db"
    db.init_db(path)
    with db.connect(path) as conn:
        first = db.ensure_default_profile(conn)
        second = get_or_create_profile(conn, "Second")
        add_custom_station(
            conn,
            profile_id=first,
            name="Radio",
            url="https://example.test/live",
        )
        station_id = int(conn.execute("SELECT id FROM stations").fetchone()["id"])
        conn.commit()
        yield conn, first, second, station_id


@pytest.mark.parametrize("station_id", [None, 0, -1, True, 999999])
def test_invalid_station_cannot_create_observation(library, station_id):
    conn, first, _, _ = library
    source_id = provenance.create_source(conn, profile_id=first, kind="local_collection")
    with pytest.raises(ValueError):
        provenance.record_observation(
            conn,
            profile_id=first,
            source_id=source_id,
            station_id=station_id,
        )
    assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 0


def test_shared_station_can_have_independent_profile_sources(library):
    conn, first, second, station_id = library
    local = provenance.create_source(conn, profile_id=first, kind="local_collection")
    remote = provenance.create_source(conn, profile_id=first, kind="remote_collection")
    other = provenance.create_source(conn, profile_id=second, kind="local_collection")
    for owner, source in ((first, local), (first, remote), (second, other)):
        provenance.record_observation(
            conn, profile_id=owner, source_id=source, station_id=station_id
        )

    first_sources = provenance.list_station_sources(conn, profile_id=first, station_id=station_id)
    second_sources = provenance.list_station_sources(conn, profile_id=second, station_id=station_id)
    assert {item["id"] for item in first_sources} == {local, remote}
    assert {item["id"] for item in second_sources} == {other}
    assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 1


def test_profile_deletion_cascades_only_owned_provenance(library):
    conn, first, second, station_id = library
    first_source = provenance.create_source(conn, profile_id=first, kind="local_collection")
    second_source = provenance.create_source(conn, profile_id=second, kind="remote_collection")
    provenance.record_observation(
        conn, profile_id=first, source_id=first_source, station_id=station_id
    )
    provenance.record_observation(
        conn, profile_id=second, source_id=second_source, station_id=station_id
    )

    conn.execute("DELETE FROM profiles WHERE id = ?", (first,))
    remaining = conn.execute("SELECT id, profile_id FROM station_sources").fetchall()
    assert [(row["id"], row["profile_id"]) for row in remaining] == [(second_source, second)]
    assert (
        provenance.list_station_sources(conn, profile_id=second, station_id=station_id)[0]["id"]
        == second_source
    )
    assert conn.execute("SELECT COUNT(*) FROM stations").fetchone()[0] == 1
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_foreign_source_id_is_not_usable_as_capability(library):
    conn, first, second, station_id = library
    source_id = provenance.create_source(conn, profile_id=first, kind="local_collection")
    provenance.record_observation(
        conn, profile_id=first, source_id=source_id, station_id=station_id
    )

    for action in (
        lambda: provenance.get_source(conn, profile_id=second, source_id=source_id),
        lambda: provenance.list_source_stations(conn, profile_id=second, source_id=source_id),
        lambda: provenance.record_observation(
            conn, profile_id=second, source_id=source_id, station_id=station_id
        ),
        lambda: provenance.delete_source(conn, profile_id=second, source_id=source_id),
    ):
        with pytest.raises(ValueError, match="Source not found"):
            action()

    assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 1


def test_observation_timestamp_update_can_be_rolled_back(library):
    conn, first, _, station_id = library
    source_id = provenance.create_source(conn, profile_id=first, kind="local_collection")
    provenance.record_observation(
        conn, profile_id=first, source_id=source_id, station_id=station_id
    )
    conn.commit()

    conn.execute(
        """
        UPDATE station_source_memberships
        SET last_observed_at = ?
        WHERE source_id = ? AND station_id = ?
        """,
        ("2000-01-01T00:00:00+00:00", source_id, station_id),
    )
    conn.commit()

    conn.execute("SAVEPOINT observe_rollback")
    provenance.record_observation(
        conn, profile_id=first, source_id=source_id, station_id=station_id
    )
    assert (
        conn.execute(
            """
        SELECT last_observed_at FROM station_source_memberships
        WHERE source_id = ? AND station_id = ?
        """,
            (source_id, station_id),
        ).fetchone()[0]
        != "2000-01-01T00:00:00+00:00"
    )

    conn.execute("ROLLBACK TO SAVEPOINT observe_rollback")
    conn.execute("RELEASE SAVEPOINT observe_rollback")
    assert (
        conn.execute(
            """
        SELECT last_observed_at FROM station_source_memberships
        WHERE source_id = ? AND station_id = ?
        """,
            (source_id, station_id),
        ).fetchone()[0]
        == "2000-01-01T00:00:00+00:00"
    )


def test_public_source_data_does_not_expose_opaque_ref(library):
    conn, first, _, station_id = library
    source_id = provenance.create_source(
        conn, profile_id=first, kind="remote_collection", display_name="Jazz"
    )
    provenance.record_observation(
        conn, profile_id=first, source_id=source_id, station_id=station_id
    )

    private_ref = conn.execute(
        "SELECT source_ref FROM station_sources WHERE id = ?", (source_id,)
    ).fetchone()[0]

    source = provenance.get_source(conn, profile_id=first, source_id=source_id)
    observed = provenance.list_station_sources(conn, profile_id=first, station_id=station_id)

    assert "source_ref" not in source
    assert all("source_ref" not in item for item in observed)
    assert private_ref not in str(source)
    assert private_ref not in str(observed)
