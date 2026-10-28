# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""UX-03 read-only library routing contracts."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from fluxtuner.web.routes import library, subscriptions


def test_catalog_stations_requires_authentication(monkeypatch):
    def deny(_request, *, mutation=True):
        raise HTTPException(status_code=401, detail="Authentication required.")

    monkeypatch.setattr(subscriptions, "_authorize", deny)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(subscriptions.subscriptions_stations(7, object()))

    assert exc.value.status_code == 401


def test_catalog_stations_checks_ownership(monkeypatch):
    monkeypatch.setattr(
        subscriptions,
        "_authorize",
        lambda request, *, mutation=True: 42,
    )

    def deny(_user, _profile, _source):
        raise ValueError("Subscription unavailable for this profile.")

    monkeypatch.setattr(subscriptions, "_catalog_stations", deny)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(subscriptions.subscriptions_stations(9, object()))

    assert exc.value.status_code == 404


def test_catalog_stations_returns_shared_station_format(monkeypatch):
    monkeypatch.setattr(
        subscriptions,
        "_authorize",
        lambda request, *, mutation=True: 42,
    )
    monkeypatch.setattr(
        subscriptions,
        "_catalog_stations",
        lambda user, profile, source: {
            "source_id": source,
            "count": 1,
            "stations": [
                {
                    "name": "Example",
                    "url": "https://radio.example/live",
                }
            ],
        },
    )

    result = asyncio.run(subscriptions.subscriptions_stations(9, object()))

    assert result["source_id"] == 9
    assert result["count"] == 1
    assert result["stations"][0]["name"] == "Example"


def test_manual_stations_requires_authentication(monkeypatch):
    def deny(_request):
        raise HTTPException(status_code=401, detail="Authentication required.")

    monkeypatch.setattr(library, "_require_authenticated_user", deny)

    with pytest.raises(HTTPException) as exc:
        library.list_custom_stations(object(), profile=None)

    assert exc.value.status_code == 401


def test_manual_stations_rejects_foreign_profile(monkeypatch):
    monkeypatch.setattr(
        library,
        "_require_authenticated_user",
        lambda request: {"id": 42},
    )

    def deny(_user, _profile):
        raise LookupError("The requested profile is unavailable.")

    monkeypatch.setattr(library, "_manual_stations", deny)

    with pytest.raises(HTTPException) as exc:
        library.list_custom_stations(object(), profile=None)

    assert exc.value.status_code == 404
