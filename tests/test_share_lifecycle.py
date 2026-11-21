# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Recommendation expiry, privacy, batch and rollback tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from fluxtuner.core import db
from fluxtuner.core.share_lifecycle import expire_shares, purge_old_shares
from fluxtuner.core.share_service import create_share

NOW = datetime(2026, 11, 18, 21, 0, tzinfo=UTC)
URL = "https://radio.example/live"


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "lifecycle.db"
    db.init_db(path)

    with db.connect(path) as conn:
        alice = db.get_or_create_user(conn, "alice", password_hash="test")
        db.get_or_create_user(conn, "bob", password_hash="test")

        profile = db.ensure_default_profile(conn, user_id=alice)

        db.add_favorite_record(
            conn,
            {"name": "Example Radio", "url": URL},
            profile_id=profile,
        )
        for index in range(1, 4):
            db.add_favorite_record(
                conn,
                {
                    "name": f"Example Radio {index}",
                    "url": f"https://radio.example/live/{index}",
                },
                profile_id=profile,
            )

        conn.commit()

        yield conn, alice, profile


def send(conn, alice, profile, when, *, station_number=0):
    return create_share(
        conn,
        sender_user_id=alice,
        recipient_username="bob",
        source_profile_id=profile,
        kind="station",
        station_key=(
            URL if station_number == 0 else f"https://radio.example/live/{station_number}"
        ),
        now=when,
    )


def load(conn, identifier):
    return conn.execute(
        "SELECT * FROM playlist_shares WHERE id = ?",
        (identifier,),
    ).fetchone()


def test_expiry_removes_snapshot_atomically(library):
    conn, alice, profile = library

    identifier = send(conn, alice, profile, NOW - timedelta(days=8))

    before = load(conn, identifier)
    assert before["status"] == "pending"
    assert before["snapshot_json"] is not None

    assert expire_shares(conn, now=NOW) == 1

    after = load(conn, identifier)

    assert after["status"] == "expired"
    assert after["snapshot_json"] is None
    assert after["resolved_at"] == NOW.isoformat()
    assert after["sender_user_id"] == alice


def test_expiry_is_idempotent(library):
    conn, alice, profile = library
    identifier = send(conn, alice, profile, NOW - timedelta(days=8))

    assert expire_shares(conn, now=NOW) == 1
    assert expire_shares(conn, now=NOW) == 0

    assert load(conn, identifier)["status"] == "expired"


def test_active_share_is_not_expired(library):
    conn, alice, profile = library
    identifier = send(conn, alice, profile, NOW)

    assert expire_shares(conn, now=NOW) == 0

    row = load(conn, identifier)
    assert row["status"] == "pending"
    assert row["snapshot_json"] is not None


def test_expiration_boundary_is_inclusive(library):
    conn, alice, profile = library

    created = NOW - timedelta(days=7)
    identifier = send(conn, alice, profile, created)

    assert expire_shares(conn, now=NOW) == 1
    assert load(conn, identifier)["status"] == "expired"


def test_resolved_recommendation_is_preserved(library):
    conn, alice, profile = library
    identifier = send(conn, alice, profile, NOW - timedelta(days=8))

    resolved_time = NOW - timedelta(days=1)

    conn.execute(
        """
        UPDATE playlist_shares
        SET status = 'rejected',
            snapshot_json = NULL,
            resolved_at = ?
        WHERE id = ?
        """,
        (resolved_time.isoformat(), identifier),
    )
    conn.commit()

    assert expire_shares(conn, now=NOW) == 0

    row = load(conn, identifier)
    assert row["status"] == "rejected"
    assert row["resolved_at"] == resolved_time.isoformat()


def test_batch_size_limits_work_per_call(library):
    conn, alice, profile = library

    identifiers = [
        send(
            conn,
            alice,
            profile,
            NOW - timedelta(days=12 - index),
            station_number=index,
        )
        for index in range(4)
    ]

    assert expire_shares(conn, now=NOW, batch_size=2) == 2

    statuses = [load(conn, identifier)["status"] for identifier in identifiers]

    assert statuses == [
        "expired",
        "expired",
        "pending",
        "pending",
    ]

    assert expire_shares(conn, now=NOW, batch_size=2) == 2

    assert all(load(conn, identifier)["snapshot_json"] is None for identifier in identifiers)


@pytest.mark.parametrize(
    "batch_size",
    [0, -1, 501, True, 1.5, "20"],
)
def test_invalid_batch_size_is_rejected(library, batch_size):
    conn, _, _ = library

    with pytest.raises(ValueError):
        expire_shares(conn, now=NOW, batch_size=batch_size)

    assert not conn.in_transaction


@pytest.mark.parametrize(
    "timestamp",
    [datetime(2026, 11, 18), "2026-11-18", 0],
)
def test_invalid_timestamp_is_rejected(library, timestamp):
    conn, _, _ = library

    with pytest.raises(ValueError):
        expire_shares(conn, now=timestamp)


def test_existing_transaction_is_never_committed(library):
    conn, _, _ = library

    conn.execute("BEGIN")

    with pytest.raises(ValueError, match="independent transaction"):
        expire_shares(conn, now=NOW)

    assert conn.in_transaction
    conn.rollback()


def test_failure_rolls_back_entire_expiry_batch(library):
    conn, alice, profile = library

    first = send(conn, alice, profile, NOW - timedelta(days=10))
    second = send(
        conn,
        alice,
        profile,
        NOW - timedelta(days=9),
        station_number=1,
    )

    conn.execute(
        f"""
        CREATE TRIGGER block_expiry_{second}
        BEFORE UPDATE ON playlist_shares
        WHEN NEW.id = {second}
         AND NEW.status = 'expired'
        BEGIN
            SELECT RAISE(ABORT, 'expiry blocked');
        END
        """
    )
    conn.commit()

    with pytest.raises(Exception, match="expiry blocked"):
        expire_shares(conn, now=NOW)

    for identifier in (first, second):
        row = load(conn, identifier)
        assert row["status"] == "pending"
        assert row["snapshot_json"] is not None
        assert row["resolved_at"] is None

    assert not conn.in_transaction


def test_history_purge_preserves_pending_and_recent_resolutions(library):
    conn, alice, profile = library
    old = send(conn, alice, profile, NOW - timedelta(days=40))
    recent = send(conn, alice, profile, NOW - timedelta(days=10), station_number=1)
    pending = send(conn, alice, profile, NOW - timedelta(days=40), station_number=2)
    conn.execute(
        "UPDATE playlist_shares SET status = 'accepted', snapshot_json = NULL, "
        "resolved_at = ? WHERE id = ?",
        ((NOW - timedelta(days=31)).isoformat(), old),
    )
    conn.execute(
        "UPDATE playlist_shares SET status = 'rejected', snapshot_json = NULL, "
        "resolved_at = ? WHERE id = ?",
        ((NOW - timedelta(days=29)).isoformat(), recent),
    )
    conn.commit()

    assert purge_old_shares(conn, now=NOW) == 1
    assert load(conn, old) is None
    assert load(conn, recent) is not None
    assert load(conn, pending)["status"] == "pending"
    assert purge_old_shares(conn, now=NOW) == 0


def test_history_purge_uses_expiry_date_not_delayed_cleanup_date(library):
    conn, alice, profile = library
    identifier = send(conn, alice, profile, NOW - timedelta(days=40))
    assert expire_shares(conn, now=NOW) == 1
    assert load(conn, identifier)["resolved_at"] == NOW.isoformat()
    assert purge_old_shares(conn, now=NOW) == 1
    assert load(conn, identifier) is None


def test_history_purge_is_bounded_and_keeps_30_day_boundary(library):
    conn, alice, profile = library
    ids = [
        send(conn, alice, profile, NOW - timedelta(days=40), station_number=index)
        for index in range(3)
    ]
    for index, identifier in enumerate(ids):
        conn.execute(
            "UPDATE playlist_shares SET status = 'rejected', snapshot_json = NULL, "
            "resolved_at = ? WHERE id = ?",
            ((NOW - timedelta(days=31 if index < 2 else 29)).isoformat(), identifier),
        )
    conn.commit()

    assert purge_old_shares(conn, now=NOW, batch_size=1) == 1
    assert purge_old_shares(conn, now=NOW, batch_size=1) == 1
    assert purge_old_shares(conn, now=NOW, batch_size=1) == 0
    assert load(conn, ids[2]) is not None


@pytest.mark.parametrize("batch_size", [0, -1, 501, True, 1.5, "20"])
def test_history_purge_rejects_invalid_batch_sizes(library, batch_size):
    conn, _, _ = library
    with pytest.raises(ValueError):
        purge_old_shares(conn, now=NOW, batch_size=batch_size)
    assert not conn.in_transaction


def test_history_purge_does_not_commit_caller_transaction(library):
    conn, _, _ = library
    conn.execute("BEGIN")
    with pytest.raises(ValueError, match="independent transaction"):
        purge_old_shares(conn, now=NOW)
    assert conn.in_transaction
    conn.rollback()


def test_history_purge_failure_rolls_back_entire_batch(library):
    conn, alice, profile = library
    first = send(conn, alice, profile, NOW - timedelta(days=40))
    second = send(conn, alice, profile, NOW - timedelta(days=40), station_number=1)
    for identifier in (first, second):
        conn.execute(
            "UPDATE playlist_shares SET status = 'rejected', snapshot_json = NULL, "
            "resolved_at = ? WHERE id = ?",
            ((NOW - timedelta(days=31)).isoformat(), identifier),
        )
    conn.execute(
        f"""
        CREATE TRIGGER block_history_purge_{second}
        BEFORE DELETE ON playlist_shares
        WHEN OLD.id = {second}
        BEGIN
            SELECT RAISE(ABORT, 'history purge blocked');
        END
        """
    )
    conn.commit()

    with pytest.raises(Exception, match="history purge blocked"):
        purge_old_shares(conn, now=NOW)
    assert load(conn, first) is not None
    assert load(conn, second) is not None
    assert not conn.in_transaction
