"""HTTP contracts for persistent versioned static assets."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fluxtuner import paths
from fluxtuner.web.app import create_app
from fluxtuner.web.static_builds import create_static_snapshot

IMMUTABLE = "public, max-age=31536000, immutable"


@pytest.fixture
def build_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    source = tmp_path / "source"
    (source / "js").mkdir(parents=True)

    # Larger than StaticCompression's gzip threshold.
    (source / "app.js").write_text(
        'import "./js/module.js";\n'
        + 'export const content = "'
        + "snapshot-integrity-" * 300
        + '";\n',
        encoding="utf-8",
    )
    (source / "js" / "module.js").write_text(
        "export const ready = true;\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")

    root = paths.DATA_DIR / "web" / "static-builds"
    build = create_static_snapshot(source, root)

    return TestClient(create_app()), build, source


def test_versioned_javascript_identity(build_client) -> None:
    client, build, source = build_client
    response = client.get(
        f"/static/build/{build.build_id}/app.js",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == IMMUTABLE
    assert "content-encoding" not in response.headers
    assert response.content == (source / "app.js").read_bytes()


def test_versioned_javascript_gzip_and_etag(build_client) -> None:
    client, build, _source = build_client
    url = f"/static/build/{build.build_id}/app.js"

    compressed = client.get(url, headers={"Accept-Encoding": "gzip"})

    assert compressed.status_code == 200
    assert compressed.headers["cache-control"] == IMMUTABLE
    assert compressed.headers["content-encoding"] == "gzip"
    assert compressed.headers["etag"].startswith('W/"gzip-')
    assert "Accept-Encoding" in compressed.headers["vary"]

    repeated = client.get(
        url,
        headers={
            "Accept-Encoding": "gzip",
            "If-None-Match": compressed.headers["etag"],
        },
    )

    assert repeated.status_code == 304
    assert repeated.content == b""
    assert repeated.headers["cache-control"] == IMMUTABLE
    assert repeated.headers["etag"] == compressed.headers["etag"]


def test_versioned_head_and_range(build_client) -> None:
    client, build, source = build_client
    url = f"/static/build/{build.build_id}/app.js"

    head = client.head(url, headers={"Accept-Encoding": "identity"})

    assert head.status_code == 200
    assert head.content == b""
    assert head.headers["cache-control"] == IMMUTABLE

    partial = client.get(
        url,
        headers={
            "Accept-Encoding": "gzip",
            "Range": "bytes=0-19",
        },
    )

    assert partial.status_code == 206
    assert partial.headers["cache-control"] == IMMUTABLE
    assert partial.content == (source / "app.js").read_bytes()[:20]
    assert "content-encoding" not in partial.headers


def test_versioned_missing_and_invalid_build(build_client) -> None:
    client, build, _source = build_client

    for url in (
        "/static/build/invalid/app.js",
        "/static/build/0000000000000000/app.js",
        f"/static/build/{build.build_id}/missing.js",
        f"/static/build/{build.build_id}/.fluxtuner-manifest.json",
    ):
        response = client.get(url)
        assert response.status_code == 404, url
        assert response.headers["cache-control"] == "no-store", url


def test_versioned_corruption_fails_closed(build_client) -> None:
    client, build, _source = build_client
    url = f"/static/build/{build.build_id}/app.js"

    (build.directory / "app.js").write_text(
        "corrupted\n",
        encoding="utf-8",
    )

    response = client.get(url)

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"


def test_versioned_symlink_fails_closed(build_client, tmp_path: Path) -> None:
    client, build, _source = build_client
    target = build.directory / "app.js"
    external = tmp_path / "external.js"
    external.write_text("export const leaked = true;\n")

    target.unlink()
    target.symlink_to(external)

    response = client.get(f"/static/build/{build.build_id}/app.js")

    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
    assert "leaked" not in response.text


def test_legacy_static_contract_remains_unchanged(build_client) -> None:
    client, _build, _source = build_client

    response = client.get(
        "/static/app.js",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_html_does_not_activate_versioned_urls(build_client) -> None:
    client, build, _source = build_client

    response = client.get(
        "/",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"
    assert f"/static/build/{build.build_id}/" not in response.text


def test_cached_build_keeps_verified_bytes_after_disk_change(build_client) -> None:
    client, build, source = build_client
    url = f"/static/build/{build.build_id}/app.js"
    expected = (source / "app.js").read_bytes()
    assert client.get(url, headers={"Accept-Encoding": "identity"}).content == expected
    (build.directory / "app.js").write_bytes(b"mutated on disk")
    response = client.get(url, headers={"Accept-Encoding": "identity"})
    assert response.status_code == 200
    assert response.content == expected
    assert response.headers["cache-control"] == IMMUTABLE


def test_versioned_invalid_range(build_client) -> None:
    client, build, _source = build_client
    response = client.get(
        f"/static/build/{build.build_id}/app.js",
        headers={"Range": "bytes=999999999-", "Accept-Encoding": "identity"},
    )
    assert response.status_code == 416
    assert response.headers["content-range"].startswith("bytes */")


def test_versioned_suffix_range(build_client) -> None:
    client, build, source = build_client
    response = client.get(
        f"/static/build/{build.build_id}/app.js",
        headers={"Range": "bytes=-10", "Accept-Encoding": "identity"},
    )
    assert response.status_code == 206
    assert response.content == (source / "app.js").read_bytes()[-10:]


def test_versioned_unknown_asset_not_cached_as_success(build_client) -> None:
    client, build, _source = build_client
    response = client.get(f"/static/build/{build.build_id}/missing.js")
    assert response.status_code == 404
    assert response.headers["cache-control"] == "no-store"
