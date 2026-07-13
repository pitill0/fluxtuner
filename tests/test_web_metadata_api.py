# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from types import MappingProxyType
from typing import Any

from fastapi.testclient import TestClient

from fluxtuner.core import db
from fluxtuner.web import auth
from fluxtuner.web.app import create_app
from fluxtuner.web.metadata import MetadataCacheSnapshot, MetadataCacheStatus

VALID_PASSWORD = "correct horse battery staple"


class FakeCoordinator:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.close_calls: list[bool] = []

    def get_or_schedule(self, raw_url: str) -> MetadataCacheSnapshot:
        self.urls.append(raw_url)
        return MetadataCacheSnapshot(
            url="https://radio.example/live",
            status=MetadataCacheStatus.FRESH,
            metadata=MappingProxyType(
                {
                    "raw": "Artist - Song",
                    "artist": "Artist",
                    "title": "Song",
                    "source": "icy",
                }
            ),
            updated_at=1.0,
            retry_at=16.0,
            failure_count=0,
        )

    def close(self, *, wait: bool = True) -> None:
        self.close_calls.append(wait)


def create_user(username: str) -> None:
    password_hash = auth.hash_password(VALID_PASSWORD)
    with db.connect() as conn:
        db.get_or_create_user(
            conn,
            username,
            password_hash=password_hash,
            is_active=True,
        )
        conn.commit()


def login(client: TestClient, username: str) -> None:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": VALID_PASSWORD},
    )
    assert response.status_code == 200


def make_app(tmp_path: Any, monkeypatch: Any, coordinator: FakeCoordinator) -> Any:
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "web-metadata-api.db")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    db.init_db()
    create_user("alice")
    return create_app(metadata_coordinator_factory=lambda: coordinator)


def test_metadata_endpoint_requires_authentication(tmp_path, monkeypatch) -> None:
    coordinator = FakeCoordinator()
    app = make_app(tmp_path, monkeypatch, coordinator)

    with TestClient(app) as client:
        response = client.get(
            "/api/metadata",
            params={"url": "https://radio.example/live"},
        )

    assert response.status_code == 401
    assert coordinator.urls == []


def test_metadata_endpoint_returns_cached_snapshot_without_remote_wait(
    tmp_path,
    monkeypatch,
) -> None:
    coordinator = FakeCoordinator()
    app = make_app(tmp_path, monkeypatch, coordinator)

    with TestClient(app) as client:
        login(client, "alice")
        response = client.get(
            "/api/metadata",
            params={"url": "https://radio.example/live"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "url": "https://radio.example/live",
        "status": "fresh",
        "metadata": {
            "raw": "Artist - Song",
            "artist": "Artist",
            "title": "Song",
            "source": "icy",
        },
        "failure_count": 0,
    }
    assert coordinator.urls == ["https://radio.example/live"]


def test_metadata_coordinator_is_owned_by_application_lifespan(
    tmp_path,
    monkeypatch,
) -> None:
    coordinator = FakeCoordinator()
    app = make_app(tmp_path, monkeypatch, coordinator)

    assert not hasattr(app.state, "metadata_coordinator")
    with TestClient(app):
        assert app.state.metadata_coordinator is coordinator

    assert coordinator.close_calls == [True]
    assert not hasattr(app.state, "metadata_coordinator")


def test_metadata_endpoint_rejects_invalid_url(tmp_path, monkeypatch) -> None:
    from fluxtuner.web.metadata import StreamTargetValidationError

    class RejectingCoordinator(FakeCoordinator):
        def get_or_schedule(self, raw_url: str) -> MetadataCacheSnapshot:
            raise StreamTargetValidationError("invalid")

    coordinator = RejectingCoordinator()
    app = make_app(tmp_path, monkeypatch, coordinator)

    with TestClient(app) as client:
        login(client, "alice")
        response = client.get(
            "/api/metadata",
            params={"url": "file:///etc/passwd"},
        )

    assert response.status_code == 400
    assert response.json() == {"detail": "Stream URL must be a valid HTTP or HTTPS URL."}
