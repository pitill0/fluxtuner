# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Web recommendation authorization, CSRF and acceptance contracts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import create_app
from fluxtuner.web.security import CSRF_HEADER_NAME

PASSWORD = "correct horse battery staple"
STREAM = "https://radio.example/one"


def _client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "shares.db")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()
    with db.connect() as conn:
        for username in ("alice", "bob", "charlie"):
            identifier = db.get_or_create_user(
                conn, username, password_hash=auth.hash_password(PASSWORD)
            )
            profile = db.ensure_default_profile(conn, user_id=identifier)
            if username == "alice":
                db.add_favorite_record(
                    conn, {"name": "Radio One", "url": STREAM}, profile_id=profile
                )
        conn.commit()
    return TestClient(create_app())


def _login(client: TestClient, username: str) -> dict[str, str]:
    result = client.post("/api/auth/login", json={"username": username, "password": PASSWORD})
    assert result.status_code == 200
    return {CSRF_HEADER_NAME: str(result.json()["csrf_token"])}


def _send(client: TestClient, headers: dict[str, str]) -> int:
    response = client.post(
        "/api/recommendations",
        json={"recipient_username": "bob", "kind": "station", "station_key": STREAM},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return int(response.json()["id"])


def test_recommendation_endpoints_require_authentication(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    for method, url in (
        ("get", "/api/recommendations"),
        ("post", "/api/recommendations"),
        ("post", "/api/recommendations/1/accept"),
        ("post", "/api/recommendations/1/reject"),
    ):
        body = (
            {"recipient_username": "bob", "kind": "station", "station_key": STREAM}
            if url == "/api/recommendations" and method == "post"
            else None
        )
        assert client.request(method, url, json=body).status_code == 401


def test_send_list_and_accept_are_scoped(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    alice_csrf = _login(client, "alice")
    identifier = _send(client, alice_csrf)
    sent = client.get("/api/recommendations?direction=sent")
    assert sent.status_code == 200
    assert [entry["id"] for entry in sent.json()["recommendations"]] == [identifier]
    assert "snapshot_json" not in sent.text

    assert client.post("/api/auth/logout", headers=alice_csrf).status_code == 200
    charlie_csrf = _login(client, "charlie")
    assert client.get("/api/recommendations").json() == {"recommendations": []}
    denied = client.post(f"/api/recommendations/{identifier}/accept", headers=charlie_csrf)
    assert denied.status_code == 409
    assert denied.json()["detail"] == "Recommendation unavailable."

    assert client.post("/api/auth/logout", headers=charlie_csrf).status_code == 200
    bob_csrf = _login(client, "bob")
    inbox = client.get("/api/recommendations")
    assert inbox.status_code == 200
    assert inbox.json()["recommendations"][0]["counterpart_username"] == "alice"
    assert client.post(f"/api/recommendations/{identifier}/accept").status_code == 403
    accepted = client.post(f"/api/recommendations/{identifier}/accept", headers=bob_csrf)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"
    assert (
        client.post(f"/api/recommendations/{identifier}/accept", headers=bob_csrf).status_code
        == 409
    )
    with db.connect() as conn:
        share = conn.execute(
            "SELECT status, snapshot_json FROM playlist_shares WHERE id = ?", (identifier,)
        ).fetchone()
        assert share["status"] == "accepted"
        assert share["snapshot_json"] is None


def test_mutations_require_csrf_and_validate_inputs(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = _login(client, "alice")
    selection = {"recipient_username": "bob", "kind": "station", "station_key": STREAM}
    assert client.post("/api/recommendations", json=selection).status_code == 403
    assert (
        client.post(
            "/api/recommendations", json={**selection, "sender_user_id": 999}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/recommendations",
            json={"recipient_username": "bob", "kind": "station"},
            headers=headers,
        ).status_code
        == 400
    )
    identifier = _send(client, headers)
    assert client.post(f"/api/recommendations/{identifier}/reject").status_code == 403


def test_unknown_recipient_and_duplicate_hide_details(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    headers = _login(client, "alice")
    missing = client.post(
        "/api/recommendations",
        json={"recipient_username": "unknown", "kind": "station", "station_key": STREAM},
        headers=headers,
    )
    assert missing.status_code == 409
    assert missing.json()["detail"] == "Recommendation could not be sent."
    _send(client, headers)
    duplicate = client.post(
        "/api/recommendations",
        json={"recipient_username": "bob", "kind": "station", "station_key": STREAM},
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == missing.json()["detail"]


def test_rejection_does_not_import_station(tmp_path, monkeypatch) -> None:
    client = _client(tmp_path, monkeypatch)
    alice_csrf = _login(client, "alice")
    identifier = _send(client, alice_csrf)
    assert client.post("/api/auth/logout", headers=alice_csrf).status_code == 200
    bob_csrf = _login(client, "bob")
    result = client.post(f"/api/recommendations/{identifier}/reject", headers=bob_csrf)
    assert result.status_code == 200
    assert result.json() == {"id": identifier, "status": "rejected"}
