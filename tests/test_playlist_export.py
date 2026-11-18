"""Tests for read-only, user-scoped playlist export resolution."""

from __future__ import annotations

import pytest

from fluxtuner.core import db
from fluxtuner.core.exporters import export_m3u, export_pls
from fluxtuner.core.m3u_import import parse_m3u, parse_pls
from fluxtuner.core.playlist_export import resolve_playlist_entries


@pytest.fixture
def library(tmp_path):
    path = tmp_path / "library.db"
    db.init_db(path)

    with db.connect(path) as conn:
        alice = db.get_or_create_user(conn, "alice", password_hash="test")
        bob = db.get_or_create_user(conn, "bob", password_hash="test")
        alice_profile = db.ensure_default_profile(conn, user_id=alice)
        bob_profile = db.ensure_default_profile(conn, user_id=bob)

        db.create_playlist_record(conn, "Morning", profile_id=alice_profile)
        db.add_station_to_playlist_record(
            conn,
            "Morning",
            {"name": "Second", "url": "https://radio.example/second"},
            profile_id=alice_profile,
        )
        db.add_station_to_playlist_record(
            conn,
            "Morning",
            {"name": "First", "url": "https://radio.example/first"},
            profile_id=alice_profile,
        )

        station_id = conn.execute(
            "SELECT id FROM stations WHERE station_key = ?",
            ("https://radio.example/second",),
        ).fetchone()[0]
        now = db.utc_now()
        conn.execute(
            """
            INSERT INTO favorites (
                profile_id, station_id, custom_name,
                favorite_tags_json, created_at, updated_at
            ) VALUES (?, ?, ?, '[]', ?, ?)
            """,
            (alice_profile, station_id, "My Second", now, now),
        )
        conn.commit()
        yield conn, alice, alice_profile, bob, bob_profile


def test_resolves_order_and_profile_custom_names(library):
    conn, alice, profile, _, _ = library
    entries = resolve_playlist_entries(
        conn, user_id=alice, profile_id=profile, playlist_name="Morning"
    )
    assert [(entry.name, entry.url) for entry in entries] == [
        ("My Second", "https://radio.example/second"),
        ("First", "https://radio.example/first"),
    ]


@pytest.mark.parametrize(
    ("exporter", "parser"),
    [(export_m3u, parse_m3u), (export_pls, parse_pls)],
)
def test_resolved_playlist_round_trips(library, exporter, parser):
    conn, alice, profile, _, _ = library
    entries = resolve_playlist_entries(
        conn, user_id=alice, profile_id=profile, playlist_name="Morning"
    )
    preview = parser(exporter(entries))
    assert [(entry.name, entry.url) for entry in preview.entries] == [
        (entry.name, entry.url) for entry in entries
    ]
    assert not preview.issues


def test_foreign_profile_is_not_accessible(library):
    conn, alice, _, _, bob_profile = library
    with pytest.raises(ValueError, match="unavailable"):
        resolve_playlist_entries(
            conn, user_id=alice, profile_id=bob_profile, playlist_name="Morning"
        )


def test_foreign_user_cannot_read_playlist(library):
    conn, _, alice_profile, bob, _ = library
    with pytest.raises(ValueError, match="unavailable"):
        resolve_playlist_entries(
            conn, user_id=bob, profile_id=alice_profile, playlist_name="Morning"
        )


def test_missing_playlist_is_rejected(library):
    conn, alice, profile, _, _ = library
    with pytest.raises(ValueError, match="unavailable"):
        resolve_playlist_entries(conn, user_id=alice, profile_id=profile, playlist_name="Missing")


def test_invalid_identity_is_rejected(library):
    conn, _, profile, _, _ = library
    with pytest.raises(ValueError):
        resolve_playlist_entries(conn, user_id=0, profile_id=profile, playlist_name="Morning")


def test_empty_playlist_returns_no_entries(library):
    conn, alice, profile, _, _ = library
    db.create_playlist_record(conn, "Empty", profile_id=profile)
    conn.commit()

    entries = resolve_playlist_entries(
        conn, user_id=alice, profile_id=profile, playlist_name="Empty"
    )
    assert entries == ()


def test_resolution_does_not_write_to_database(library):
    conn, alice, profile, _, _ = library
    before_changes = conn.total_changes
    before_transaction = conn.in_transaction

    entries = resolve_playlist_entries(
        conn, user_id=alice, profile_id=profile, playlist_name="Morning"
    )

    assert len(entries) == 2
    assert conn.total_changes == before_changes
    assert conn.in_transaction == before_transaction


def test_missing_playlist_does_not_create_records(library):
    conn, alice, profile, _, _ = library
    before_changes = conn.total_changes
    before_profiles = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]

    with pytest.raises(ValueError, match="unavailable"):
        resolve_playlist_entries(conn, user_id=alice, profile_id=profile, playlist_name="Missing")

    assert conn.total_changes == before_changes
    assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == before_profiles
