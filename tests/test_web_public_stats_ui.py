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

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    public_response = client.get("/static/public.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert public_response.status_code == 200

    auth_link = '<link rel="stylesheet" href="/static/auth.css">'
    public_link = '<link rel="stylesheet" href="/static/public.css">'
    dashboard_link = '<link rel="stylesheet" href="/static/dashboard.css">'
    assert auth_link in page_response.text
    assert public_link in page_response.text
    assert dashboard_link in page_response.text
    assert page_response.text.index(auth_link) < page_response.text.index(public_link)
    assert page_response.text.index(public_link) < page_response.text.index(dashboard_link)

    owned_selectors = (
        ".public-entry",
        ".public-intro-panel",
        ".public-intro-copy",
        ".public-intro-points",
        ".public-entry .auth-panel",
        ".public-entry .auth-form",
        ".public-entry .auth-secondary-actions",
        ".public-stats-panel",
        ".public-stats-content",
        ".public-stats-card",
        ".public-stats-list",
        ".public-stats-totals",
        ".public-stat-tile",
        ".public-stats-message",
    )
    for selector in owned_selectors:
        assert selector in public_response.text
        assert selector not in styles_response.text

    assert "Public entry, authentication composition" in public_response.text


def test_web_static_js_closes_public_dialogs_with_escape() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    navigation_response = client.get("/static/js/navigation.js")

    assert app_response.status_code == 200
    assert navigation_response.status_code == 200
    assert "function closeOpenDialog()" in navigation_response.text
    assert 'event.key === "Escape"' in app_response.text
    assert "closeOpenDialog()" in app_response.text
    assert "closeRegisterDialog" in navigation_response.text
    assert "closePasswordChangeDialog" in navigation_response.text
