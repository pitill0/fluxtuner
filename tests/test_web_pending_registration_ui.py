# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_index_exposes_pending_registration_form() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-register-form" in response.text
    assert "Request access" in response.text
    assert "No email is sent" in response.text


def test_web_static_js_submits_pending_registration() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/account-requests.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    assert 'document.querySelector("[data-register-form]")' in app_response.text
    assert (
        'import { createAccountRequestsController } from "/static/js/account-requests.js";'
        in app_response.text
    )
    assert "export function createAccountRequestsController" in module_response.text
    assert "async function registerAccount(event)" in module_response.text
    assert 'fetchImpl("/api/auth/register"' in module_response.text
    assert "Account pending approval" not in module_response.text
