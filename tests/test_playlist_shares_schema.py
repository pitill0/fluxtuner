# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Schema v6 user-to-user recommendation storage contracts."""

from __future__ import annotations

import sqlite3

import pytest

from fluxtuner.core import db


def _schema_objects(conn):
    return {
        tuple(row)
        for row in conn.execute(
            """
            SELECT type, name, tbl_name, sql
            FROM sqlite_master
            WHERE name NOT LIKE 'sqlite_%'
            """
        )
    }


def _v5_database(path):
    db.init_db(path)
    with db.connect(path) as conn:
        conn.execute("DROP TABLE playlist_shares")
        conn.execute("PRAGMA user_version = 5")
        conn.commit()


def test_v5_migration_preserves_data_and_matches_fresh_schema(tmp_path):
    legacy = tmp_path / "legacy.db"
    fresh = tmp_path / "fresh.db"
    _v5_database(legacy)

    with db.connect(legacy) as conn:
        alice = db.get_or_create_user(conn, "alice")
        profile = db.ensure_default_profile(conn, user_id=alice)
        conn.commit()

    db.init_db(legacy)
    db.init_db(fresh)

    with db.connect(legacy) as old, db.connect(fresh) as new:
        assert _schema_objects(old) == _schema_objects(new)
        assert old.execute("PRAGMA user_version").fetchone()[0] == 6
        assert db.get_user_by_username(old, "alice")["id"] == alice
        assert (
            old.execute("SELECT id FROM profiles WHERE id = ?", (profile,)).fetchone() is not None
        )
        assert old.execute("PRAGMA foreign_key_check").fetchall() == []


def test_v5_migration_is_idempotent(tmp_path):
    path = tmp_path / "library.db"
    _v5_database(path)
    db.init_db(path)

    with db.connect(path) as conn:
        before = _schema_objects(conn)

    db.init_db(path)

    with db.connect(path) as conn:
        assert _schema_objects(conn) == before


def test_failed_v5_migration_rolls_back_schema_and_version(tmp_path, monkeypatch):
    path = tmp_path / "library.db"
    _v5_database(path)
    original = db._create_playlist_share_schema

    def fail_after_creation(conn):
        original(conn)
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(db, "_create_playlist_share_schema", fail_after_creation)

    with db.connect(path) as conn, pytest.raises(RuntimeError, match="simulated"):
        db.migrate_schema(conn)

    with db.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        assert "playlist_shares" not in db.table_names(conn)


@pytest.fixture
def sharing_db(tmp_path):
    path = tmp_path / "sharing.db"
    db.init_db(path)

    with db.connect(path) as conn:
        alice = db.get_or_create_user(conn, "alice")
        bob = db.get_or_create_user(conn, "bob")
        profile = db.ensure_default_profile(conn, user_id=alice)
        conn.commit()
        yield conn, alice, bob, profile


def _insert(conn, sender, recipient, profile, **changes):
    fields = {
        "sender_user_id": sender,
        "recipient_user_id": recipient,
        "source_profile_id": profile,
        "kind": "playlist",
        "title": "Morning",
        "snapshot_json": '{"stations":[]}',
        "status": "pending",
        "created_at": "2026-11-18T19:00:00+00:00",
        "expires_at": "2026-11-25T19:00:00+00:00",
        "resolved_at": None,
    }
    fields.update(changes)
    columns = ", ".join(fields)
    placeholders = ", ".join("?" for _ in fields)
    return conn.execute(
        f"INSERT INTO playlist_shares ({columns}) VALUES ({placeholders})",
        tuple(fields.values()),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"kind": "invalid"},
        {"title": ""},
        {"title": " "},
        {"title": "x" * 121},
        {"snapshot_json": None},
        {"snapshot_json": "{invalid"},
        {"snapshot_json": "null"},
        {"snapshot_json": '"hello"'},
        {"snapshot_json": "[]"},
        {"snapshot_json": "é" * 600000},
        {"status": "unknown"},
        {"status": "accepted"},
        {"status": "rejected"},
        {"status": "expired"},
        {"resolved_at": "2026-11-18T20:00:00+00:00"},
    ],
)
def test_invalid_pending_share_is_rejected(sharing_db, changes):
    conn, alice, bob, profile = sharing_db
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, alice, bob, profile, **changes)


def test_foreign_source_profile_rejected_on_insert(sharing_db):
    conn, alice, bob, _ = sharing_db
    foreign_profile = db.ensure_default_profile(conn, user_id=bob)

    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, alice, bob, foreign_profile)


def test_foreign_source_profile_rejected_on_update(sharing_db):
    conn, alice, bob, profile = sharing_db
    foreign_profile = db.ensure_default_profile(conn, user_id=bob)
    identifier = _insert(conn, alice, bob, profile).lastrowid

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            UPDATE playlist_shares
            SET source_profile_id = ?
            WHERE id = ?
            """,
            (foreign_profile, identifier),
        )

    row = conn.execute(
        "SELECT source_profile_id FROM playlist_shares WHERE id = ?",
        (identifier,),
    ).fetchone()
    assert row["source_profile_id"] == profile


def test_sender_change_cannot_retain_foreign_profile(sharing_db):
    conn, alice, bob, profile = sharing_db
    charlie = db.get_or_create_user(conn, "charlie")
    identifier = _insert(conn, alice, bob, profile).lastrowid

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            UPDATE playlist_shares
            SET sender_user_id = ?
            WHERE id = ?
            """,
            (charlie, identifier),
        )


def test_self_sharing_is_rejected(sharing_db):
    conn, alice, _, profile = sharing_db
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, alice, alice, profile)


def test_unknown_recipient_is_rejected(sharing_db):
    conn, alice, _, profile = sharing_db
    with pytest.raises(sqlite3.IntegrityError):
        _insert(conn, alice, 99999999, profile)


@pytest.mark.parametrize("status", ["accepted", "rejected", "expired"])
def test_resolving_share_requires_snapshot_removal(sharing_db, status):
    conn, alice, bob, profile = sharing_db
    identifier = _insert(conn, alice, bob, profile).lastrowid

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            UPDATE playlist_shares
            SET status = ?, resolved_at = ?
            WHERE id = ?
            """,
            (status, "2026-11-19T00:00:00+00:00", identifier),
        )

    conn.execute(
        """
        UPDATE playlist_shares
        SET status = ?, snapshot_json = NULL, resolved_at = ?
        WHERE id = ?
        """,
        (status, "2026-11-19T00:00:00+00:00", identifier),
    )

    row = conn.execute(
        "SELECT status, snapshot_json FROM playlist_shares WHERE id = ?",
        (identifier,),
    ).fetchone()
    assert tuple(row) == (status, None)


def test_source_profile_deletion_preserves_pending_snapshot(sharing_db):
    conn, alice, bob, profile = sharing_db
    identifier = _insert(conn, alice, bob, profile).lastrowid

    conn.execute("DELETE FROM profiles WHERE id = ?", (profile,))

    row = conn.execute(
        """
        SELECT source_profile_id, status, snapshot_json
        FROM playlist_shares WHERE id = ?
        """,
        (identifier,),
    ).fetchone()

    assert row["source_profile_id"] is None
    assert row["status"] == "pending"
    assert row["snapshot_json"] == '{"stations":[]}'


def test_recipient_deletion_cascades(sharing_db):
    conn, alice, bob, profile = sharing_db
    _insert(conn, alice, bob, profile)

    conn.execute("DELETE FROM users WHERE id = ?", (bob,))

    assert conn.execute("SELECT COUNT(*) FROM playlist_shares").fetchone()[0] == 0
