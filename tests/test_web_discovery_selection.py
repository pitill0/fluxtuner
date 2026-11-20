"""Opaque public discovery references and authenticated redemption contract."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.core.public_featured import featured_station_candidate
from fluxtuner.web.app import create_app
from fluxtuner.web.discovery_selection import issue_selection, verify_selection
from fluxtuner.web.routes import public as public_routes
from fluxtuner.web.security import (
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    csrf_token_for_session_token,
)

_KEY = b"d" * 32


def _seed(conn):
    db.upsert_station(
        conn,
        {"name": "Safe Radio", "url": "https://radio.example.test/live", "stationuuid": "safe"},
    )
    conn.commit()


def test_selection_expires_and_rechecks_live_url(tmp_path):
    path = tmp_path / "discovery-selection.db"
    db.init_db(path)
    now = datetime(2026, 11, 20, 12, 0, tzinfo=UTC)
    with db.connect(path) as conn:
        _seed(conn)
        row = featured_station_candidate(conn, as_of=now.date())
        assert row is not None
        reference = issue_selection(row, _KEY, now=now)
        assert "radio.example" not in reference
        assert "safe" not in reference
        assert verify_selection(conn, reference, _KEY, now=now) is not None
        assert verify_selection(conn, reference + "x", _KEY, now=now) is None
        assert verify_selection(conn, reference, b"x" * 32, now=now) is None
        assert verify_selection(conn, reference, _KEY, now=now + timedelta(minutes=16)) is None
        assert verify_selection(conn, reference, _KEY, now=now - timedelta(seconds=1)) is None
        conn.execute(
            "UPDATE stations SET url_resolved = ? WHERE station_key = ?",
            ("https://radio.example.test/live?token=secret", row["station_key"]),
        )
        assert verify_selection(conn, reference, _KEY, now=now) is None


def test_public_selection_is_opaque_and_requires_auth_to_redeem(tmp_path, monkeypatch):
    path = tmp_path / "discovery-public.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    monkeypatch.setattr(public_routes, "get_artwork_signing_key", lambda: _KEY)
    db.init_db(path)
    with db.connect(path) as conn:
        _seed(conn)
    client = TestClient(create_app())
    response = client.get("/api/public/featured")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["station"] == {"name": "Safe Radio"}
    reference = response.json()["selection"]
    assert "radio.example" not in response.text
    assert "station_key" not in response.text
    unauthorized = client.post("/api/public/featured/redeem", json={"selection": reference})
    assert unauthorized.status_code == 401


def test_authenticated_redemption_is_scoped_idempotent_and_limited(web_library, monkeypatch):
    client, users = web_library
    monkeypatch.setattr(public_routes, "get_artwork_signing_key", lambda: _KEY)
    with db.connect() as conn:
        _seed(conn)

    reference = client.get("/api/public/featured").json()["selection"]
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    session = client.cookies.get(SESSION_COOKIE_NAME)
    assert session
    headers = {CSRF_HEADER_NAME: csrf_token_for_session_token(session)}

    endpoint = "/api/public/featured/redeem"
    assert client.post(endpoint, json={"selection": reference}).status_code == 403
    first = client.post(endpoint, json={"selection": reference}, headers=headers)
    assert first.status_code == 200
    assert first.json() == {"added": True, "name": "Safe Radio"}
    second = client.post(endpoint, json={"selection": reference}, headers=headers)
    assert second.status_code == 200
    assert second.json()["added"] is False
    with db.connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM favorites WHERE profile_id = ?",
                (users["alice"][1],),
            ).fetchone()[0]
            == 1
        )
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM favorites WHERE profile_id = ?",
                (users["bob"][1],),
            ).fetchone()[0]
            == 0
        )

    for _ in range(3):
        assert (
            client.post(endpoint, json={"selection": "invalid"}, headers=headers).status_code == 404
        )
    assert client.post(endpoint, json={"selection": reference}, headers=headers).status_code == 429
