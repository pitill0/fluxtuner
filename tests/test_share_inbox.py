# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Read-only recommendation inbox privacy and pagination tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from fluxtuner.core import db
from fluxtuner.core.share_inbox import list_shares
from fluxtuner.core.share_service import create_share

NOW = datetime(2026, 11, 18, 21, 0, tzinfo=UTC)


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "inbox.db"
    db.init_db(path)

    with db.connect(path) as conn:
        users = {}
        profiles = {}

        for name in ("alice", "bob", "charlie"):
            user_id = db.get_or_create_user(conn, name, password_hash="test")
            profile_id = db.ensure_default_profile(conn, user_id=user_id)
            users[name] = user_id
            profiles[name] = profile_id

            for number in range(4):
                db.add_favorite_record(
                    conn,
                    {
                        "name": f"{name} Radio {number}",
                        "url": f"https://radio.example/{name}/{number}",
                    },
                    profile_id=profile_id,
                )

        conn.commit()

        yield conn, users, profiles


def send(conn, users, profiles, sender, recipient, number=0, now=NOW):
    return create_share(
        conn,
        sender_user_id=users[sender],
        recipient_username=recipient,
        source_profile_id=profiles[sender],
        kind="station",
        station_key=f"https://radio.example/{sender}/{number}",
        now=now,
    )


def listing(conn, users, who, direction="inbox", **kwargs):
    return list_shares(
        conn,
        user_id=users[who],
        direction=direction,
        now=kwargs.pop("now", NOW),
        **kwargs,
    )


def test_recipient_sees_only_own_inbox(library):
    conn, users, profiles = library
    share_id = send(conn, users, profiles, "alice", "bob")

    bob = listing(conn, users, "bob")
    assert len(bob) == 1
    assert bob[0]["id"] == share_id
    assert bob[0]["counterpart_username"] == "alice"
    assert listing(conn, users, "charlie") == []


def test_sender_sees_only_own_sent_shares(library):
    conn, users, profiles = library
    share_id = send(conn, users, profiles, "alice", "bob")

    sent = listing(conn, users, "alice", direction="sent")
    assert [item["id"] for item in sent] == [share_id]
    assert sent[0]["counterpart_username"] == "bob"
    assert listing(conn, users, "charlie", direction="sent") == []


def test_metadata_never_exposes_snapshot(library):
    conn, users, profiles = library
    send(conn, users, profiles, "alice", "bob")

    for direction, who in (("inbox", "bob"), ("sent", "alice")):
        result = listing(conn, users, who, direction=direction)
        assert len(result) == 1

        item = result[0]
        assert set(item) == {
            "id",
            "kind",
            "title",
            "status",
            "created_at",
            "expires_at",
            "resolved_at",
            "counterpart_username",
        }
        assert "snapshot_json" not in str(item)
        assert "https://radio.example" not in str(item)


def test_pagination_is_stable_with_identical_timestamps(library):
    conn, users, profiles = library

    ids = [send(conn, users, profiles, "alice", "bob", number) for number in range(4)]

    first_page = listing(conn, users, "bob", limit=2)
    second_page = listing(conn, users, "bob", limit=2, offset=2)

    assert [item["id"] for item in first_page] == ids[::-1][:2]
    assert [item["id"] for item in second_page] == ids[::-1][2:]


def test_expired_pending_is_hidden(library):
    conn, users, profiles = library

    send(
        conn,
        users,
        profiles,
        "alice",
        "bob",
        now=NOW - timedelta(days=8),
    )

    assert listing(conn, users, "bob", status="pending") == []
    assert listing(conn, users, "bob", status="all") == []
    assert listing(conn, users, "alice", direction="sent") == []


def test_pending_filter(library):
    conn, users, profiles = library
    send(conn, users, profiles, "alice", "bob")

    assert len(listing(conn, users, "bob", status="pending")) == 1
    assert listing(conn, users, "bob", status="resolved") == []


def test_resolved_share_can_be_listed_without_snapshot(library):
    conn, users, profiles = library
    share_id = send(conn, users, profiles, "alice", "bob")

    conn.execute(
        """
        UPDATE playlist_shares
        SET status = 'rejected',
            snapshot_json = NULL,
            resolved_at = ?
        WHERE id = ?
        """,
        (NOW.isoformat(), share_id),
    )
    conn.commit()

    result = listing(conn, users, "bob", status="resolved")
    assert len(result) == 1
    assert result[0]["status"] == "rejected"
    assert result[0]["resolved_at"] == NOW.isoformat()
    assert listing(conn, users, "bob", status="pending") == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"direction": "invalid"},
        {"direction": "inbox", "status": "invalid"},
        {"direction": "inbox", "limit": 0},
        {"direction": "inbox", "limit": 51},
        {"direction": "inbox", "limit": True},
        {"direction": "inbox", "offset": -1},
        {"direction": "inbox", "offset": 10001},
        {"direction": "inbox", "offset": True},
        {"direction": "inbox", "now": datetime(2026, 11, 18)},
    ],
)
def test_invalid_listing_options_rejected(library, kwargs):
    conn, users, _ = library

    with pytest.raises(ValueError):
        list_shares(conn, user_id=users["bob"], **kwargs)


@pytest.mark.parametrize("identity", [0, -1, True, "2"])
def test_invalid_identity_rejected(library, identity):
    conn, _, _ = library

    with pytest.raises(ValueError):
        list_shares(conn, user_id=identity, direction="inbox", now=NOW)


def test_disabled_user_cannot_read_libraries(library):
    conn, users, profiles = library
    send(conn, users, profiles, "alice", "bob")
    db.set_user_approval_status(conn, users["bob"], "disabled")
    conn.commit()

    with pytest.raises(ValueError, match="User unavailable"):
        listing(conn, users, "bob")


def test_listing_does_not_mutate_database(library):
    conn, users, profiles = library
    send(conn, users, profiles, "alice", "bob")

    before = conn.total_changes
    in_transaction = conn.in_transaction

    listing(conn, users, "bob")
    listing(conn, users, "alice", direction="sent")

    assert conn.total_changes == before
    assert conn.in_transaction == in_transaction
