# SPDX-License-Identifier: MIT
"""Regression coverage for station provenance schema migration."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from fluxtuner.core import db


def _make_v3_database(path):
    """Create a representative v3 schema without provenance tables."""
    db.init_db(path)

    with db.connect(path) as conn:
        conn.execute("DROP TABLE station_source_memberships")
        conn.execute("DROP TABLE station_sources")
        conn.execute("DROP TABLE remote_import_receipts")
        conn.execute("PRAGMA user_version = 3")
        conn.commit()


def _schema_objects(conn):
    return {
        (row["type"], row["name"], row["sql"])
        for row in conn.execute(
            """
            SELECT type, name, sql
            FROM sqlite_master
            WHERE type IN ('table', 'index')
              AND name NOT LIKE 'sqlite_%'
            """
        )
    }


def test_v3_upgrade_preserves_existing_library_data(tmp_path):
    path = tmp_path / "upgrade.db"
    _make_v3_database(path)

    with db.connect(path) as conn:
        profile_id = db.ensure_default_profile(conn)
        now = db.utc_now()

        conn.execute(
            """
            INSERT INTO stations (
                station_key, name, url, url_resolved,
                metadata_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "https://example.test/live",
                "Existing station",
                "https://example.test/live",
                "https://example.test/live",
                "{}",
                now,
                now,
            ),
        )
        station_id = conn.execute(
            "SELECT id FROM stations WHERE station_key = ?",
            ("https://example.test/live",),
        ).fetchone()["id"]

        conn.execute(
            """
            INSERT INTO favorites (
                profile_id, station_id, favorite_tags_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (profile_id, station_id, '["Keep"]', now, now),
        )
        conn.commit()

        station_before = tuple(
            conn.execute("SELECT * FROM stations WHERE id = ?", (station_id,)).fetchone()
        )
        favorite_before = tuple(
            conn.execute("SELECT * FROM favorites WHERE station_id = ?", (station_id,)).fetchone()
        )

    db.init_db(path)

    with db.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 4
        assert (
            tuple(conn.execute("SELECT * FROM stations WHERE id = ?", (station_id,)).fetchone())
            == station_before
        )
        assert (
            tuple(
                conn.execute(
                    "SELECT * FROM favorites WHERE station_id = ?", (station_id,)
                ).fetchone()
            )
            == favorite_before
        )
        assert conn.execute("SELECT COUNT(*) FROM station_sources").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 0
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_v3_upgrade_matches_fresh_v4_schema(tmp_path):
    legacy = tmp_path / "legacy.db"
    fresh = tmp_path / "fresh.db"

    _make_v3_database(legacy)
    db.init_db(fresh)
    db.init_db(legacy)

    with db.connect(legacy) as old_conn, db.connect(fresh) as fresh_conn:
        assert _schema_objects(old_conn) == _schema_objects(fresh_conn)
        assert old_conn.execute("PRAGMA user_version").fetchone()[0] == 4
        assert fresh_conn.execute("PRAGMA user_version").fetchone()[0] == 4


def test_failed_v3_upgrade_rolls_back_ddl_and_version(tmp_path, monkeypatch):
    path = tmp_path / "failure.db"
    _make_v3_database(path)

    original = db._create_station_provenance_schema

    def fail_after_ddl(conn):
        original(conn)
        raise RuntimeError("injected provenance schema failure")

    monkeypatch.setattr(db, "_create_station_provenance_schema", fail_after_ddl)

    with pytest.raises(RuntimeError, match="injected provenance schema failure"):
        db.init_db(path)

    with db.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 3
        tables = db.table_names(conn)
        assert "station_sources" not in tables
        assert "station_source_memberships" not in tables
        assert "remote_import_receipts" not in tables
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []


def test_concurrent_v3_initializers_create_one_consistent_schema(tmp_path):
    path = tmp_path / "concurrent.db"
    _make_v3_database(path)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: db.init_db(path), range(4)))

    assert results == [None] * 4

    with db.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 4
        assert "station_sources" in db.table_names(conn)
        assert "station_source_memberships" in db.table_names(conn)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
