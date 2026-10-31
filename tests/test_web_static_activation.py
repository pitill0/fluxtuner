"""Versioned static activation and safe fallback contracts."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fluxtuner import paths
from fluxtuner.web import app as app_module
from fluxtuner.web import static_routes
from fluxtuner.web.static_builds import (
    StaticBuildError,
    create_static_snapshot,
)

BUILD_PATTERN = re.compile(r"/static/build/([0-9a-f]{16})/")


@pytest.fixture
def isolated_static_data(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    data = tmp_path / "data"
    monkeypatch.setattr(paths, "DATA_DIR", data)
    monkeypatch.delenv("FLUXTUNER_WEB_VERSIONED_STATIC", raising=False)
    return data


def test_versioned_static_is_opt_in(
    isolated_static_data: Path,
) -> None:
    client = TestClient(app_module.create_app())
    response = client.get("/")

    assert response.status_code == 200
    assert 'src="/static/app.js"' in response.text
    assert 'href="/static/styles.css"' in response.text
    assert "/static/build/" not in response.text
    assert not (isolated_static_data / "web" / "static-builds").exists()


def test_activation_publishes_before_html(
    isolated_static_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXTUNER_WEB_VERSIONED_STATIC", "1")

    client = TestClient(app_module.create_app())
    html = client.get("/")

    assert html.status_code == 200
    assert html.headers["cache-control"] == "no-cache"

    matches = set(BUILD_PATTERN.findall(html.text))
    assert len(matches) == 1

    build_id = matches.pop()
    prefix = f"/static/build/{build_id}"

    root = isolated_static_data / "web" / "static-builds"
    assert (root / build_id).is_dir()

    assert f'src="{prefix}/app.js"' in html.text
    assert f'href="{prefix}/styles.css"' in html.text
    assert f'href="{prefix}/site.webmanifest"' in html.text
    assert f'src="{prefix}/brand-icon.webp"' in html.text

    for asset in (
        "app.js",
        "styles.css",
        "js/player.js",
        "site.webmanifest",
        "icons/icon-192.png",
    ):
        response = client.get(
            f"{prefix}/{asset}",
            headers={"Accept-Encoding": "identity"},
        )
        assert response.status_code == 200, asset
        assert response.headers["cache-control"].endswith("immutable")

    assert client.get("/static/app.js").status_code == 200


def test_identical_startups_reuse_existing_snapshot(
    isolated_static_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXTUNER_WEB_VERSIONED_STATIC", "1")

    first = TestClient(app_module.create_app()).get("/").text
    second = TestClient(app_module.create_app()).get("/").text

    assert first == second
    assert len(set(BUILD_PATTERN.findall(first))) == 1

    root = isolated_static_data / "web" / "static-builds"
    assert len(list(root.glob("[0-9a-f]" * 16))) == 1
    assert not list(root.glob(".tmp-*"))


def test_publication_failure_uses_legacy_urls(
    isolated_static_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FLUXTUNER_WEB_VERSIONED_STATIC", "1")

    def fail_publication(*_args, **_kwargs):
        raise StaticBuildError("Simulated publication failure")

    monkeypatch.setattr(
        static_routes,
        "create_static_snapshot",
        fail_publication,
    )

    client = TestClient(app_module.create_app())
    html = client.get("/")

    assert html.status_code == 200
    assert 'src="/static/app.js"' in html.text
    assert 'href="/static/styles.css"' in html.text
    assert "/static/build/" not in html.text
    assert client.get("/static/app.js").status_code == 200


def test_previous_build_remains_available(
    isolated_static_data: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    root = isolated_static_data / "web" / "static-builds"
    older_source = tmp_path / "old-source"
    older_source.mkdir()
    (older_source / "old.js").write_text(
        "export const old = true;\n",
        encoding="utf-8",
    )
    previous = create_static_snapshot(older_source, root)

    monkeypatch.setenv("FLUXTUNER_WEB_VERSIONED_STATIC", "1")
    client = TestClient(app_module.create_app())

    current_html = client.get("/").text
    current_ids = set(BUILD_PATTERN.findall(current_html))

    assert len(current_ids) == 1
    assert previous.build_id not in current_ids

    old_asset = client.get(
        f"/static/build/{previous.build_id}/old.js",
        headers={"Accept-Encoding": "identity"},
    )

    assert old_asset.status_code == 200
    assert old_asset.content == b"export const old = true;\n"
    assert old_asset.headers["cache-control"].endswith("immutable")
    assert (root / previous.build_id / "old.js").is_file()


def test_manifest_icons_resolve_in_legacy_and_versioned_routes(
    isolated_static_data: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json
    from urllib.parse import urljoin, urlsplit

    monkeypatch.setenv("FLUXTUNER_WEB_VERSIONED_STATIC", "1")
    client = TestClient(app_module.create_app())

    html = client.get("/").text
    matches = set(BUILD_PATTERN.findall(html))
    assert len(matches) == 1
    build_id = matches.pop()

    for manifest_url in (
        "/static/site.webmanifest",
        f"/static/build/{build_id}/site.webmanifest",
    ):
        response = client.get(manifest_url)
        assert response.status_code == 200

        manifest = json.loads(response.content)
        assert len(manifest["icons"]) == 3

        for icon in manifest["icons"]:
            reference = icon["src"]
            assert not reference.startswith("/")
            resolved = urljoin(manifest_url, reference)
            assert urlsplit(resolved).path.startswith(manifest_url.rsplit("/", 1)[0] + "/icons/")
            icon_response = client.get(resolved)
            assert icon_response.status_code == 200

            if "/static/build/" in manifest_url:
                assert (
                    icon_response.headers["cache-control"] == "public, max-age=31536000, immutable"
                )
