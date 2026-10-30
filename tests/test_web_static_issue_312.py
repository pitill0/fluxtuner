"""Regression contracts for issue #312 static delivery."""

from pathlib import Path

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app
from fluxtuner.web.static_builds import create_static_snapshot


def test_versioned_head_matches_gzip_get(tmp_path, monkeypatch):
    from fluxtuner import paths

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")

    source = tmp_path / "source"
    source.mkdir()
    (source / "app.js").write_text("const value = 42;\n" * 200)

    root = paths.DATA_DIR / "web" / "static-builds"
    build = create_static_snapshot(source, root)

    client = TestClient(create_app())
    url = f"/static/build/{build.build_id}/app.js"
    headers = {"Accept-Encoding": "gzip"}

    get_response = client.get(url, headers=headers)
    head_response = client.head(url, headers=headers)

    assert get_response.status_code == head_response.status_code == 200
    assert head_response.content == b""

    for name in (
        "content-length",
        "content-encoding",
        "etag",
        "vary",
        "cache-control",
        "content-type",
    ):
        assert head_response.headers.get(name) == get_response.headers.get(name), name


def test_legacy_css_revalidates():
    client = TestClient(create_app())
    response = client.get(
        "/static/styles.css",
        headers={"Accept-Encoding": "identity"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"


def test_official_favicon_replaces_obsolete_declaration():
    client = TestClient(create_app())
    html = client.get("/").text

    assert 'href="/static/app-icon.png"' not in html
    assert 'href="/static/icons/icon-192.png"' in html


def test_official_compose_enables_versioned_static():
    import yaml

    compose = yaml.safe_load(Path("compose.yaml").read_text())
    service = compose["services"]["fluxtuner-web"]

    assert service["environment"]["FLUXTUNER_WEB_VERSIONED_STATIC"] == "1"
    assert "/data" in service["volumes"][0]
