"""Publication controls appear only in authenticated favorites."""

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web.app import create_app
from fluxtuner.web.security import CSRF_HEADER_NAME


def test_publication_controls_are_scoped_to_favorites_view() -> None:
    client = TestClient(create_app())
    renderer = client.get("/static/js/station-renderer.js")
    controller = client.get("/static/js/station-publication.js")
    app = client.get("/static/app.js")
    assert all(item.status_code == 200 for item in (renderer, controller, app))
    assert 'currentView === "favorites"' in renderer.text
    assert "data-toggle-publication" in renderer.text
    assert "publication_eligible" in renderer.text
    assert 'method: "PUT"' in controller.text
    assert "getSessionKey" in controller.text
    assert "createStationPublicationController" in app.text


def test_authenticated_favorites_include_owned_publication_state(web_library) -> None:
    client, users = web_library
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    csrf = {CSRF_HEADER_NAME: login.json()["csrf_token"]}
    created = client.post(
        "/api/favorites",
        headers=csrf,
        json={"name": "Demo", "url": "https://radio.example/live"},
    )
    assert created.status_code == 200
    response = client.get("/api/favorites")
    assert response.status_code == 200
    station = response.json()["stations"][0]
    assert type(station["station_id"]) is int and station["station_id"] > 0
    assert station["published"] is False
    assert station["publication_eligible"] is True
    with db.connect() as conn:
        row = conn.execute(
            "SELECT station_id FROM favorites WHERE profile_id = ?",
            (users["alice"][1],),
        ).fetchone()
        assert station["station_id"] == row["station_id"]

    enabled = client.put(
        f"/api/stations/{station['station_id']}/publication",
        headers=csrf,
        json={"published": True},
    )
    assert enabled.status_code == 200
    assert client.get("/api/favorites").json()["stations"][0]["published"] is True


def test_token_stream_is_disabled_in_favorites_payload(web_library) -> None:
    client, _users = web_library
    login = client.post(
        "/api/auth/login",
        json={"username": "alice", "password": "correct horse battery staple"},
    )
    assert login.status_code == 200
    csrf = {CSRF_HEADER_NAME: login.json()["csrf_token"]}
    assert (
        client.post(
            "/api/favorites",
            headers=csrf,
            json={"name": "Private stream", "url": "https://radio.example/live?token=private"},
        ).status_code
        == 200
    )
    station = client.get("/api/favorites").json()["stations"][0]
    assert station["publication_eligible"] is False
    assert station["published"] is False


def test_publication_requires_informed_confirmation() -> None:
    from fastapi.testclient import TestClient

    from fluxtuner.web.app import create_app

    client = TestClient(create_app())
    response = client.get("/static/js/station-publication.js")

    assert response.status_code == 200
    source = response.text

    assert "if (published)" in source
    assert "window.confirm(" in source
    assert "if (!confirmed) return;" in source
    assert "Other users may discover it" in source
    assert "copies already saved" in source

    assert source.index("window.confirm(") < source.index("button.disabled = true;")
    assert source.index("if (!confirmed) return;") < source.index(
        "apiFetch(`/api/stations/${id}/publication`"
    )


def test_publication_privacy_is_documented() -> None:
    from pathlib import Path

    guide = Path("docs/web.md").read_text(encoding="utf-8")

    assert "## Station publication and privacy" in guide
    assert "private by default" in guide
    assert "Make public" in guide
    assert "Make private" in guide
    assert "previously saved by third parties" in guide
    assert "Neither operation automatically" in guide
