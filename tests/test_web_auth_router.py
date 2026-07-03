# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app
from fluxtuner.web.routes.auth import router

EXPECTED_AUTH_ROUTES = {
    "/api/auth/register",
    "/api/auth/password-change-requests",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
}


def test_auth_router_registers_auth_routes() -> None:
    paths = {route.path for route in router.routes}

    assert paths >= EXPECTED_AUTH_ROUTES


def test_create_app_includes_auth_router() -> None:
    client = TestClient(create_app())

    paths = set(client.app.openapi()["paths"])

    assert paths >= EXPECTED_AUTH_ROUTES
