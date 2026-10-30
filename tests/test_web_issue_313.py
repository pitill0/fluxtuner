"""Regression contracts for issue #313: URL validation and private API caching."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app
from fluxtuner.web.routes import imports, subscriptions


class FakeRequest:
    def __init__(self, payload: dict[str, str]) -> None:
        self.headers = {"content-type": "application/json"}
        self.data = json.dumps(payload).encode()

    async def stream(self):
        yield self.data


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://radio.example/list.m3u",
        "javascript:alert(1)",
        "https:///missing-host",
        "not-a-url",
    ],
)
def test_remote_import_rejects_unsupported_urls_without_download(
    monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    monkeypatch.setattr(imports, "_authorize", lambda request: 7)
    monkeypatch.setattr(
        imports,
        "fetch_remote_station_collection",
        lambda *_args: pytest.fail("Unexpected network access"),
    )

    with pytest.raises(HTTPException) as error:
        asyncio.run(imports.fetch_remote_import(FakeRequest({"url": url})))

    assert error.value.status_code == 400


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "ftp://radio.example/list.m3u", "https:///missing-host"],
)
def test_subscription_rejects_unsupported_urls_before_download(url: str) -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(subscriptions._read_subscription_input(FakeRequest({"url": url})))

    assert error.value.status_code == 400


def test_supported_url_reaches_existing_download_handling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(imports, "_authorize", lambda request: 7)

    def failed_fetch(*_args):
        raise OSError("Remote connection failed")

    monkeypatch.setattr(imports, "fetch_remote_station_collection", failed_fetch)

    with pytest.raises(HTTPException) as error:
        asyncio.run(
            imports.fetch_remote_import(FakeRequest({"url": "https://radio.example/list.m3u"}))
        )

    assert error.value.status_code == 502


@pytest.mark.parametrize(
    "path",
    ["/api/auth/me", "/api/favorites", "/api/metadata?url=file:///etc/passwd"],
)
def test_private_api_responses_disable_storage(path: str) -> None:
    client = TestClient(create_app())
    response = client.get(path)

    assert response.headers["cache-control"] == "no-store"


def test_public_routes_do_not_inherit_private_cache_policy() -> None:
    client = TestClient(create_app())

    for path in ("/api/health", "/api/public/stats"):
        response = client.get(path)
        assert response.headers.get("cache-control") != "no-store"


def test_static_delivery_cache_policy_is_unchanged() -> None:
    client = TestClient(create_app())
    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
