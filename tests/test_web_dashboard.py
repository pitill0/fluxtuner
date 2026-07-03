# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from fluxtuner import __app_name__, __version__
from fluxtuner.core import db, favorites, history, manual_playlists
from fluxtuner.web import auth
from fluxtuner.web.dashboard import (
    admin_user_counts,
    dashboard_user_payload,
    server_health_payload,
)

VALID_PASSWORD = "correct horse battery staple"


def configure_db(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    monkeypatch.setattr(favorites, "FAVORITES_FILE", tmp_path / "favorites.json")
    monkeypatch.setattr(history, "HISTORY_FILE", tmp_path / "history.json")
    monkeypatch.setattr(manual_playlists, "PLAYLISTS_FILE", tmp_path / "playlists.json")
    db.init_db()


def create_user(conn, username: str, *, is_admin: bool = False) -> int:
    user_id = db.get_or_create_user(
        conn,
        username,
        password_hash=auth.hash_password(VALID_PASSWORD),
        is_admin=is_admin,
    )
    db.ensure_default_profile(conn, user_id=user_id)
    return user_id


def test_server_health_payload() -> None:
    assert server_health_payload() == {
        "status": "ok",
        "app": __app_name__,
        "version": __version__,
        "mode": "web",
    }


def test_admin_user_counts_include_users_pending_and_password_changes(
    tmp_path, monkeypatch
) -> None:
    configure_db(tmp_path, monkeypatch)

    with db.connect() as conn:
        create_user(conn, "admin", is_admin=True)
        alice_id = create_user(conn, "alice")
        db.create_pending_user(
            conn,
            "pending",
            password_hash=auth.hash_password(VALID_PASSWORD),
        )
        db.upsert_pending_password_change_request(
            conn,
            alice_id,
            password_hash=auth.hash_password("correct horse battery staple updated"),
            note="reset please",
            expires_at="2999-01-01T00:00:00+00:00",
        )
        conn.commit()

        counts = admin_user_counts(conn)

    assert counts["users_count"] >= 4
    assert counts["pending_users_count"] == 1
    assert counts["pending_password_change_requests_count"] == 1
    assert counts["users_created_today"] >= 4
    assert counts["users_created_7_days"] >= 4
    assert counts["users_created_30_days"] >= 4


def test_dashboard_user_payload_empty_user_data(tmp_path, monkeypatch) -> None:
    configure_db(tmp_path, monkeypatch)

    with db.connect() as conn:
        user_id = create_user(conn, "alice")
        conn.commit()

    payload = dashboard_user_payload(user_id, "default")

    assert payload == {
        "favorites_count": 0,
        "playlists_count": 0,
        "playlist_stations_count": 0,
        "history_count": 0,
        "recent_history": [],
        "favorite_highlights": [],
    }
