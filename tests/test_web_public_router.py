from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app
from fluxtuner.web.routes.public import router


def test_public_router_registers_public_stats_route() -> None:
    paths = {route.path for route in router.routes}

    assert "/api/public/stats" in paths


def test_public_stats_route_is_included_in_app() -> None:
    client = TestClient(create_app())

    response = client.get("/api/public/stats")

    assert response.status_code == 200
    assert "totals" in response.json()
