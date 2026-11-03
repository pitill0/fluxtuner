"""#332: reject embedded credentials before any remote collection retrieval."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException

from fluxtuner.web.routes import imports, subscriptions
from fluxtuner.web.validation import is_supported_web_url


class FakeRequest:
    headers = {"content-type": "application/json"}

    def __init__(self, url: str) -> None:
        self.body = json.dumps({"url": url}).encode()

    async def stream(self):
        yield self.body


@pytest.mark.parametrize(
    "url",
    [
        "http://testuser:testpass@catalog.example/collection.m3u",
        "https://testuser@catalog.example/collection.m3u",
        "https://testuser:@catalog.example/collection.m3u",
        "https://:testpass@catalog.example/collection.m3u",
        "https://@catalog.example/collection.m3u",
    ],
)
def test_credential_url_rejected_before_remote_fetch(monkeypatch, url: str) -> None:
    assert is_supported_web_url(url) is False
    monkeypatch.setattr(imports, "_authorize", lambda request: 7)

    def forbidden_fetch(*_args, **_kwargs):
        pytest.fail("Credential URL reached remote retrieval")

    monkeypatch.setattr(imports, "fetch_remote_station_collection", forbidden_fetch)
    with pytest.raises(HTTPException) as error:
        asyncio.run(imports.fetch_remote_import(FakeRequest(url)))
    assert error.value.status_code == 400
    assert "testuser" not in str(error.value.detail)
    assert "testpass" not in str(error.value.detail)


@pytest.mark.parametrize(
    "url",
    [
        "http://testuser:testpass@catalog.example/collection.m3u",
        "https://testuser@catalog.example/collection.m3u",
        "https://testuser:@catalog.example/collection.m3u",
        "https://:testpass@catalog.example/collection.m3u",
        "https://@catalog.example/collection.m3u",
    ],
)
def test_subscription_rejects_credential_url_before_download(url: str) -> None:
    with pytest.raises(HTTPException) as error:
        asyncio.run(subscriptions._read_subscription_input(FakeRequest(url)))
    assert error.value.status_code == 400
    assert "testuser" not in str(error.value.detail)
    assert "testpass" not in str(error.value.detail)


@pytest.mark.parametrize(
    "url",
    [
        "https://catalog.example/collection.m3u",
        "http://catalog.example:8080/collection.m3u?ref=a",
    ],
)
def test_ordinary_web_collection_urls_remain_supported(url: str) -> None:
    assert is_supported_web_url(url)
    imported = asyncio.run(imports._read_remote_url(FakeRequest(url)))
    subscribed, _ = asyncio.run(subscriptions._read_subscription_input(FakeRequest(url)))
    assert imported == subscribed == url


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "ftp://catalog.example/a.m3u", "https:///missing-host"],
)
def test_existing_scheme_and_host_restrictions_unchanged(url: str) -> None:
    assert is_supported_web_url(url) is False
