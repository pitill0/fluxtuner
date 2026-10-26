# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Offline remote subscription route contracts."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException

from fluxtuner.web.routes import subscriptions as routes


class FakeRequest:
    def __init__(self, data=b"", session="session-a"):
        self.data = data
        self.headers = {
            "content-type": "application/json",
            "X-FluxTuner-Refresh-Receipt": "receipt-1",
        }
        self.cookies = {"fluxtuner_session": session}

    async def stream(self):
        yield self.data


def test_create_requires_authorization_before_download(monkeypatch):
    def deny(_request, *, mutation=True):
        raise HTTPException(status_code=403, detail="CSRF")

    monkeypatch.setattr(routes, "_authorize", deny)
    monkeypatch.setattr(
        routes, "_download_catalog",
        lambda *_: pytest.fail("Unexpected download"),
    )

    request = FakeRequest(
        json.dumps({"url": "https://catalog.example/a"}).encode()
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(routes.subscriptions_create(request))

    assert exc.value.status_code == 403


def test_preview_checks_ownership_before_download(monkeypatch):
    monkeypatch.setattr(routes, "_authorize", lambda request: 7)

    def deny_owned(*_args):
        raise ValueError("Foreign source")

    monkeypatch.setattr(routes, "_owned_catalog", deny_owned)
    monkeypatch.setattr(
        routes, "_download_catalog",
        lambda *_: pytest.fail("Unexpected download"),
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            routes.subscriptions_preview(
                99, FakeRequest()
            )
        )
    assert exc.value.status_code == 404


def test_confirm_uses_server_snapshot_only(monkeypatch):
    calls = {}

    monkeypatch.setattr(routes, "_authorize", lambda request: 7)

    def confirm(**kwargs):
        calls.update(kwargs)
        return {"status": "ok"}

    monkeypatch.setattr(
        routes.service, "confirm_stored_refresh", confirm
    )

    result = asyncio.run(
        routes.subscriptions_confirm(
            3, FakeRequest(), revision=2
        )
    )
    assert result == {"status": "ok"}
    assert calls["source_id"] == 3
    assert calls["revision"] == 2
    assert calls["receipt"] == "receipt-1"
    assert "data" not in calls


def test_delete_calls_owned_removal(monkeypatch):
    calls = []

    monkeypatch.setattr(routes, "_authorize", lambda request: 7)
    monkeypatch.setattr(
        routes, "_remove_owned",
        lambda user, profile, source: calls.append(
            (user, source)
        ),
    )

    result = asyncio.run(
        routes.subscriptions_delete(5, FakeRequest())
    )
    assert result == {"status": "ok"}
    assert calls == [(7, 5)]
