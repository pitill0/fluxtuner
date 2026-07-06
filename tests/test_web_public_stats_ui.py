from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_index_includes_public_stats_card() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-public-entry" in response.text
    assert "public-intro-panel" in response.text
    assert "data-public-stats" in response.text
    assert "public-stats-panel" in response.text
    assert "data-public-stats-content" in response.text
    assert "data-public-stats-message" in response.text
    assert "Your private listening space" in response.text
    assert "Server activity" in response.text
    assert "Public stats" in response.text
    assert "Anonymous aggregate usage and listening stats" in response.text


def test_web_static_js_loads_public_stats() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    public_stats_response = client.get("/static/js/public-stats.js")

    assert app_response.status_code == 200
    assert public_stats_response.status_code == 200
    assert 'from "/static/js/public-stats.js"' in app_response.text
    assert '"/api/public/stats"' in public_stats_response.text
    assert "loadPublicStats" in public_stats_response.text
    assert "renderPublicStats" in public_stats_response.text
    assert "renderPublicStatTile" in public_stats_response.text
    assert "No public activity yet." in public_stats_response.text
    assert '"user", "users"' in public_stats_response.text


def test_web_static_css_styles_public_stats() -> None:
    client = TestClient(create_app())

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert ".public-entry" in response.text
    assert ".public-intro-panel" in response.text
    assert ".public-stats-panel" in response.text
    assert ".public-stats-card" in response.text
    assert ".public-stats-list" in response.text
    assert ".public-stats-totals" in response.text
    assert ".public-stat-tile" in response.text
    assert ".public-stats-message" in response.text


def test_web_static_js_closes_public_dialogs_with_escape() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "function closeOpenDialog" in response.text
    assert 'event.key === "Escape"' in response.text
    assert "closeRegisterDialog" in response.text
    assert "closePasswordChangeDialog" in response.text
