from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app
from fluxtuner.web.routes.library import router

EXPECTED_LIBRARY_ROUTES = {
    "/api/search",
    "/api/history",
    "/api/favorites",
    "/api/playlists",
    "/api/playlists/{name}",
    "/api/playlists/{name}/stations",
}


def test_library_router_registers_library_routes() -> None:
    paths = {route.path for route in router.routes}

    assert paths >= EXPECTED_LIBRARY_ROUTES


def test_library_routes_are_included_in_app() -> None:
    client = TestClient(create_app())

    response = client.get("/api/search")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required."}
