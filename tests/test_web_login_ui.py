# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_index_exposes_login_ui() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-login-form" in response.text
    assert "data-auth-panel" in response.text
    assert "data-logout" in response.text


def test_web_static_js_does_not_store_auth_tokens() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "localStorage" not in response.text
    assert "sessionStorage" not in response.text
    assert "/api/auth/login" in response.text
    assert "/api/auth/logout" in response.text
    assert "/api/auth/me" in response.text
    assert "X-FluxTuner-CSRF" in response.text


def test_web_static_js_stops_playback_on_logout() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "async function logout()" in response.text
    assert "stopPlayback();\n    currentUser = null;" in response.text
    assert "function stopPlayback()" in response.text


def test_web_playlist_picker_replaces_prompt() -> None:
    client = TestClient(create_app())

    index_response = client.get("/")
    js_response = client.get("/static/app.js")

    assert index_response.status_code == 200
    assert js_response.status_code == 200
    assert "data-playlist-dialog" in index_response.text
    assert "data-playlist-select" in index_response.text
    assert 'window.prompt("Playlist name:")' not in js_response.text
    assert "async function openPlaylistDialog(station)" in js_response.text
    assert "async function submitPlaylistDialog(event)" in js_response.text
    assert "/api/playlists" in js_response.text


def test_web_index_has_minimal_hamburger_header() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert 'class="app-header"' in response.text
    assert 'data-mobile-menu-open="false"' in response.text
    assert 'class="app-header-actions"' in response.text
    assert "data-nav-toggle" in response.text
    assert 'aria-controls="app-menu"' in response.text
    assert 'aria-expanded="false"' in response.text
    assert 'id="app-menu"' in response.text
    assert "FluxTuner Web" in response.text
    assert "/static/app-icon.png" in response.text
    assert response.text.count("data-auth-user ") == 1
    assert response.text.count("data-logout") == 1
    assert response.text.count("data-nav-search") == 1
    assert response.text.count("data-nav-favorites") == 1
    assert response.text.count("data-nav-playlists") == 1
    assert response.text.count("data-nav-history") == 1


def test_web_index_keeps_app_private_until_authenticated() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-app-content hidden" in response.text
    assert 'class="hero app-hero"' not in response.text
    assert "Tune your radio library from any browser" not in response.text


def test_web_health_lives_inside_admin_not_header_menu() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Open health endpoint" not in response.text
    assert 'href="/api/health"' not in response.text
    assert '<details class="server-tools">' not in response.text
    assert "data-server-tools" not in response.text
    assert 'class="admin-health"' in response.text
    assert "data-health-check" in response.text
    assert "data-status" in response.text


def test_web_index_uses_real_icon_for_favicon() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/static/app-icon.png"' in response.text
    assert 'href="/static/favicon.svg"' not in response.text


def test_web_static_js_controls_mobile_menu() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert 'document.querySelector("[data-nav-toggle]")' in response.text
    assert "function setMobileMenuOpen(open)" in response.text
    assert "function closeMobileMenu()" in response.text
    assert "appHeader.dataset.mobileMenuOpen = nextState;" in response.text
    assert 'navToggleButton.setAttribute("aria-expanded", nextState);' in response.text


def test_web_static_js_admin_is_exclusive_view() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "function showRadioBrowserView()" in response.text
    assert "function showAdminView()" in response.text
    assert "searchPanel.hidden = true;" in response.text
    assert "searchPanel.hidden = false;" in response.text
    assert "adminPanel.hidden = true;" in response.text
    assert "adminPanel.hidden = false;" in response.text
    assert "showAdminView();" in response.text
    assert "adminPanel.hidden = false;\n\n    if (!adminUsersLoaded)" not in response.text


def test_web_css_has_clean_header_and_admin_view() -> None:
    client = TestClient(create_app())

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert "/* Clean app shell header and exclusive admin view */" in response.text
    assert ".app-menu" in response.text
    assert "display: none !important;" in response.text
    assert '.app-header[data-mobile-menu-open="true"] .app-menu' in response.text
    assert ".admin-health" in response.text
    assert "width: min(100%, 52rem) !important;" in response.text
    assert "width: min(50rem, calc(100% - 2rem)) !important;" in response.text


def test_web_static_serves_app_icon() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app-icon.png")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert len(response.content) > 1024


def test_web_admin_health_is_compact_and_collapsible() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-admin-health" in response.text
    assert "data-health-state" in response.text
    assert "data-health-summary" in response.text
    assert 'class="admin-health-details"' in response.text
    assert "Check server health" not in response.text


def test_web_static_js_formats_admin_health_summary() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert 'document.querySelector("[data-health-state]")' in response.text
    assert 'document.querySelector("[data-health-summary]")' in response.text
    assert "formatHealthSummary(payload)" in response.text
    assert "await checkHealth();" in response.text


def test_web_css_has_compact_admin_health_bar() -> None:
    client = TestClient(create_app())

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert "/* Compact admin health bar */" in response.text
    assert ".admin-health-details" in response.text
    assert "grid-template-columns: minmax(0, 1fr) auto !important;" in response.text
