"""Artwork routes cannot become an unauthenticated or unsigned image proxy."""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fluxtuner.core.artwork_download import DownloadedArtwork
from fluxtuner.web import context as web_context
from fluxtuner.web.artwork_tokens import issue_artwork_reference
from fluxtuner.web.routes import artwork as artwork_routes
from fluxtuner.web.security import SESSION_COOKIE_NAME

KEY = b"web-server-only-key-with-sufficient-entropy-32"
URL = "https://radio.example/favicon.png"
PNG = b"a-validated-image-payload"


@dataclass
class StubService:
    result: DownloadedArtwork | None = DownloadedArtwork(PNG, "image/png")
    calls: list[str] = field(default_factory=list)

    def get(self, url: str) -> DownloadedArtwork | None:
        self.calls.append(url)
        return self.result


def _client(service: StubService, monkeypatch) -> TestClient:
    monkeypatch.setattr(
        web_context,
        "authenticated_user",
        lambda request: {"id": 1} if request.cookies.get(SESSION_COOKIE_NAME) else None,
    )
    app = FastAPI()
    app.include_router(artwork_routes.router)
    app.dependency_overrides[artwork_routes.get_artwork_signing_key] = lambda: KEY
    app.dependency_overrides[artwork_routes.get_artwork_service] = lambda: service
    return TestClient(app)


def _reference(session: str, *, now: int | None = None) -> str:
    return issue_artwork_reference(URL, session, KEY, now=now)


def test_authenticated_reference_returns_validated_bytes(monkeypatch) -> None:
    service = StubService()
    client = _client(service, monkeypatch)
    client.cookies.set(SESSION_COOKIE_NAME, "session-a")

    response = client.get(f"/api/artwork/{_reference('session-a')}")

    assert response.status_code == 200
    assert response.content == PNG
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert service.calls == [URL]


def test_unauthenticated_request_is_denied_without_fetch(monkeypatch) -> None:
    service = StubService()
    client = _client(service, monkeypatch)
    response = client.get(f"/api/artwork/{_reference('session-a')}")
    assert response.status_code == 401
    assert service.calls == []


def test_cross_session_reference_is_denied_without_fetch(monkeypatch) -> None:
    service = StubService()
    client = _client(service, monkeypatch)
    client.cookies.set(SESSION_COOKIE_NAME, "session-b")
    response = client.get(f"/api/artwork/{_reference('session-a')}")
    assert response.status_code == 404
    assert service.calls == []


def test_expired_or_tampered_reference_is_denied_without_fetch(monkeypatch) -> None:
    service = StubService()
    client = _client(service, monkeypatch)
    client.cookies.set(SESSION_COOKIE_NAME, "session-a")
    expired = _reference("session-a", now=int(time.time()) - 1000)
    valid = _reference("session-a")
    tampered = valid[:-1] + ("0" if valid[-1] != "0" else "1")
    for reference in (expired, tampered, "invalid"):
        response = client.get(f"/api/artwork/{reference}")
        assert response.status_code == 404
    assert service.calls == []


def test_missing_artwork_is_fail_closed(monkeypatch) -> None:
    service = StubService(result=None)
    client = _client(service, monkeypatch)
    client.cookies.set(SESSION_COOKIE_NAME, "session-a")
    response = client.get(f"/api/artwork/{_reference('session-a')}")
    assert response.status_code == 404
    assert service.calls == [URL]


def test_different_users_share_one_artwork_source(monkeypatch) -> None:
    service = StubService()
    client = _client(service, monkeypatch)
    for session in ("session-a", "session-b"):
        client.cookies.set(SESSION_COOKIE_NAME, session)
        assert client.get(f"/api/artwork/{_reference(session)}").status_code == 200
    assert service.calls == [URL, URL]
