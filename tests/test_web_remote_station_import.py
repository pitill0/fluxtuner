# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Offline API contract: URL fetch is authenticated, bounded, and read-only."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException

from fluxtuner.web.routes import imports


class FakeRequest:
    def __init__(self, data, content_type="application/json"):
        self.data = data
        self.headers = {"content-type": content_type}

    async def stream(self):
        yield self.data


def test_remote_url_fetch_returns_exact_bytes_and_does_not_import(monkeypatch):
    calls = []
    payload = b"#EXTM3U\n#EXTINF:-1,Example\nhttps://radio.example/live\n"
    monkeypatch.setattr(imports, "_authorize", lambda request: 7)

    def fetch(url, resolver):
        calls.append((url, resolver))
        return payload

    monkeypatch.setattr(imports, "fetch_remote_station_collection", fetch)
    response = asyncio.run(
        imports.fetch_remote_import(
            FakeRequest(json.dumps({"url": "https://radio.example/list.m3u"}).encode())
        )
    )
    assert response.body == payload
    assert response.media_type == "application/octet-stream"
    assert response.headers["cache-control"] == "no-store"
    assert len(calls) == 1
    assert calls[0][0] == "https://radio.example/list.m3u"


@pytest.mark.parametrize(
    "body,content_type,status",
    [
        (b"{}", "application/json", 400),
        (b"not json", "application/json", 400),
        (b"{}", "text/plain", 415),
        (b"x" * 4097, "application/json", 413),
        (json.dumps({"url": "a" * 2049}).encode(), "application/json", 400),
    ],
)
def test_remote_url_rejects_bad_requests(monkeypatch, body, content_type, status):
    monkeypatch.setattr(imports, "_authorize", lambda request: 7)
    monkeypatch.setattr(
        imports, "fetch_remote_station_collection", lambda *_: pytest.fail("Unexpected download")
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(imports.fetch_remote_import(FakeRequest(body, content_type)))
    assert exc.value.status_code == status


def test_remote_url_authorization_precedes_network(monkeypatch):
    def denied(_request):
        raise HTTPException(status_code=403, detail="CSRF rejected")

    monkeypatch.setattr(imports, "_authorize", denied)
    monkeypatch.setattr(
        imports, "fetch_remote_station_collection", lambda *_: pytest.fail("Unexpected download")
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(imports.fetch_remote_import(FakeRequest(b"{}")))
    assert exc.value.status_code == 403


def test_remote_url_protected_fetch_failure(monkeypatch):
    monkeypatch.setattr(imports, "_authorize", lambda request: 7)

    def blocked(*_args):
        raise ValueError("Blocked destination")

    monkeypatch.setattr(imports, "fetch_remote_station_collection", blocked)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            imports.fetch_remote_import(
                FakeRequest(json.dumps({"url": "http://127.0.0.1/"}).encode())
            )
        )
    assert exc.value.status_code == 400
