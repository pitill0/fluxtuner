# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_index_exposes_login_ui() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-login-form" in response.text
    assert 'method="post" action="/api/auth/login" data-login-form' in response.text
    assert "data-auth-panel" in response.text
    assert "data-logout" in response.text


def test_web_static_js_does_not_store_auth_tokens() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    api_response = client.get("/static/js/api.js")
    auth_response = client.get("/static/js/auth.js")

    assert app_response.status_code == 200
    assert api_response.status_code == 200
    assert auth_response.status_code == 200
    assert "sessionStorage" not in app_response.text
    assert "sessionStorage" not in api_response.text
    assert "sessionStorage" not in auth_response.text
    assert "/api/auth/login" in auth_response.text
    assert "/api/auth/logout" in auth_response.text
    assert "/api/auth/me" in auth_response.text
    assert 'import { createAuthController } from "/static/js/auth.js";' in app_response.text
    assert "X-FluxTuner-CSRF" in api_response.text
    assert "localStorage" not in api_response.text
    assert "localStorage" not in auth_response.text


def test_web_static_js_shows_login_errors_after_auth_ui_reset() -> None:
    client = TestClient(create_app())

    auth_response = client.get("/static/js/auth.js")

    assert auth_response.status_code == 200
    assert "authMessageNode.hidden = false;" in auth_response.text
    assert "error instanceof Error ? error.message : String(error)" in auth_response.text
    assert "Invalid username or password." in auth_response.text


def test_web_static_js_stops_playback_on_logout() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    auth_response = client.get("/static/js/auth.js")
    player_response = client.get("/static/js/player.js")

    assert app_response.status_code == 200
    assert auth_response.status_code == 200
    assert player_response.status_code == 200
    assert "async function logout()" in auth_response.text
    assert "stopPlayback();" in auth_response.text
    assert "setCurrentUser(null);" in auth_response.text
    assert "function stopPlayback()" in player_response.text


def test_web_playlist_picker_replaces_station_add_prompt() -> None:
    client = TestClient(create_app())

    index_response = client.get("/")
    app_response = client.get("/static/app.js")
    playlists_response = client.get("/static/js/playlists.js")

    assert index_response.status_code == 200
    assert app_response.status_code == 200
    assert playlists_response.status_code == 200
    assert "data-playlist-dialog" in index_response.text
    assert "data-playlist-select" in index_response.text
    assert "window.prompt" not in app_response.text
    assert "window.prompt" not in playlists_response.text
    assert "async function openPlaylistDialog(station)" in playlists_response.text
    assert "async function submitPlaylistDialog(event)" in playlists_response.text
    assert "async function createPlaylist(playlistName)" in playlists_response.text
    assert "/api/playlists" in playlists_response.text


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

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/ui-shell.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert 'document.querySelector("[data-nav-toggle]")' in app_response.text
    assert "function setMobileMenuOpen(open)" in module_response.text
    assert "function closeMobileMenu()" in module_response.text
    assert "appHeader.dataset.mobileMenuOpen = nextState;" in module_response.text
    assert 'navToggleButton.setAttribute("aria-expanded", nextState);' in module_response.text


def test_web_static_js_admin_is_exclusive_view() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/ui-shell.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert "function showRadioBrowserView()" in module_response.text
    assert "function showAdminView()" in module_response.text
    assert "searchPanel.hidden = true;" in module_response.text
    assert "searchPanel.hidden = false;" in module_response.text
    assert "adminPanel.hidden = true;" in module_response.text
    assert "adminPanel.hidden = false;" in module_response.text
    assert "showAdminView();" in app_response.text
    assert "adminPanel.hidden = false;\n\n    if (!adminUsersLoaded)" not in app_response.text


def test_web_css_has_clean_header_and_admin_view() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    shell_response = client.get("/static/shell.css")
    admin_response = client.get("/static/admin.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert shell_response.status_code == 200
    assert admin_response.status_code == 200

    styles_link = '<link rel="stylesheet" href="/static/styles.css">'
    shell_link = '<link rel="stylesheet" href="/static/shell.css">'
    admin_link = '<link rel="stylesheet" href="/static/admin.css">'
    assert styles_link in page_response.text
    assert shell_link in page_response.text
    assert admin_link in page_response.text
    assert page_response.text.index(styles_link) < page_response.text.index(shell_link)
    assert page_response.text.index(shell_link) < page_response.text.index(admin_link)

    for selector in (
        ".shell",
        ".app-header",
        ".app-brand",
        ".app-user",
        ".app-menu-toggle",
        ".app-menu",
        ".app-nav",
        ".theme-toggle",
        ".app-user[hidden]",
        ".app-content[hidden]",
    ):
        assert selector in shell_response.text

    assert '.app-header[data-mobile-menu-open="true"] .app-menu' in shell_response.text
    assert "@media (max-width: 38rem)" in shell_response.text
    assert "@media (max-width: 30rem)" in shell_response.text
    assert "/* Legacy shell ownership completed */" in shell_response.text
    assert "min-width: 4.35rem !important;" in shell_response.text
    assert "display: none !important;" in shell_response.text
    assert "text-decoration: none;" in shell_response.text
    assert ".app-brand:hover" in shell_response.text
    assert "color: var(--text);" in shell_response.text
    assert "transform: none;" in shell_response.text

    for selector in (
        "\n.shell {",
        "\n.app-header {",
        "\n.app-brand {",
        "\n.app-brand-icon {",
        "\n.app-nav {",
        "\n.app-user {",
        "\n.server-tools {",
        "\n.app-content {",
        "\n.theme-toggle {",
        ".app-user[hidden]",
        ".app-content[hidden]",
    ):
        assert selector not in styles_response.text

    assert "/* Clean app shell header and exclusive admin view */" not in styles_response.text
    assert ".admin-health" in admin_response.text
    assert "width: min(100%, 52rem);" in admin_response.text


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

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/health.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert 'document.querySelector("[data-health-state]")' in app_response.text
    assert 'document.querySelector("[data-health-summary]")' in app_response.text
    assert 'from "/static/js/health.js"' in app_response.text
    assert "formatHealthSummary(payload)" in module_response.text
    assert "await checkHealth();" in app_response.text


def test_web_css_has_compact_admin_health_bar() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    admin_response = client.get("/static/admin.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert admin_response.status_code == 200

    styles_link = '<link rel="stylesheet" href="/static/styles.css">'
    admin_link = '<link rel="stylesheet" href="/static/admin.css">'
    assert styles_link in page_response.text
    assert admin_link in page_response.text
    assert page_response.text.index(styles_link) < page_response.text.index(admin_link)

    assert '@import url("./admin.css");' not in styles_response.text
    assert "/* Compact admin health bar */" not in styles_response.text
    assert "/* Compact admin health bar */" in admin_response.text
    assert ".admin-health-details" in admin_response.text
    assert "grid-template-columns: minmax(0, 1fr) auto;" in admin_response.text
    assert ".admin-panel" in admin_response.text
    assert ".player-debug-panel" in admin_response.text
    assert ".player-debug-actions" in admin_response.text
    assert ".player-debug-export" in admin_response.text
    assert "color: var(--muted);" in admin_response.text
    assert "width: min(100%, 52rem)" not in styles_response.text
    assert "margin-inline: auto" in admin_response.text
    assert ".player-debug-panel" not in styles_response.text
    assert ".player-debug-actions" not in styles_response.text
    assert "\n.player-debug-export {" not in styles_response.text
    assert "var(--text-muted)" not in admin_response.text
    assert "!important" not in admin_response.text


def test_web_header_has_theme_toggle() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-theme-toggle" in response.text
    assert "data-theme-label" in response.text
    assert "Switch theme" in response.text


def test_web_static_js_controls_theme_without_auth_storage() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    theme_response = client.get("/static/js/theme.js")

    assert app_response.status_code == 200
    assert theme_response.status_code == 200
    assert 'const THEME_STORAGE_KEY = "fluxtuner.theme";' in theme_response.text
    assert "function applyTheme(theme)" in theme_response.text
    assert "function toggleTheme()" in theme_response.text
    assert "storedThemePreference() || systemThemePreference()" in theme_response.text
    assert 'document.querySelector("[data-theme-toggle]")' in app_response.text
    assert "authToken" not in app_response.text
    assert "authToken" not in theme_response.text
    assert "accessToken" not in app_response.text
    assert "accessToken" not in theme_response.text
    assert "sessionStorage" not in app_response.text
    assert "sessionStorage" not in theme_response.text


def test_web_css_has_light_theme() -> None:
    client = TestClient(create_app())

    styles_response = client.get("/static/styles.css")
    shell_response = client.get("/static/shell.css")

    assert styles_response.status_code == 200
    assert shell_response.status_code == 200
    assert ':root[data-theme="light"]' in styles_response.text
    assert 'html[data-theme="light"] body' in styles_response.text
    assert 'html[data-theme="light"] body::before' in styles_response.text
    assert ".theme-toggle" in shell_response.text
    assert 'html[data-theme="light"] .theme-toggle span::before' in shell_response.text
    assert "\n.theme-toggle {" not in styles_response.text


def test_web_static_js_hides_player_without_auth_and_resets_non_admin_view() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/ui-shell.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert 'playerBar.removeAttribute("hidden")' in module_response.text
    assert 'playerBar.setAttribute("hidden", "")' in module_response.text
    assert "showRadioBrowserView();" in module_response.text
    assert "searchPanel.hidden" in module_response.text


def test_web_css_has_accessible_playlist_dialog_theme() -> None:
    client = TestClient(create_app())

    styles_response = client.get("/static/styles.css")
    forms_response = client.get("/static/forms.css")
    dialogs_response = client.get("/static/dialogs.css")

    assert styles_response.status_code == 200
    assert forms_response.status_code == 200
    assert dialogs_response.status_code == 200

    assert "--field-muted" in forms_response.text
    assert "input::placeholder" in forms_response.text
    assert "--field-muted" not in styles_response.text
    assert "input::placeholder" not in styles_response.text

    assert "--dialog-bg" in styles_response.text
    assert "--dialog-backdrop" in styles_response.text
    assert ".playlist-dialog {" in dialogs_response.text
    assert ".playlist-dialog-card {" in dialogs_response.text
    assert 'html[data-theme="light"] .playlist-dialog-card' in dialogs_response.text
    assert "background: var(--dialog-backdrop)" in dialogs_response.text
    assert "var(--dialog-bg)" in dialogs_response.text

    assert "\n.playlist-dialog {" not in styles_response.text
    assert "\n.playlist-dialog-card {" not in styles_response.text


def test_web_player_starts_hidden_until_authenticated() -> None:
    client = TestClient(create_app())

    html = client.get("/")
    player_css = client.get("/static/player.css")

    assert html.status_code == 200
    assert player_css.status_code == 200
    assert 'data-player-bar aria-live="polite" hidden' in html.text
    assert ".player-bar[hidden]" in player_css.text
    assert "display: none !important;" in player_css.text


def test_web_static_js_closes_mobile_menu_from_outside_click() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert 'document.addEventListener("click"' in response.text
    assert "appHeader.contains(event.target)" in response.text
    assert 'event.key === "Escape"' in response.text


def test_web_static_js_controls_player_visibility_from_auth_ui() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/ui-shell.js")
    setup_response = client.get("/static/js/setup.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert setup_response.status_code == 200
    assert "function setPlayerVisible(isVisible)" in module_response.text
    assert "setPlayerVisible(!setupAvailable && authenticated);" in setup_response.text
    assert 'playerBar.removeAttribute("hidden")' in module_response.text
    assert 'playerBar.setAttribute("hidden", "")' in module_response.text


def test_web_static_js_resets_search_view_on_auth_changes() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/ui-shell.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert "function resetRadioBrowserView()" in module_response.text
    assert 'setCurrentView("search");' in module_response.text
    assert 'setCurrentPlaylistName("");' in module_response.text
    assert 'setResultsHeader("Radio Browser", "Search stations");' in module_response.text
    assert "resetRadioBrowserView();" in app_response.text
