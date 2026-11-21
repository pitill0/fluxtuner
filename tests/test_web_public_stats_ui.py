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
    assert 'from "./js/public-stats.js"' in app_response.text
    assert '"/api/public/stats"' in public_stats_response.text
    assert "loadPublicStats" in public_stats_response.text
    assert "renderPublicStats" in public_stats_response.text
    assert "renderPublicStatTile" in public_stats_response.text
    assert "No public activity yet." in public_stats_response.text
    assert '"active user", "active users"' in public_stats_response.text


def test_public_trending_ui_fetches_independently_and_escapes_names() -> None:
    client = TestClient(create_app())

    script = client.get("/static/js/public-stats.js")
    styles = client.get("/static/public.css")

    assert script.status_code == 200
    assert styles.status_code == 200
    assert 'fetchImpl("/api/public/trending"' in script.text
    assert 'escapeHtml(station.name || "Unknown station")' in script.text
    assert "Trending availability must never hide existing public statistics" in script.text
    assert "Weekly trends will appear when enough listening activity is available." in script.text
    assert "public-stats-trending" in script.text
    assert ".public-trending-list" in styles.text
    assert "grid-template-columns: 1fr" in styles.text


def test_public_featured_ui_fetches_independently_and_escapes_name() -> None:
    client = TestClient(create_app())
    script = client.get("/static/js/public-stats.js")
    styles = client.get("/static/public.css")
    assert script.status_code == 200
    assert styles.status_code == 200
    assert 'fetchImpl("/api/public/featured"' in script.text
    assert "escapeHtml(featuredName)" in script.text
    assert "Featured availability must never hide existing public statistics" in script.text
    assert "Station to discover" in script.text
    assert ".public-stats-featured" in styles.text


def test_discovery_selection_ui_is_ephemeral_and_csrf_protected() -> None:
    client = TestClient(create_app())
    featured = client.get("/static/js/public-stats.js")
    pending = client.get("/static/js/discovery-pending.js")
    app = client.get("/static/app.js")
    styles = client.get("/static/public.css")

    assert all(response.status_code == 200 for response in (featured, pending, app, styles))
    assert "data-featured-save" in featured.text
    assert "escapeHtml(featuredName)" in featured.text
    assert "onSelect(selection)" in featured.text
    assert "discoverySessionStorage()" in app.text
    assert "window.sessionStorage" in pending.text
    assert "apiFetch: (...args) => apiFetch(...args)" in app.text
    assert "await discoveryPending.redeem()" in app.text
    assert "MAX_AGE_MS = 15 * 60 * 1000" in pending.text
    assert "storage?.removeItem(STORAGE_KEY)" in pending.text
    assert '"/api/public/featured/redeem"' in pending.text
    assert 'method: "POST"' in pending.text
    assert ".public-featured-save" in styles.text
    assert "html[data-theme] .public-featured-save:hover" in styles.text
    assert "background: var(--action-fill-hover);" in styles.text
    assert "color: #fff;" in styles.text


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
    events_response = client.get("/static/js/app-events.js")
    navigation_response = client.get("/static/js/navigation.js")

    assert app_response.status_code == 200
    assert events_response.status_code == 200
    assert navigation_response.status_code == 200
    assert "function closeOpenDialog()" in navigation_response.text
    assert 'event.key === "Escape"' in events_response.text
    assert "closeOpenDialog()" in events_response.text
    assert "closeRegisterDialog" in navigation_response.text
    assert "closePasswordChangeDialog" in navigation_response.text
    assert "recoveryCodesRegenerateDialog" in navigation_response.text
    assert "closeRecoveryCodeRegenerationDialog" in navigation_response.text
