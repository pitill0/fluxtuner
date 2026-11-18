# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Concurrent recommendation resolution against independent SQLite connections."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime
from threading import Barrier

import pytest

from fluxtuner.core import db
from fluxtuner.core.share_resolution import resolve_share
from fluxtuner.core.share_service import create_share

NOW = datetime(2026, 11, 18, 21, 0, tzinfo=UTC)
ONE = "https://radio.example/one"
TWO = "https://radio.example/two"


def _prepare(path, kind):
    db.init_db(path)

    with closing(db.connect(path)) as conn:
        alice = db.get_or_create_user(conn, "alice", password_hash="test")
        bob = db.get_or_create_user(conn, "bob", password_hash="test")
        alice_profile = db.ensure_default_profile(conn, user_id=alice)
        bob_profile = db.ensure_default_profile(conn, user_id=bob)

        for name, url in (("One", ONE), ("Two", TWO)):
            db.add_favorite_record(
                conn,
                {"name": name, "url": url},
                profile_id=alice_profile,
            )

        if kind == "playlist":
            db.create_playlist_record(conn, "Shared Morning", profile_id=alice_profile)
            for name, url in (("One", ONE), ("Two", TWO)):
                db.add_station_to_playlist_record(
                    conn,
                    "Shared Morning",
                    {"name": name, "url": url},
                    profile_id=alice_profile,
                )

        conn.commit()

        share_id = create_share(
            conn,
            sender_user_id=alice,
            recipient_username="bob",
            source_profile_id=alice_profile,
            kind=kind,
            station_key=ONE if kind == "station" else None,
            playlist_name=("Shared Morning" if kind == "playlist" else None),
            now=NOW,
        )

    return alice, bob, alice_profile, bob_profile, share_id


def _race(path, bob, bob_profile, share_id, actions):
    barrier = Barrier(2)

    def worker(action):
        barrier.wait(timeout=15)

        try:
            with closing(db.connect(path)) as conn:
                result = resolve_share(
                    conn,
                    recipient_user_id=bob,
                    share_id=share_id,
                    action=action,
                    destination_profile_id=(bob_profile if action == "accept" else None),
                    now=NOW,
                )
                return "success", action, result["status"]
        except ValueError as exc:
            return "rejected", action, str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        return list(executor.map(worker, actions))


@pytest.mark.parametrize(
    ("kind", "actions"),
    [
        ("station", ("accept", "accept")),
        ("playlist", ("accept", "accept")),
        ("station", ("accept", "reject")),
        ("playlist", ("accept", "reject")),
        ("playlist", ("reject", "accept")),
        ("station", ("reject", "reject")),
    ],
)
def test_resolution_is_single_winner_and_atomic(tmp_path, kind, actions):
    path = tmp_path / "resolution-race.db"
    alice, bob, alice_profile, bob_profile, share_id = _prepare(path, kind)

    results = _race(path, bob, bob_profile, share_id, actions)

    winners = [result for result in results if result[0] == "success"]
    losers = [result for result in results if result[0] == "rejected"]

    assert len(winners) == 1, results
    assert len(losers) == 1, results
    assert losers[0][2] == "Recommendation unavailable."

    with closing(db.connect(path)) as conn:
        share = conn.execute(
            """
            SELECT status, snapshot_json, resolved_at
            FROM playlist_shares
            WHERE id = ?
            """,
            (share_id,),
        ).fetchone()

        assert share is not None
        assert share["status"] == winners[0][2]
        assert share["snapshot_json"] is None
        assert share["resolved_at"] == NOW.isoformat()

        bob_urls = {row["url"] for row in db.list_favorites(conn, profile_id=bob_profile)}
        bob_playlists = db.list_playlists(conn, profile_id=bob_profile)

        if share["status"] == "accepted":
            assert bob_urls == ({ONE, TWO} if kind == "playlist" else {ONE})

            if kind == "playlist":
                assert len(bob_playlists) == 1
                imported = db.get_playlist_record(
                    conn,
                    "Shared Morning",
                    profile_id=bob_profile,
                )
                assert imported is not None
                assert imported["station_keys"] == [ONE, TWO]
            else:
                assert bob_playlists == []
        else:
            assert bob_urls == set()
            assert bob_playlists == []

        sender_urls = {row["url"] for row in db.list_favorites(conn, profile_id=alice_profile)}
        assert sender_urls == {ONE, TWO}

        if kind == "playlist":
            original = db.get_playlist_record(
                conn,
                "Shared Morning",
                profile_id=alice_profile,
            )
            assert original is not None
            assert original["station_keys"] == [ONE, TWO]

        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_resolution_race_never_leaves_pending_snapshot(tmp_path):
    path = tmp_path / "single-consumption.db"
    _, bob, _, bob_profile, share_id = _prepare(path, "playlist")

    results = _race(
        path,
        bob,
        bob_profile,
        share_id,
        ("accept", "reject"),
    )

    assert sum(result[0] == "success" for result in results) == 1

    with closing(db.connect(path)) as conn:
        row = conn.execute(
            """
            SELECT status, snapshot_json
            FROM playlist_shares
            WHERE id = ?
            """,
            (share_id,),
        ).fetchone()

        assert row["status"] in ("accepted", "rejected")
        assert row["snapshot_json"] is None

        with pytest.raises(ValueError, match="unavailable"):
            resolve_share(
                conn,
                recipient_user_id=bob,
                share_id=share_id,
                action="reject",
                now=NOW,
            )
