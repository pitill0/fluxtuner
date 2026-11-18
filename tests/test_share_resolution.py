# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Security and transaction tests for recommendation resolution."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from fluxtuner.core import db
from fluxtuner.core.share_resolution import resolve_share
from fluxtuner.core.share_service import create_share

NOW = datetime(2026, 11, 18, 21, 0, tzinfo=UTC)
ONE = "https://radio.example/one"
TWO = "https://radio.example/two"


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "resolve.db"
    db.init_db(path)
    with db.connect(path) as conn:
        alice = db.get_or_create_user(conn, "alice", password_hash="test")
        bob = db.get_or_create_user(conn, "bob", password_hash="test")
        charlie = db.get_or_create_user(conn, "charlie", password_hash="test")
        ap = db.ensure_default_profile(conn, user_id=alice)
        bp = db.ensure_default_profile(conn, user_id=bob)
        cp = db.ensure_default_profile(conn, user_id=charlie)

        db.add_favorite_record(conn, {"name": "One", "url": ONE}, profile_id=ap)
        db.create_playlist_record(conn, "Morning", profile_id=ap)
        for name, url in (("One", ONE), ("Two", TWO)):
            db.add_station_to_playlist_record(
                conn,
                "Morning",
                {"name": name, "url": url},
                profile_id=ap,
            )
        conn.commit()
        yield conn, alice, bob, charlie, ap, bp, cp


def send(conn, alice, ap, kind="station", when=NOW):
    return create_share(
        conn,
        sender_user_id=alice,
        recipient_username="bob",
        source_profile_id=ap,
        kind=kind,
        station_key=ONE if kind == "station" else None,
        playlist_name="Morning" if kind == "playlist" else None,
        now=when,
    )


def accept(conn, bob, bp, share, **kwargs):
    return resolve_share(
        conn,
        recipient_user_id=bob,
        share_id=share,
        action="accept",
        destination_profile_id=bp,
        now=NOW,
        **kwargs,
    )


def reject(conn, bob, share):
    return resolve_share(
        conn,
        recipient_user_id=bob,
        share_id=share,
        action="reject",
        now=NOW,
    )


def state(conn, share):
    return conn.execute(
        "SELECT status, snapshot_json, resolved_at FROM playlist_shares WHERE id = ?",
        (share,),
    ).fetchone()


def test_accept_station_adds_only_recipient_favorite(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap)
    outcome = accept(conn, bob, bp, share)

    assert outcome["added_favorites"] == 1
    assert [x["url"] for x in db.list_favorites(conn, profile_id=bp)] == [ONE]
    assert state(conn, share)["status"] == "accepted"
    assert state(conn, share)["snapshot_json"] is None


def test_accept_playlist_preserves_order(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap, kind="playlist")
    outcome = accept(conn, bob, bp, share)

    assert outcome["added_to_playlist"] == 2
    assert db.get_playlist_record(conn, "Morning", profile_id=bp)["station_keys"] == [ONE, TWO]
    assert state(conn, share)["snapshot_json"] is None


def test_reject_does_not_import(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap)
    assert reject(conn, bob, share)["status"] == "rejected"
    assert db.list_favorites(conn, profile_id=bp) == []
    assert state(conn, share)["snapshot_json"] is None


def test_double_accept_is_denied(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap)
    accept(conn, bob, bp, share)

    with pytest.raises(ValueError, match="unavailable"):
        accept(conn, bob, bp, share)
    assert len(db.list_favorites(conn, profile_id=bp)) == 1


def test_reject_after_accept_is_denied(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap)
    accept(conn, bob, bp, share)

    with pytest.raises(ValueError, match="unavailable"):
        reject(conn, bob, share)
    assert state(conn, share)["status"] == "accepted"


def test_foreign_user_and_profile_are_denied(library):
    conn, alice, bob, charlie, ap, bp, cp = library
    share = send(conn, alice, ap)

    with pytest.raises(ValueError):
        accept(conn, charlie, cp, share)

    with pytest.raises(ValueError):
        accept(conn, bob, cp, share)

    assert state(conn, share)["status"] == "pending"
    assert db.list_favorites(conn, profile_id=cp) == []


def test_existing_playlist_conflict_is_atomic(library):
    conn, alice, bob, _, ap, bp, _ = library
    db.create_playlist_record(conn, "Morning", profile_id=bp)
    conn.commit()

    share = send(conn, alice, ap, kind="playlist")
    with pytest.raises(ValueError, match="already exists"):
        accept(conn, bob, bp, share)

    assert db.get_playlist_record(conn, "Morning", profile_id=bp)["station_keys"] == []
    assert db.list_favorites(conn, profile_id=bp) == []
    assert state(conn, share)["status"] == "pending"


def test_expired_share_cannot_be_accepted(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap, when=NOW - timedelta(days=8))

    with pytest.raises(ValueError, match="unavailable"):
        accept(conn, bob, bp, share)
    assert db.list_favorites(conn, profile_id=bp) == []


def test_invalid_stored_snapshot_rolls_back(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap)
    conn.execute(
        "UPDATE playlist_shares SET snapshot_json = ? WHERE id = ?",
        (
            json.dumps(
                {
                    "version": 1,
                    "stations": [
                        {"name": "Injected", "url": "https://radio.example/x?token=secret"}
                    ],
                }
            ),
            share,
        ),
    )
    conn.commit()

    with pytest.raises(ValueError, match="Invalid stored"):
        accept(conn, bob, bp, share)

    assert state(conn, share)["status"] == "pending"
    assert db.list_favorites(conn, profile_id=bp) == []


def test_import_failure_rolls_back_entire_acceptance(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap, kind="playlist")

    assert type(bp) is int and bp > 0
    conn.execute(
        f"""
        CREATE TRIGGER block_second_import
        BEFORE INSERT ON favorites
        WHEN NEW.profile_id = {bp}
        BEGIN
            SELECT RAISE(ABORT, 'import blocked');
        END
        """
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="import blocked"):
        accept(conn, bob, bp, share)

    assert db.list_favorites(conn, profile_id=bp) == []
    assert db.get_playlist_record(conn, "Morning", profile_id=bp) is None
    assert state(conn, share)["status"] == "pending"
    assert state(conn, share)["snapshot_json"] is not None


def test_inactive_recipient_cannot_resolve(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap)
    db.set_user_approval_status(conn, bob, "disabled")
    conn.commit()

    with pytest.raises(ValueError, match="unavailable"):
        reject(conn, bob, share)

    assert state(conn, share)["status"] == "pending"


def test_reject_requires_no_destination(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap)

    with pytest.raises(ValueError):
        resolve_share(
            conn,
            recipient_user_id=bob,
            share_id=share,
            action="reject",
            destination_profile_id=bp,
            now=NOW,
        )
    assert state(conn, share)["status"] == "pending"


def test_external_transaction_is_not_consumed(library):
    conn, alice, bob, _, ap, bp, _ = library
    share = send(conn, alice, ap)

    conn.execute("BEGIN")
    with pytest.raises(ValueError, match="independent transaction"):
        accept(conn, bob, bp, share)
    assert conn.in_transaction
    conn.rollback()
    assert state(conn, share)["status"] == "pending"
