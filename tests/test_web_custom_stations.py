from __future__ import annotations

import socket

import pytest
from fastapi.testclient import TestClient

from fluxtuner import config
from fluxtuner.core import db, favorites, history, manual_playlists
from fluxtuner.core.profiles import get_or_create_profile
from fluxtuner.web import auth
from fluxtuner.web.app import create_app
from fluxtuner.web.security import CSRF_HEADER_NAME

ENDPOINT = "/api/stations/custom"
PASSWORD = "correct horse battery staple"
STATION = {"name": "Personal radio", "url": "https://radio.example/live"}


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


def login(client, username="alice"):
    response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return {CSRF_HEADER_NAME: response.json()["csrf_token"]}


def assert_empty_library():
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM stations").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM favorites").fetchone()[0] == 0


def test_manual_station_requires_login(web_library):
    client, _ = web_library
    response = client.post(ENDPOINT, json=STATION)
    assert response.status_code == 401
    assert_empty_library()


@pytest.mark.parametrize("token", [None, "invalid"])
def test_manual_station_requires_csrf(web_library, token):
    client, _ = web_library
    login(client)
    headers = {} if token is None else {CSRF_HEADER_NAME: token}
    response = client.post(ENDPOINT, json=STATION, headers=headers)
    assert response.status_code == 403
    assert_empty_library()


def test_manual_station_saves_without_network_access(web_library, monkeypatch):
    client, users = web_library
    headers = login(client)

    def unexpected_network(*args, **kwargs):
        pytest.fail("Manual creation must not contact the supplied stream")

    monkeypatch.setattr(socket, "getaddrinfo", unexpected_network)
    monkeypatch.setattr(socket, "create_connection", unexpected_network)
    response = client.post(ENDPOINT, json=STATION, headers=headers)

    assert response.status_code == 200
    assert response.json()["added"] is True
    saved = favorites.load_favorites(profile_id=users["alice"][1])
    assert len(saved) == 1
    assert favorites.favorite_display_name(saved[0]) == STATION["name"]
    assert saved[0]["url_resolved"] == STATION["url"]
    assert favorites.load_favorites(profile_id=users["bob"][1]) == []


def test_manual_station_duplicate_keeps_existing_name_and_tags(web_library):
    client, users = web_library
    headers = login(client)
    first = client.post(ENDPOINT, json=STATION, headers=headers)
    assert first.status_code == 200
    with db.connect() as conn:
        favorites.update_favorite_record(
            conn,
            STATION["url"],
            custom_name="Keep this name",
            favorite_tags=["Keep"],
            profile_id=users["alice"][1],
        )
        conn.commit()
        before = dict(conn.execute("SELECT * FROM stations").fetchone())

    response = client.post(ENDPOINT, json={**STATION, "name": "Replacement"}, headers=headers)

    assert response.status_code == 200
    assert response.json()["added"] is False
    saved = favorites.load_favorites(profile_id=users["alice"][1])
    assert len(saved) == 1
    assert saved[0]["custom_name"] == "Keep this name"
    assert saved[0]["favorite_tags"] == ["Keep"]
    with db.connect() as conn:
        assert dict(conn.execute("SELECT * FROM stations").fetchone()) == before


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"name": "", "url": STATION["url"]},
        {"name": "Radio", "url": "file:///tmp/audio.mp3"},
        {"name": "Radio", "url": "https://user:pass@radio.example/live"},
        {"name": "Radio", "url": "https://radio.example:bad/live"},
        {"name": "Radio", "url": "https://radio.example/li\nve"},
        {"name": "x" * 201, "url": STATION["url"]},
        {"name": "Radio", "url": "https://radio.example/" + "x" * 2048},
        {"name": ["Radio"], "url": STATION["url"]},
        {"name": "Radio", "url": 123},
        {**STATION, "profile_id": 1},
        {**STATION, "user_id": 1},
        {**STATION, "url_resolved": "https://other.example/live"},
    ],
)
def test_invalid_or_unexpected_fields_cannot_write(web_library, payload):
    client, _ = web_library
    response = client.post(ENDPOINT, json=payload, headers=login(client))
    assert response.status_code == 400
    assert_empty_library()


def test_explicit_profile_is_resolved_inside_authenticated_user(web_library):
    client, users = web_library
    with db.connect() as conn:
        alice_work = get_or_create_profile(conn, "Work", user_id=users["alice"][0])
        bob_work = get_or_create_profile(conn, "Work", user_id=users["bob"][0])
        conn.commit()

    response = client.post(
        ENDPOINT, params={"profile": "Work"}, json=STATION, headers=login(client)
    )

    assert response.status_code == 200
    assert len(favorites.load_favorites(profile_id=alice_work)) == 1
    assert favorites.load_favorites(profile_id=bob_work) == []
    assert favorites.load_favorites(profile_id=users["alice"][1]) == []


def test_foreign_profile_is_not_recreated_for_current_user(web_library):
    client, users = web_library
    with db.connect() as conn:
        get_or_create_profile(conn, "Bob only", user_id=users["bob"][0])
        conn.commit()
        before = conn.execute("SELECT count(*) FROM profiles").fetchone()[0]

    response = client.post(
        ENDPOINT, params={"profile": "Bob only"}, json=STATION, headers=login(client)
    )

    assert response.status_code == 404
    assert_empty_library()
    with db.connect() as conn:
        assert conn.execute("SELECT count(*) FROM profiles").fetchone()[0] == before


def test_default_target_does_not_inherit_desktop_active_profile(web_library):
    client, users = web_library
    config.set_config_value("active_profile", "Desktop only")

    response = client.post(ENDPOINT, json=STATION, headers=login(client))

    assert response.status_code == 200
    assert len(favorites.load_favorites(profile_id=users["alice"][1])) == 1
