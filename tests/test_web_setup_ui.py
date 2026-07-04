# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_index_exposes_first_run_setup_ui() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-setup-panel" in response.text
    assert "data-setup-form" in response.text
    assert "data-setup-token-field" in response.text


def test_web_static_js_wires_first_run_setup_api() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    setup_response = client.get("/static/js/setup.js")

    assert app_response.status_code == 200
    assert setup_response.status_code == 200
    assert "/static/js/setup.js" in app_response.text
    assert "/api/setup/status" in setup_response.text
    assert "/api/setup/create-admin" in setup_response.text
    assert "setup_token" in setup_response.text
    assert "authToken" not in setup_response.text
    assert "accessToken" not in setup_response.text
    assert "sessionStorage" not in setup_response.text
