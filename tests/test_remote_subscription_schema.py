# SPDX-License-Identifier: MIT
"""Schema contract for profile-owned remote subscriptions."""

from __future__ import annotations

import sqlite3

from fluxtuner.core import db


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def test_fresh_schema_has_remote_subscription_tables() -> None:
    with _connection() as conn:
        db.create_schema(conn)
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "remote_catalog_subscriptions" in tables
        assert "remote_catalog_entries" in tables


def test_v4_schema_migrates_to_v5_without_losing_existing_rows() -> None:
    with _connection() as conn:
        db.create_schema(conn)

        # Simulate an existing v4 database, which lacks the new tables.
        conn.execute("DROP TABLE remote_catalog_entries")
        conn.execute("DROP TABLE remote_catalog_subscriptions")
        conn.execute("PRAGMA user_version = 4")
        conn.commit()

        db.migrate_schema(conn)

        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert "station_sources" in tables
        assert "remote_catalog_subscriptions" in tables
        assert "remote_catalog_entries" in tables


def test_subscription_tables_have_cascade_foreign_keys() -> None:
    with _connection() as conn:
        db.create_schema(conn)

        subscription_fks = conn.execute(
            "PRAGMA foreign_key_list(remote_catalog_subscriptions)"
        ).fetchall()
        entry_fks = conn.execute(
            "PRAGMA foreign_key_list(remote_catalog_entries)"
        ).fetchall()

        assert any(
            row["table"] == "station_sources"
            and row["on_delete"] == "CASCADE"
            for row in subscription_fks
        )
        assert any(
            row["table"] == "remote_catalog_subscriptions"
            and row["on_delete"] == "CASCADE"
            for row in entry_fks
        )


def test_v4_migration_preserves_existing_profile_and_source() -> None:
    from fluxtuner.core import station_provenance as provenance

    with _connection() as conn:
        db.create_schema(conn)
        user_id = db.ensure_default_user(conn)
        profile_id = db.ensure_default_profile(conn, user_id=user_id)
        source_id = provenance.create_source(
            conn,
            profile_id=profile_id,
            kind="remote_collection",
            display_name="Existing catalog",
        )

        conn.execute("DROP TABLE remote_catalog_entries")
        conn.execute("DROP TABLE remote_catalog_subscriptions")
        conn.execute("PRAGMA user_version = 4")
        conn.commit()

        db.migrate_schema(conn)

        assert conn.execute("PRAGMA user_version").fetchone()[0] == 5
        assert conn.execute(
            "SELECT name FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()["name"] == db.DEFAULT_PROFILE_NAME

        assert provenance.get_source(
            conn,
            profile_id=profile_id,
            source_id=source_id,
        )["display_name"] == "Existing catalog"
