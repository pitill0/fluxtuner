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

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert 'document.querySelector("[data-register-form]")' in response.text
    assert "async function registerAccount(event)" in response.text
    assert 'fetch("/api/auth/register"' in response.text
    assert "Account pending approval" not in response.text
