# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_index_exposes_pending_registration_form() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-register-form" in response.text
    assert 'method="post" action="/api/auth/register" data-register-form' in response.text
    assert (
        'method="post" action="/api/auth/recover-password" data-password-change-form'
        in response.text
    )
    assert 'name="recovery_code"' in response.text

    recovery_dialog = response.text.split(
        "data-password-change-dialog",
        1,
    )[1].split(
        "data-register-dialog",
        1,
    )[0]

    assert "Note for admin" not in recovery_dialog
    assert "/api/auth/password-change-requests" not in response.text
    assert "administrator approves" not in response.text
    assert "data-recovery-codes-dialog" in response.text
    assert "data-recovery-codes-list" in response.text
    assert "data-recovery-codes-close" in response.text
    assert "Request access" in response.text
    assert "No email is sent" in response.text


def test_web_static_js_submits_pending_registration() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    module_response = client.get("/static/js/account-requests.js")

    assert app_response.status_code == 200
    assert module_response.status_code == 200
    elements_response = client.get("/static/js/app-elements.js")
    assert elements_response.status_code == 200
    assert 'root.querySelector("[data-register-form]")' in elements_response.text
    assert (
        'import { createAccountRequestsController } from "/static/js/account-requests.js";'
        in app_response.text
    )
    assert "export function createAccountRequestsController" in module_response.text
    assert "async function registerAccount(event)" in module_response.text
    assert 'fetchImpl("/api/auth/register"' in module_response.text
    assert "Account pending approval" not in module_response.text


def test_web_static_js_uses_recovery_code_password_recovery() -> None:
    client = TestClient(create_app())

    module_response = client.get("/static/js/account-requests.js")
    auth_response = client.get("/static/js/auth.js")
    app_response = client.get("/static/app.js")
    elements_response = client.get("/static/js/app-elements.js")

    assert module_response.status_code == 200
    assert auth_response.status_code == 200
    assert app_response.status_code == 200
    assert elements_response.status_code == 200

    assert 'fetchImpl("/api/auth/recover-password"' in module_response.text
    assert "/api/auth/password-change-requests" not in module_response.text
    assert 'formData.get("recovery_code")' in module_response.text
    assert (
        "note"
        not in module_response.text.split('fetchImpl("/api/auth/recover-password"', 1)[1].split(
            "});", 1
        )[0]
    )

    assert "function showRecoveryCodes" in module_response.text
    assert "recoveryCodesListNode" in module_response.text
    assert "recoveryCodesDialog" in module_response.text

    assert "showRecoveryCodes(payload.recovery_codes)" in auth_response.text
    assert "showRecoveryCodes," in app_response.text

    assert 'root.querySelector("[data-recovery-codes-dialog]")' in elements_response.text
    assert 'root.querySelector("[data-recovery-codes-list]")' in elements_response.text
