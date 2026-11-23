# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Security headers across document, API, error and static responses."""

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app
from fluxtuner.web.middleware import CONTENT_SECURITY_POLICY


def test_security_policy_has_expected_restrictions() -> None:
    policy = CONTENT_SECURITY_POLICY

    assert "default-src 'self';" in policy
    assert "script-src 'self';" in policy
    assert "object-src 'none';" in policy
    assert "frame-ancestors 'none';" in policy
    assert "base-uri 'self';" in policy
    assert "form-action 'self';" in policy

    assert "media-src 'self' blob: http: https:;" in policy
    assert "img-src 'self' data: blob: http: https:;" in policy
    assert "style-src 'self' 'unsafe-inline';" in policy

    assert "unsafe-eval" not in policy
    assert "script-src 'self' 'unsafe-inline'" not in policy


def test_security_headers_cover_document_api_static_and_errors() -> None:
    client = TestClient(create_app())

    for method, url in (
        ("GET", "/"),
        ("HEAD", "/"),
        ("GET", "/api/health"),
        ("GET", "/api/auth/me"),
        ("GET", "/static/app.js"),
        ("GET", "/static/styles.css"),
        ("GET", "/route-that-does-not-exist"),
    ):
        response = client.request(method, url)
        assert response.headers["content-security-policy"] == (CONTENT_SECURITY_POLICY), (
            method,
            url,
            response.status_code,
        )
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
        assert response.headers["referrer-policy"] == "no-referrer"


def test_security_headers_cover_conditional_document_response() -> None:
    client = TestClient(create_app())
    first = client.get("/")
    assert first.status_code == 200

    conditional = client.get(
        "/",
        headers={"If-None-Match": first.headers["etag"]},
    )

    assert conditional.status_code == 304
    assert conditional.headers["content-security-policy"] == (CONTENT_SECURITY_POLICY)
    assert conditional.headers["x-frame-options"] == "DENY"


def test_security_headers_preserve_cache_contracts() -> None:
    client = TestClient(create_app())

    assert client.get("/").headers["cache-control"] == "no-cache"
    assert client.get("/static/app.js").headers["cache-control"] == ("no-cache")
    assert client.get("/api/auth/me").headers["cache-control"] == ("no-store")
