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


def test_web_index_uses_compact_app_header() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert 'class="app-topbar"' in response.text
    assert "data-nav-favorites" in response.text
    assert "data-nav-playlists" in response.text
    assert "data-nav-history" in response.text
    assert "data-nav-admin" in response.text
    assert response.text.count("data-logout") == 1
    assert response.text.count("data-auth-user ") == 1
