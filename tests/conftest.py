from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fluxtuner import config
from fluxtuner.core import db, favorites, history, manual_playlists
from fluxtuner.web import auth
from fluxtuner.web.app import create_app

PASSWORD = "correct horse battery staple"


@pytest.fixture
def web_library(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    for module, current, legacy, filename in [
        (favorites, "FAVORITES_FILE", "LEGACY_FAVORITES_FILE", "favorites.json"),
        (history, "HISTORY_FILE", "LEGACY_HISTORY_FILE", "history.json"),
        (manual_playlists, "PLAYLISTS_FILE", "LEGACY_PLAYLISTS_FILE", "playlists.json"),
    ]:
        monkeypatch.setattr(module, current, tmp_path / filename)
        monkeypatch.setattr(module, legacy, tmp_path / "legacy" / filename)
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()
    users = {}
    with db.connect() as conn:
        for username in ("alice", "bob"):
            user_id = db.get_or_create_user(
                conn, username, password_hash=auth.hash_password(PASSWORD)
            )
            profile_id = db.ensure_default_profile(conn, user_id=user_id)
            users[username] = (user_id, profile_id)
        conn.commit()
    return TestClient(create_app()), users
