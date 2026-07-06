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

    app_response = client.get("/static/app.js")
    admin_response = client.get("/static/js/admin.js")

    assert app_response.status_code == 200
    assert admin_response.status_code == 200
    assert 'import { createAdminController } from "/static/js/admin.js";' in app_response.text
    assert "/api/admin/users" in admin_response.text
    assert "data-admin-user-action" in admin_response.text
    assert 'data-admin-user-action="delete"' in admin_response.text
    assert "DELETE ${username}" in admin_response.text
    assert '<details class="admin-user-danger-zone">' in admin_response.text
    assert "<summary>${dangerTitle}</summary>" in admin_response.text
    assert "Deleting a user is permanent and cannot be undone." in admin_response.text
    assert "data-admin-user-danger-feedback" in admin_response.text
    assert "Confirmation did not match" in admin_response.text
    assert "authToken" not in app_response.text
    assert "authToken" not in admin_response.text
    assert "accessToken" not in app_response.text
    assert "accessToken" not in admin_response.text
    assert "sessionStorage" not in app_response.text
    assert "sessionStorage" not in admin_response.text


def test_web_static_js_renders_only_applicable_admin_user_actions() -> None:
    client = TestClient(create_app())

    response = client.get("/static/js/admin.js")

    assert response.status_code == 200
    assert "function adminUserActions(user, username, isCurrentUser = false)" in response.text
    assert 'approvalStatus === "pending"' in response.text
    assert 'approvalStatus === "approved"' in response.text
    assert 'approvalStatus === "rejected"' not in response.text
    assert 'approvalStatus === "disabled"' not in response.text
    assert 'actions.push(adminUserActionButton("approve", username, "Approve"));' in response.text
    assert 'actions.push(adminUserActionButton("reject", username, "Reject"));' in response.text
    assert 'actions.push(adminUserActionButton("activate", username, "Activate"));' in response.text
    assert (
        'actions.push(adminUserActionButton("deactivate", username, "Deactivate"));'
        in response.text
    )
    assert (
        'actions.push(adminUserActionButton("grant-admin", username, "Grant admin"));'
        in response.text
    )
    assert (
        'actions.push(adminUserActionButton("revoke-admin", username, "Revoke admin"));'
        in response.text
    )
    assert "const userActions = adminUserActions(user, username, isCurrentUser);" in response.text
    assert "if (!isCurrentUser)" in response.text
    assert '<div class="admin-user-actions-normal">' in response.text
    assert "${userActions}" in response.text
    assert (
        'data-admin-user-action="activate" data-admin-username="${username}">Activate</button>'
        not in response.text
    )
    assert (
        'data-admin-user-action="approve" data-admin-username="${username}">Approve</button>'
        not in response.text
    )
