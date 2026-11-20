"""Publication consent belongs to a favorite, not its shared station."""

import pytest

from fluxtuner.core import db
from fluxtuner.core.public_station_visibility import (
    list_public_station_ids,
    set_station_publication,
)


def _owner(conn, username):
    now = db.utc_now()
    cursor = conn.execute(
        """
        INSERT INTO users (username, password_hash, is_active, approval_status, created_at, updated_at)
        VALUES (?, 'test-hash', 1, 'approved', ?, ?)
        """,
        (username, now, now),
    )
    user_id = int(cursor.lastrowid)
    profile_id = db.get_or_create_profile(conn, "default", user_id=user_id)
    return user_id, profile_id


def _favorite(conn, profile_id, station_id):
    now = db.utc_now()
    conn.execute(
        """
        INSERT INTO favorites (profile_id, station_id, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (profile_id, station_id, now, now),
    )


def test_opt_in_is_scoped_to_owned_favorite_and_cascades(tmp_path):
    path = tmp_path / "publication.db"
    db.init_db(path)
    with db.connect(path) as conn:
        alice_id, alice_profile = _owner(conn, "alice-visible")
        bob_id, bob_profile = _owner(conn, "bob-visible")
        station_id = db.upsert_station(
            conn, {"name": "Example", "url": "https://radio.example.test/stream"}
        )
        _favorite(conn, alice_profile, station_id)
        _favorite(conn, bob_profile, station_id)

        assert list_public_station_ids(conn) == []
        with pytest.raises(ValueError, match="Station unavailable"):
            set_station_publication(
                conn,
                user_id=bob_id,
                profile_id=alice_profile,
                station_id=station_id,
                published=True,
            )
        set_station_publication(
            conn,
            user_id=alice_id,
            profile_id=alice_profile,
            station_id=station_id,
            published=True,
        )
        assert list_public_station_ids(conn) == [station_id]
        assert conn.execute("SELECT COUNT(*) FROM public_station_opt_ins").fetchone()[0] == 1

        # Another account has no implicit permission, even for the same station.
        set_station_publication(
            conn,
            user_id=bob_id,
            profile_id=bob_profile,
            station_id=station_id,
            published=False,
        )
        assert list_public_station_ids(conn) == [station_id]
        conn.execute(
            "DELETE FROM favorites WHERE profile_id = ? AND station_id = ?",
            (alice_profile, station_id),
        )
        assert list_public_station_ids(conn) == []
        assert conn.execute("SELECT COUNT(*) FROM public_station_opt_ins").fetchone()[0] == 0


def test_secret_url_rejected_and_upgrade_preserves_library(tmp_path):
    path = tmp_path / "upgrade.db"
    db.init_db(path)
    with db.connect(path) as conn:
        user_id, profile_id = _owner(conn, "safety-test")
        station_id = db.upsert_station(
            conn, {"name": "Private", "url": "https://example.test/live?token=secret"}
        )
        _favorite(conn, profile_id, station_id)
        with pytest.raises(ValueError, match="not eligible"):
            set_station_publication(
                conn,
                user_id=user_id,
                profile_id=profile_id,
                station_id=station_id,
                published=True,
            )
        assert list_public_station_ids(conn) == []
        conn.execute("DROP TABLE public_station_opt_ins")
        conn.execute("PRAGMA user_version = 7")
        conn.commit()

    db.init_db(path)
    with db.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 8
        assert conn.execute("SELECT COUNT(*) FROM favorites").fetchone()[0] >= 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert list_public_station_ids(conn) == []
