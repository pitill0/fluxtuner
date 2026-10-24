"""Verify compression and revalidation of public Web assets."""

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_public_static_javascript_compression() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/static/app.js",
        headers={"Accept-Encoding": "gzip"},
    )

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert "Accept-Encoding" in response.headers["vary"]
    assert response.headers["cache-control"] == "no-cache"
    assert "createApiFetch" in response.text


def test_public_static_assets_without_gzip() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/static/app.js",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert "content-encoding" not in response.headers
    assert response.headers["cache-control"] == "no-cache"


def test_public_static_conditional_revalidation() -> None:
    client = TestClient(create_app())

    first = client.get(
        "/static/app.js",
        headers={"Accept-Encoding": "gzip"},
    )

    assert first.status_code == 200
    assert "etag" not in first.headers

    second = client.get(
        "/static/app.js",
        headers={
            "Accept-Encoding": "gzip",
            "If-None-Match": '"identity-etag"',
        },
    )

    assert second.status_code == 200
    assert second.headers["content-encoding"] == "gzip"
    assert "etag" not in second.headers
    assert second.content == first.content


def test_private_route_is_not_gzip_wrapped() -> None:
    client = TestClient(create_app())

    response = client.get(
        "/api/auth/me",
        headers={"Accept-Encoding": "gzip"},
    )

    assert response.headers.get("content-encoding") != "gzip"


def test_png_is_not_compressed() -> None:
    client = TestClient(create_app())
    response = client.get(
        "/static/app-icon.png",
        headers={"Accept-Encoding": "gzip"},
    )
    assert response.status_code == 200
    assert "content-encoding" not in response.headers


def test_identity_etag_still_revalidates() -> None:
    client = TestClient(create_app())
    first = client.get(
        "/static/app.js",
        headers={"Accept-Encoding": "identity"},
    )
    assert first.headers.get("etag")

    second = client.get(
        "/static/app.js",
        headers={
            "Accept-Encoding": "identity",
            "If-None-Match": first.headers["etag"],
        },
    )
    assert second.status_code == 304


def test_gzip_does_not_reuse_identity_etag() -> None:
    client = TestClient(create_app())
    identity = client.get(
        "/static/app.js",
        headers={"Accept-Encoding": "identity"},
    )
    compressed = client.get(
        "/static/app.js",
        headers={
            "Accept-Encoding": "gzip",
            "If-None-Match": identity.headers["etag"],
        },
    )
    assert compressed.status_code == 200
    assert compressed.headers["content-encoding"] == "gzip"
    assert "etag" not in compressed.headers
