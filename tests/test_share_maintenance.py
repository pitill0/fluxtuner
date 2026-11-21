# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Recommendation cleanup integration with existing Web maintenance."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from fluxtuner.core import db, share_lifecycle
from fluxtuner.core.share_service import create_share
from fluxtuner.web import maintenance

NOW = datetime(2026, 11, 18, 21, 0, tzinfo=UTC)


@pytest.fixture
def library(tmp_path, monkeypatch):
    path = tmp_path / "maintenance.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    db.init_db(path)

    with db.connect(path) as conn:
        alice = db.get_or_create_user(conn, "alice", password_hash="test")
        db.get_or_create_user(conn, "bob", password_hash="test")
        profile = db.ensure_default_profile(conn, user_id=alice)

        for index in range(2):
            db.add_favorite_record(
                conn,
                {
                    "name": f"Radio {index}",
                    "url": f"https://radio.example/{index}",
                },
                profile_id=profile,
            )
        conn.commit()

        yield path, alice, profile


def send(alice, profile, index, when):
    with db.connect() as conn:
        return create_share(
            conn,
            sender_user_id=alice,
            recipient_username="bob",
            source_profile_id=profile,
            kind="station",
            station_key=f"https://radio.example/{index}",
            now=when,
        )


def read_share(identifier):
    with db.connect() as conn:
        return conn.execute(
            "SELECT * FROM playlist_shares WHERE id = ?",
            (identifier,),
        ).fetchone()


def test_existing_maintenance_clears_expired_snapshots(library):
    _, alice, profile = library

    expired = send(alice, profile, 0, NOW - timedelta(days=8))
    active = send(alice, profile, 1, NOW)

    result = maintenance.run_auth_maintenance(now=NOW)

    assert result.expired_recommendations == 1
    assert read_share(expired)["status"] == "expired"
    assert read_share(expired)["snapshot_json"] is None

    assert read_share(active)["status"] == "pending"
    assert read_share(active)["snapshot_json"] is not None

    assert maintenance.run_auth_maintenance(now=NOW).expired_recommendations == 0


def test_maintenance_purges_old_resolved_recommendations(library):
    _, alice, profile = library
    old = send(alice, profile, 0, NOW - timedelta(days=40))
    recent = send(alice, profile, 1, NOW - timedelta(days=10))
    with db.connect() as conn:
        for identifier, age in ((old, 31), (recent, 29)):
            conn.execute(
                "UPDATE playlist_shares SET status = 'accepted', snapshot_json = NULL, "
                "resolved_at = ? WHERE id = ?",
                ((NOW - timedelta(days=age)).isoformat(), identifier),
            )
        conn.commit()

    result = maintenance.run_auth_maintenance(now=NOW)
    assert result.purged_recommendations == 1
    assert read_share(old) is None
    assert read_share(recent) is not None
    assert maintenance.run_auth_maintenance(now=NOW).purged_recommendations == 0


def test_expiry_uses_independent_idle_transaction(library, monkeypatch):
    _, alice, profile = library

    send(alice, profile, 0, NOW - timedelta(days=8))
    original = share_lifecycle.expire_shares
    observed = []

    def checked_expiry(conn, *, now=None, batch_size=100):
        observed.append(conn.in_transaction)
        return original(conn, now=now, batch_size=batch_size)

    monkeypatch.setattr(share_lifecycle, "expire_shares", checked_expiry)

    result = maintenance.run_auth_maintenance(now=NOW)

    assert observed == [False]
    assert result.expired_recommendations == 1


def test_failed_expiry_does_not_block_auth_maintenance(library, monkeypatch, caplog):
    _, alice, profile = library
    expired = send(alice, profile, 0, NOW - timedelta(days=8))

    monkeypatch.setattr(maintenance, "_last_auth_maintenance_monotonic", None)

    def broken_expiry(conn, *, now=None, batch_size=100):
        raise RuntimeError("synthetic share cleanup failure")

    original = share_lifecycle.expire_shares
    monkeypatch.setattr(share_lifecycle, "expire_shares", broken_expiry)

    with caplog.at_level("ERROR"):
        assert maintenance.run_auth_maintenance_if_due(
            now=NOW,
            monotonic_now=1000.0,
        )

    assert maintenance._last_auth_maintenance_monotonic == 1000.0
    assert any(
        "Recommendation expiry maintenance failed" in record.message and record.exc_info is not None
        for record in caplog.records
    )

    # Optional maintenance failed: snapshot is not falsely marked
    # resolved or deleted.
    assert read_share(expired)["status"] == "pending"
    assert read_share(expired)["snapshot_json"] is not None

    # The normal throttle still applies to successful auth maintenance.
    assert not maintenance.run_auth_maintenance_if_due(
        now=NOW,
        monotonic_now=1001.0,
    )

    # A subsequent maintenance window can retry the failed cleanup.
    monkeypatch.setattr(share_lifecycle, "expire_shares", original)

    assert maintenance.run_auth_maintenance_if_due(
        now=NOW,
        monotonic_now=1000.0 + maintenance.AUTH_MAINTENANCE_INTERVAL_SECONDS,
    )

    assert read_share(expired)["status"] == "expired"
    assert read_share(expired)["snapshot_json"] is None


def test_direct_maintenance_returns_safe_result_on_cleanup_error(library, monkeypatch, caplog):
    def broken_expiry(conn, *, now=None, batch_size=100):
        raise RuntimeError("synthetic cleanup error")

    monkeypatch.setattr(share_lifecycle, "expire_shares", broken_expiry)

    with caplog.at_level("ERROR"):
        result = maintenance.run_auth_maintenance(now=NOW)

    assert result.expired_recommendations == 0
    assert any(
        "Recommendation expiry maintenance failed" in record.message and record.exc_info is not None
        for record in caplog.records
    )
