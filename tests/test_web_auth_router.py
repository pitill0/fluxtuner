# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app
from fluxtuner.web.routes.auth import router

EXPECTED_AUTH_ROUTES = {
    "/api/auth/register",
    "/api/auth/recover-password",
    "/api/auth/recovery-codes/regenerate",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/me",
}

REMOVED_AUTH_ROUTES = {
    "/api/auth/password-change-requests",
}


def test_auth_router_registers_auth_routes() -> None:
    paths = {route.path for route in router.routes}

    assert paths >= EXPECTED_AUTH_ROUTES


def test_create_app_includes_auth_router() -> None:
    client = TestClient(create_app())

    paths = set(client.app.openapi()["paths"])

    assert paths >= EXPECTED_AUTH_ROUTES


def test_auth_router_does_not_expose_legacy_password_change_route() -> None:
    paths = {route.path for route in router.routes}

    assert paths.isdisjoint(REMOVED_AUTH_ROUTES)
