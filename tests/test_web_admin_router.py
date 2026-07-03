# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app
from fluxtuner.web.routes.admin import router

EXPECTED_ADMIN_ROUTES = {
    "/api/admin/password-change-requests",
    "/api/admin/password-change-requests/{request_id}/approve",
    "/api/admin/password-change-requests/{request_id}/reject",
    "/api/admin/users",
    "/api/admin/users/{username}/password",
    "/api/admin/users/{username}/deactivate",
    "/api/admin/users/{username}/activate",
    "/api/admin/users/{username}",
    "/api/admin/users/{username}/approve",
    "/api/admin/users/{username}/reject",
    "/api/admin/users/{username}/admin",
}


def test_admin_router_registers_admin_routes() -> None:
    paths = {route.path for route in router.routes}

    assert paths >= EXPECTED_ADMIN_ROUTES


def test_create_app_includes_admin_router() -> None:
    client = TestClient(create_app())

    paths = set(client.app.openapi()["paths"])

    assert paths >= EXPECTED_ADMIN_ROUTES
