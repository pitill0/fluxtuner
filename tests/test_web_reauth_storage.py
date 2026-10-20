# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Schema compatibility tests for persistent reauthentication attempts."""

from fluxtuner.core import db


def test_fresh_database_has_reauthentication_storage(tmp_path) -> None:
    path = tmp_path / "fresh.db"

    db.init_db(path)

    with db.connect(path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(web_reauth_attempts)"
            )
        }

    assert version == 3
    assert {
        "id",
        "user_id",
        "client_key",
        "status",
        "attempted_at",
        "expires_at",
    } <= columns


def test_v2_upgrade_preserves_existing_users(tmp_path) -> None:
    path = tmp_path / "upgrade.db"

    # Construct a populated database with the previous v2 schema.
    with db.connect(path) as conn:
        db.create_schema(conn)
        conn.execute("PRAGMA user_version = 2")
        db.get_or_create_user(
            conn,
            "migration-alice",
            password_hash="test-hash-not-a-credential",
            is_active=True,
        )
        conn.commit()

    db.init_db(path)

    with db.connect(path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        user = db.get_user_by_username(conn, "migration-alice")
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        indexes = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            )
        }

    assert version == 3
    assert user is not None
    assert user["password_hash"] == "test-hash-not-a-credential"
    assert "web_reauth_attempts" in tables
    assert "idx_web_reauth_attempts_failed_window" in indexes
    assert "idx_web_reauth_attempts_pending_lease" in indexes
    assert "idx_web_reauth_attempts_lookup" not in indexes
    assert "idx_web_reauth_attempts_expires" in indexes
