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

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "/api/setup/status" in response.text
    assert "/api/setup/create-admin" in response.text
    assert "setup_token" in response.text
    assert "authToken" not in response.text
    assert "accessToken" not in response.text
    assert "sessionStorage" not in response.text
    assert "sessionStorage" not in response.text
