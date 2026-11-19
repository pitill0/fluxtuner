# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Ownership, authorization and quota contracts for sending shares."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest

from fluxtuner.core import db, share_service


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "shares.db"
    db.init_db(path)

    with db.connect(path) as conn:
        alice = db.get_or_create_user(conn, "alice", password_hash="test")
        bob = db.get_or_create_user(conn, "bob", password_hash="test")
        charlie = db.get_or_create_user(conn, "charlie", password_hash="test")

        alice_profile = db.ensure_default_profile(conn, user_id=alice)
        bob_profile = db.ensure_default_profile(conn, user_id=bob)

        db.add_favorite_record(
            conn,
            {"name": "Radio One", "url": "https://radio.example/one"},
            profile_id=alice_profile,
        )
        db.add_favorite_record(
            conn,
            {"name": "Radio Three", "url": "https://radio.example/three"},
            profile_id=alice_profile,
        )
        db.create_playlist_record(conn, "Morning", profile_id=alice_profile)
        db.add_station_to_playlist_record(
            conn,
            "Morning",
            {"name": "Radio Two", "url": "https://radio.example/two"},
            profile_id=alice_profile,
        )
        conn.commit()

        yield conn, alice, bob, charlie, alice_profile, bob_profile


def _send(conn, alice, profile, **overrides):
    args = {
        "sender_user_id": alice,
        "recipient_username": "bob",
        "source_profile_id": profile,
        "kind": "station",
        "station_key": "https://radio.example/one",
    }
    args.update(overrides)
    return share_service.create_share(conn, **args)


def _rows(conn):
    return conn.execute("SELECT * FROM playlist_shares ORDER BY id").fetchall()


def test_sends_owned_favorite_with_minimal_snapshot(library):
    conn, alice, bob, _, profile, _ = library

    identifier = _send(conn, alice, profile)
    row = conn.execute("SELECT * FROM playlist_shares WHERE id = ?", (identifier,)).fetchone()

    assert row["sender_user_id"] == alice
    assert row["recipient_user_id"] == bob
    assert row["status"] == "pending"
    assert row["kind"] == "station"
    assert row["title"] == "Radio One"
    assert json.loads(row["snapshot_json"]) == {
        "version": 1,
        "stations": [{"name": "Radio One", "url": "https://radio.example/one"}],
    }


def test_playlist_send_preserves_order(library):
    conn, alice, _, _, profile, _ = library

    identifier = _send(
        conn,
        alice,
        profile,
        kind="playlist",
        station_key=None,
        playlist_name="Morning",
    )
    row = conn.execute("SELECT * FROM playlist_shares WHERE id = ?", (identifier,)).fetchone()

    assert row["title"] == "Morning"
    assert json.loads(row["snapshot_json"])["stations"] == [
        {"name": "Radio Two", "url": "https://radio.example/two"}
    ]


def test_playlist_member_can_be_sent_as_single_station(library):
    conn, alice, _, _, profile, _ = library

    identifier = _send(
        conn,
        alice,
        profile,
        station_key="https://radio.example/two",
    )
    assert identifier > 0


def test_case_insensitive_recipient_lookup(library):
    conn, alice, _, _, profile, _ = library

    identifier = _send(conn, alice, profile, recipient_username="BOB")
    assert identifier > 0


@pytest.mark.parametrize(
    "overrides",
    [
        {"recipient_username": "missing"},
        {"recipient_username": "alice"},
        {"recipient_username": ""},
        {"sender_user_id": 0},
        {"sender_user_id": True},
        {"source_profile_id": 0},
        {"source_profile_id": True},
        {"station_key": "https://radio.example/unknown"},
        {"kind": "invalid"},
        {"kind": "playlist", "playlist_name": "Morning"},
        {"kind": "station", "station_key": None},
    ],
)
def test_invalid_send_never_persists(library, overrides):
    conn, alice, _, _, profile, _ = library

    with pytest.raises(ValueError):
        _send(conn, alice, profile, **overrides)

    assert not _rows(conn)


def test_foreign_profile_cannot_be_used(library):
    conn, alice, _, _, _, foreign_profile = library

    with pytest.raises(ValueError):
        _send(conn, alice, foreign_profile)

    assert not _rows(conn)


def test_global_station_is_not_automatically_shareable(library):
    conn, alice, _, _, profile, _ = library

    db.upsert_station(
        conn,
        {"name": "Global", "url": "https://radio.example/global"},
    )
    conn.commit()

    with pytest.raises(ValueError, match="unavailable"):
        _send(
            conn,
            alice,
            profile,
            station_key="https://radio.example/global",
        )

    assert not _rows(conn)


def test_disabled_recipient_cannot_receive(library):
    conn, alice, bob, _, profile, _ = library
    db.set_user_approval_status(conn, bob, "disabled")
    conn.commit()

    with pytest.raises(ValueError, match="Recipient unavailable"):
        _send(conn, alice, profile)

    assert not _rows(conn)


def test_pending_recipient_cannot_receive(library):
    conn, alice, bob, _, profile, _ = library
    db.set_user_approval_status(conn, bob, "pending")
    conn.commit()

    with pytest.raises(ValueError, match="Recipient unavailable"):
        _send(conn, alice, profile)

    assert not _rows(conn)


def test_disabled_sender_cannot_send(library):
    conn, alice, _, _, profile, _ = library
    db.set_user_approval_status(conn, alice, "disabled")
    conn.commit()

    with pytest.raises(ValueError, match="Sender unavailable"):
        _send(conn, alice, profile)

    assert not _rows(conn)


def test_recipient_pending_quota_is_atomic(library, monkeypatch):
    conn, alice, _, _, profile, _ = library
    monkeypatch.setattr(share_service, "MAX_PENDING_TO_RECIPIENT", 2)

    _send(conn, alice, profile)
    _send(
        conn,
        alice,
        profile,
        station_key="https://radio.example/two",
    )

    with pytest.raises(ValueError, match="limit"):
        _send(
            conn,
            alice,
            profile,
            station_key="https://radio.example/three",
        )

    assert len(_rows(conn)) == 2


def test_daily_send_limit(library, monkeypatch):
    conn, alice, _, _, profile, _ = library
    monkeypatch.setattr(share_service, "MAX_SENT_PER_DAY", 2)

    now = datetime(2026, 11, 18, 20, 0, tzinfo=UTC)

    _send(conn, alice, profile, now=now)
    _send(
        conn,
        alice,
        profile,
        station_key="https://radio.example/two",
        now=now,
    )

    with pytest.raises(ValueError, match="limit"):
        _send(
            conn,
            alice,
            profile,
            station_key="https://radio.example/three",
            now=now,
        )

    assert len(_rows(conn)) == 2


def test_share_expires_after_seven_days(library):
    conn, alice, _, _, profile, _ = library
    now = datetime(2026, 11, 18, 20, 0, tzinfo=UTC)

    identifier = _send(conn, alice, profile, now=now)
    row = conn.execute(
        "SELECT created_at, expires_at FROM playlist_shares WHERE id = ?",
        (identifier,),
    ).fetchone()

    assert datetime.fromisoformat(row["created_at"]) == now
    assert datetime.fromisoformat(row["expires_at"]) == now + timedelta(days=7)


def test_failed_send_preserves_existing_share(library):
    conn, alice, _, _, profile, _ = library

    first = _send(conn, alice, profile)

    with pytest.raises(ValueError):
        _send(conn, alice, profile, station_key="https://invalid.example")

    assert [row["id"] for row in _rows(conn)] == [first]


def test_existing_transaction_is_not_committed(library):
    conn, alice, _, _, profile, _ = library

    conn.execute("BEGIN")
    with pytest.raises(ValueError, match="independent transaction"):
        _send(conn, alice, profile)

    assert conn.in_transaction
    conn.rollback()
    assert not _rows(conn)


def test_identical_pending_share_is_rejected(library):
    conn, alice, _, _, profile, _ = library

    first = _send(conn, alice, profile)

    with pytest.raises(ValueError, match="already pending"):
        _send(conn, alice, profile)

    assert [row["id"] for row in _rows(conn)] == [first]


def test_distinct_station_can_be_sent_to_same_recipient(library):
    conn, alice, _, _, profile, _ = library

    _send(conn, alice, profile)
    _send(
        conn,
        alice,
        profile,
        station_key="https://radio.example/two",
    )

    assert len(_rows(conn)) == 2


def test_global_inbox_limit_across_multiple_senders(library, monkeypatch):
    conn, alice, bob, charlie, profile, _ = library
    monkeypatch.setattr(share_service, "MAX_PENDING_INBOX", 2)

    charlie_profile = db.ensure_default_profile(conn, user_id=charlie)
    db.add_favorite_record(
        conn,
        {"name": "Radio One", "url": "https://radio.example/one"},
        profile_id=charlie_profile,
    )

    david = db.get_or_create_user(conn, "david", password_hash="test")
    david_profile = db.ensure_default_profile(conn, user_id=david)
    db.add_favorite_record(
        conn,
        {"name": "Radio One", "url": "https://radio.example/one"},
        profile_id=david_profile,
    )
    conn.commit()

    _send(conn, alice, profile)
    _send(conn, charlie, charlie_profile)

    with pytest.raises(ValueError, match="inbox limit"):
        _send(conn, david, david_profile)

    rows = _rows(conn)
    assert len(rows) == 2
    assert {row["sender_user_id"] for row in rows} == {alice, charlie}
    assert all(row["recipient_user_id"] == bob for row in rows)


def test_expired_pending_share_does_not_block_recommendation(library):
    conn, alice, _, _, profile, _ = library
    first_time = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    second_time = first_time + timedelta(days=8)

    first = _send(conn, alice, profile, now=first_time)
    second = _send(conn, alice, profile, now=second_time)

    assert second != first
    assert len(_rows(conn)) == 2


def test_global_inbox_limit_counts_only_unexpired_pending(library, monkeypatch):
    conn, alice, _, charlie, profile, _ = library
    monkeypatch.setattr(share_service, "MAX_PENDING_INBOX", 1)

    charlie_profile = db.ensure_default_profile(conn, user_id=charlie)
    db.add_favorite_record(
        conn,
        {"name": "Radio One", "url": "https://radio.example/one"},
        profile_id=charlie_profile,
    )
    conn.commit()

    old_time = datetime(2026, 11, 1, 12, 0, tzinfo=UTC)
    current_time = old_time + timedelta(days=8)

    _send(conn, alice, profile, now=old_time)
    _send(conn, charlie, charlie_profile, now=current_time)

    assert len(_rows(conn)) == 2
