# SPDX-License-Identifier: MIT
"""Transactional remote subscription storage contracts."""

from __future__ import annotations

import sqlite3

import pytest

from fluxtuner.core import db
from fluxtuner.core.m3u_import import M3UEntry
from fluxtuner.core.remote_subscription_store import (
    apply_update,
    create_subscription,
    delete_subscription,
    get_entries,
    get_subscription,
    list_subscriptions,
    preview_update,
)


def entry(name: str, suffix: str) -> M3UEntry:
    return M3UEntry(name, f"https://stream.example/{suffix}")


def setup(tmp_path):
    path = tmp_path / "subscriptions.db"
    db.init_db(path)
    conn = db.connect(path)
    user_id = db.ensure_default_user(conn)
    profile_a = db.ensure_default_profile(conn, user_id=user_id)
    profile_b = db.get_or_create_profile(
        conn, "second", user_id=user_id,
    )
    conn.commit()
    return conn, profile_a, profile_b


def test_create_and_refresh_preserve_user_data(tmp_path):
    conn, a, b = setup(tmp_path)
    try:
        source = create_subscription(
            conn, profile_id=a,
            catalog_url="https://catalog.example/list.m3u",
            entries=[entry("Original", "one"), entry("Gone", "two")],
        )
        conn.commit()
        assert len(get_entries(conn, profile_id=a, source_id=source)) == 2
        assert not list_subscriptions(conn, profile_id=b)

        station_id = conn.execute(
            "SELECT id FROM stations WHERE station_key = ?",
            ("https://stream.example/one",),
        ).fetchone()[0]
        now = db.utc_now()
        conn.execute(
            """
            INSERT INTO favorites (
                profile_id, station_id, custom_name,
                favorite_tags_json, created_at, updated_at
            ) VALUES (?, ?, 'My name', '["tag"]', ?, ?)
            """,
            (a, station_id, now, now),
        )
        conn.commit()

        revision, diff = preview_update(
            conn, profile_id=a, source_id=source,
            incoming=[entry("Renamed", "one"), entry("New", "three")],
        )
        assert revision == 1
        assert (len(diff.added), len(diff.removed), len(diff.changed)) == (1, 1, 1)

        with pytest.raises(ValueError):
            apply_update(
                conn, profile_id=b, source_id=source,
                expected_revision=revision,
                entries=[entry("Foreign", "four")],
            )

        assert apply_update(
            conn, profile_id=a, source_id=source,
            expected_revision=revision,
            entries=[entry("Renamed", "one"), entry("New", "three")],
        ) == diff
        conn.commit()

        assert get_subscription(
            conn, profile_id=a, source_id=source,
        )["revision"] == 2
        assert [s.name for s in get_entries(
            conn, profile_id=a, source_id=source,
        )] == ["Renamed", "New"]
        with pytest.raises(ValueError, match="Stale"):
            apply_update(
                conn, profile_id=a, source_id=source,
                expected_revision=revision,
                entries=[entry("Other", "five")],
            )

        preserved = conn.execute(
            """
            SELECT custom_name, favorite_tags_json
            FROM favorites
            WHERE profile_id = ? AND station_id = ?
            """,
            (a, station_id),
        ).fetchone()
        assert tuple(preserved) == ("My name", '["tag"]')

        delete_subscription(conn, profile_id=a, source_id=source)
        conn.commit()
        assert not list_subscriptions(conn, profile_id=a)
        assert conn.execute(
            "SELECT COUNT(*) FROM favorites WHERE profile_id = ?",
            (a,),
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_failed_update_and_rollback_keep_previous_catalog(tmp_path):
    conn, a, _ = setup(tmp_path)
    try:
        source = create_subscription(
            conn, profile_id=a,
            catalog_url="https://catalog.example/list.m3u",
            entries=[entry("One", "one")],
        )
        conn.commit()

        with pytest.raises(ValueError):
            apply_update(
                conn, profile_id=a, source_id=source,
                expected_revision=1, entries=[],
            )

        assert [e.name for e in get_entries(
            conn, profile_id=a, source_id=source,
        )] == ["One"]
        assert get_subscription(
            conn, profile_id=a, source_id=source,
        )["revision"] == 1

        apply_update(
            conn, profile_id=a, source_id=source,
            expected_revision=1,
            entries=[entry("Two", "two")],
        )
        conn.rollback()

        assert [e.name for e in get_entries(
            conn, profile_id=a, source_id=source,
        )] == ["One"]
        assert get_subscription(
            conn, profile_id=a, source_id=source,
        )["revision"] == 1
    finally:
        conn.close()


def test_duplicate_and_foreign_subscription_rejected(tmp_path):
    conn, a, b = setup(tmp_path)
    try:
        source = create_subscription(
            conn, profile_id=a,
            catalog_url="https://catalog.example/list.m3u",
            entries=[entry("One", "one")],
        )
        conn.commit()

        with pytest.raises(sqlite3.IntegrityError):
            create_subscription(
                conn, profile_id=a,
                catalog_url="https://catalog.example/list.m3u",
                entries=[entry("Two", "two")],
            )

        with pytest.raises(ValueError):
            get_subscription(conn, profile_id=b, source_id=source)

        with pytest.raises(ValueError):
            delete_subscription(conn, profile_id=b, source_id=source)

        assert len(get_entries(
            conn, profile_id=a, source_id=source,
        )) == 1
    finally:
        conn.rollback()
        conn.close()



def test_refresh_preserves_first_observation_for_survivors(tmp_path):
    conn, profile, _ = setup(tmp_path)
    try:
        source = create_subscription(
            conn,
            profile_id=profile,
            catalog_url="https://catalog.example/history.m3u",
            entries=[entry("Keep", "keep"), entry("Remove", "remove")],
        )
        conn.commit()

        first_seen = "2020-01-01T00:00:00+00:00"
        conn.execute(
            """
            UPDATE station_source_memberships
            SET first_observed_at = ?
            WHERE source_id = ?
            """,
            (first_seen, source),
        )
        conn.commit()

        apply_update(
            conn,
            profile_id=profile,
            source_id=source,
            expected_revision=1,
            entries=[entry("Keep renamed", "keep"), entry("New", "new")],
        )
        conn.commit()

        rows = conn.execute(
            """
            SELECT stations.station_key, memberships.first_observed_at
            FROM station_source_memberships AS memberships
            JOIN stations ON stations.id = memberships.station_id
            WHERE memberships.source_id = ?
            """,
            (source,),
        ).fetchall()

        history = {
            row["station_key"]: row["first_observed_at"]
            for row in rows
        }
        assert len(history) == 2
        assert history["https://stream.example/keep"] == first_seen
        assert "https://stream.example/remove" not in history
        assert "https://stream.example/new" in history
        assert history["https://stream.example/new"] != first_seen
    finally:
        conn.close()
