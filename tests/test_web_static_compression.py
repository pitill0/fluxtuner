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
    assert first.headers["etag"].startswith('W/"gzip-')

    second = client.get(
        "/static/app.js",
        headers={
            "Accept-Encoding": "gzip",
            "If-None-Match": '"identity-etag"',
        },
    )

    assert second.status_code == 200
    assert second.headers["content-encoding"] == "gzip"
    assert second.headers["etag"] == first.headers["etag"]
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
    assert compressed.headers["etag"].startswith('W/"gzip-')
    assert compressed.headers["etag"] != identity.headers["etag"]


def test_gzip_has_distinct_weak_etag() -> None:
    client = TestClient(create_app())
    identity = client.get(
        "/static/app.js",
        headers={"Accept-Encoding": "identity"},
    )
    compressed = client.get(
        "/static/app.js",
        headers={"Accept-Encoding": "gzip"},
    )

    assert compressed.status_code == 200
    assert compressed.headers["content-encoding"] == "gzip"
    assert compressed.headers["etag"].startswith('W/"gzip-')
    assert compressed.headers["etag"] != identity.headers["etag"]


def test_gzip_matching_etag_returns_304() -> None:
    client = TestClient(create_app())
    first = client.get("/static/app.js", headers={"Accept-Encoding": "gzip"})

    second = client.get(
        "/static/app.js",
        headers={
            "Accept-Encoding": "gzip",
            "If-None-Match": first.headers["etag"],
        },
    )

    assert second.status_code == 304
    assert second.content == b""
    assert second.headers["etag"] == first.headers["etag"]
    assert second.headers["cache-control"] == "no-cache"
    assert "Accept-Encoding" in second.headers["vary"]
    assert "content-encoding" not in second.headers
    assert "content-length" not in second.headers


def test_gzip_nonmatching_etag_returns_200() -> None:
    client = TestClient(create_app())
    response = client.get(
        "/static/app.js",
        headers={
            "Accept-Encoding": "gzip",
            "If-None-Match": '"outdated"',
        },
    )

    assert response.status_code == 200
    assert response.headers["content-encoding"] == "gzip"
    assert response.content


def test_identity_etag_does_not_validate_gzip() -> None:
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
    assert compressed.headers["etag"] != identity.headers["etag"]


def test_small_manifest_is_not_gzip_revalidated() -> None:
    client = TestClient(create_app())
    first = client.get(
        "/static/site.webmanifest",
        headers={"Accept-Encoding": "gzip"},
    )

    assert first.status_code == 200
    assert "content-encoding" not in first.headers

    second = client.get(
        "/static/site.webmanifest",
        headers={
            "Accept-Encoding": "gzip",
            "If-None-Match": first.headers["etag"],
        },
    )

    assert second.status_code == 304
    assert second.content == b""


def test_gzip_304_completes_asgi_response() -> None:
    app = create_app()
    mount = next(route for route in app.routes if route.path == "/static")
    original = mount.app
    messages = []

    async def instrumented_app(scope, receive, send):
        async def recorded_send(message):
            messages.append(message.copy())
            await send(message)

        await original(scope, receive, recorded_send)

    mount.app = instrumented_app
    client = TestClient(app)

    first = client.get("/static/app.js", headers={"Accept-Encoding": "gzip"})
    messages.clear()

    second = client.get(
        "/static/app.js",
        headers={
            "Accept-Encoding": "gzip",
            "If-None-Match": first.headers["etag"],
        },
    )

    assert second.status_code == 304
    assert second.content == b""
    assert messages[0]["type"] == "http.response.start"
    assert messages[0]["status"] == 304
    assert messages[-1]["type"] == "http.response.body"
    assert messages[-1].get("body", b"") == b""
    assert messages[-1].get("more_body", False) is False


def test_gzip_head_and_range_preserve_native_responses() -> None:
    client = TestClient(create_app())

    identity = client.get(
        "/static/app.js",
        headers={"Accept-Encoding": "identity"},
    )

    head = client.head(
        "/static/app.js",
        headers={"Accept-Encoding": "gzip"},
    )
    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["etag"] == identity.headers["etag"]
    assert "content-encoding" not in head.headers

    conditional_head = client.head(
        "/static/app.js",
        headers={
            "Accept-Encoding": "gzip",
            "If-None-Match": identity.headers["etag"],
        },
    )
    assert conditional_head.status_code == 304
    assert conditional_head.content == b""

    partial = client.get(
        "/static/app.js",
        headers={
            "Accept-Encoding": "gzip",
            "Range": "bytes=0-99",
        },
    )
    assert partial.status_code == 206
    assert partial.content == identity.content[:100]
    assert partial.headers["etag"] == identity.headers["etag"]
    assert partial.headers["content-range"].startswith("bytes 0-99/")
    assert "content-encoding" not in partial.headers


def test_explicit_gzip_refusal_is_respected() -> None:
    client = TestClient(create_app())

    for encoding in ("gzip;q=0", "br, gzip;q=0", "identity"):
        response = client.get(
            "/static/app.js",
            headers={"Accept-Encoding": encoding},
        )
        assert response.status_code == 200
        assert "content-encoding" not in response.headers
        assert response.headers.get("etag")
