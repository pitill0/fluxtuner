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
