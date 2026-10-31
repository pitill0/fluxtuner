# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Observable HTTP contracts across Web composition boundaries."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fluxtuner import paths
from fluxtuner.web import middleware
from fluxtuner.web.app import create_app
from fluxtuner.web.security import SESSION_COOKIE_NAME


@pytest.mark.parametrize("versioned", [False, True])
@pytest.mark.parametrize("encoding", ["identity", "gzip"])
def test_html_get_head_and_revalidation_agree(tmp_path, monkeypatch, versioned, encoding):
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
    monkeypatch.setenv("FLUXTUNER_WEB_VERSIONED_STATIC", "1" if versioned else "0")
    client = TestClient(create_app())
    headers = {"Accept-Encoding": encoding}
    get = client.get("/", headers=headers)
    head = client.head("/", headers=headers)

    assert get.status_code == head.status_code == 200
    assert head.content == b""
    for name in ("etag", "cache-control", "vary", "content-length", "content-type"):
        assert head.headers[name] == get.headers[name]
    assert get.headers["cache-control"] == "no-cache"
    assert get.headers["vary"] == "Accept-Encoding"
    if encoding == "gzip":
        assert head.headers["content-encoding"] == get.headers["content-encoding"] == "gzip"
        assert get.headers["etag"].startswith('W/"gzip-')
    else:
        assert "content-encoding" not in get.headers
        assert int(head.headers["content-length"]) == len(get.content)
    assert ('src="/static/build/' in get.text) is versioned

    for method in (client.get, client.head):
        cached = method("/", headers={**headers, "If-None-Match": get.headers["etag"]})
        assert cached.status_code == 304
        assert cached.content == b""
        for name in ("etag", "cache-control", "vary"):
            assert cached.headers[name] == get.headers[name]


def test_session_cookie_is_renewed_inside_private_cache_policy(monkeypatch):
    calls = []
    cookie_cache_headers = []

    def resolve_session(token, path):
        calls.append((token, path))
        return None, 60

    def renew_cookie(response, token, *, max_age):
        cookie_cache_headers.append(response.headers.get("cache-control"))
        response.set_cookie(SESSION_COOKIE_NAME, token, max_age=max_age)

    monkeypatch.setattr(middleware, "_resolve_and_renew_session_sync", resolve_session)
    monkeypatch.setattr(middleware, "set_session_cookie", renew_cookie)
    client = TestClient(create_app())
    client.cookies.set(SESSION_COOKIE_NAME, "existing-session")

    response = client.get("/api/private-missing")
    assert response.status_code == 404
    assert calls == [("existing-session", "/api/private-missing")]
    assert cookie_cache_headers == [None]
    assert response.headers["cache-control"] == "no-store"
    assert "Max-Age=60" in response.headers["set-cookie"]

    calls.clear()
    static = client.get("/static/app.js")
    assert static.status_code == 200
    assert static.headers["cache-control"] == "no-cache"
    assert calls == []
    assert "set-cookie" not in static.headers


@pytest.mark.parametrize("path", ["/api/health", "/api/public/missing"])
def test_public_api_paths_are_excluded_from_private_cache_policy(path):
    response = TestClient(create_app()).get(path)
    assert response.status_code == (200 if path == "/api/health" else 404)
    assert response.headers.get("cache-control") != "no-store"
