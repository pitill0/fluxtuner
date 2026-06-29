# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_index_exposes_admin_user_ui() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-admin-panel" in response.text
    assert "data-admin-create-user-form" in response.text
    assert "data-admin-password-form" in response.text
    assert "data-admin-load-users" in response.text


def test_web_static_js_wires_admin_user_api() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "/api/admin/users" in response.text
    assert "data-admin-user-action" in response.text
    assert "authToken" not in response.text
    assert "accessToken" not in response.text
    assert "sessionStorage" not in response.text
    assert "sessionStorage" not in response.text
