"""Authenticated station publication never crosses profile ownership boundaries."""

from fluxtuner.core import db
from fluxtuner.web.security import CSRF_HEADER_NAME

PASSWORD = "correct horse battery staple"


def _login(client, username):
    response = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200
    return {CSRF_HEADER_NAME: response.json()["csrf_token"]}


def _favorite(conn, profile_id, url):
    station_id = db.upsert_station(conn, {"name": "Demo", "url": url})
    now = db.utc_now()
    conn.execute(
        """
        INSERT INTO favorites (profile_id, station_id, created_at, updated_at)
        VALUES (?, ?, ?, ?)
        """,
        (profile_id, station_id, now, now),
    )
    return station_id


def test_publication_requires_auth_and_csrf_and_owns_favorite(web_library):
    client, users = web_library
    with db.connect() as conn:
        station_id = _favorite(conn, users["alice"][1], "https://radio.example/live")
        conn.commit()
    endpoint = f"/api/stations/{station_id}/publication"

    assert client.get(endpoint).status_code == 401
    assert client.put(endpoint, json={"published": True}).status_code == 401
    headers = _login(client, "bob")
    assert client.get(endpoint).status_code == 404
    assert client.put(endpoint, json={"published": True}, headers=headers).status_code == 409

    headers = _login(client, "alice")
    assert client.put(endpoint, json={"published": True}).status_code == 403
    assert (
        client.put(
            endpoint, json={"published": True}, headers={CSRF_HEADER_NAME: "invalid"}
        ).status_code
        == 403
    )
    assert client.get(endpoint).json() == {"published": False}
    enabled = client.put(endpoint, json={"published": True}, headers=headers)
    assert enabled.status_code == 200
    assert enabled.json() == {"published": True}
    assert enabled.headers["cache-control"] == "no-store"
    assert client.get(endpoint).json() == {"published": True}
    disabled = client.put(endpoint, json={"published": False}, headers=headers)
    assert disabled.status_code == 200
    assert client.get(endpoint).json() == {"published": False}


def test_publication_rejects_secret_urls_and_invalid_bodies(web_library):
    client, users = web_library
    with db.connect() as conn:
        station_id = _favorite(conn, users["alice"][1], "https://radio.example/live?token=private")
        conn.commit()
    endpoint = f"/api/stations/{station_id}/publication"
    headers = _login(client, "alice")
    assert client.put(endpoint, json={"published": True}, headers=headers).status_code == 409
    for payload in ({}, {"published": 1}, {"published": "true"}, {"published": True, "user_id": 1}):
        assert client.put(endpoint, json=payload, headers=headers).status_code == 422
    assert client.get(endpoint).json() == {"published": False}


def test_publication_rejects_foreign_profile_without_creating_it(web_library):
    client, users = web_library
    with db.connect() as conn:
        station_id = _favorite(conn, users["alice"][1], "https://radio.example/live")
        count_before = conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0]
        conn.commit()
    headers = _login(client, "bob")
    endpoint = f"/api/stations/{station_id}/publication?profile=alice-only"
    assert client.put(endpoint, json={"published": True}, headers=headers).status_code == 404
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == count_before
        assert conn.execute("SELECT COUNT(*) FROM public_station_opt_ins").fetchone()[0] == 0
