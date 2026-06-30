# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_index_exposes_dashboard_ui() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "data-nav-dashboard" in response.text
    assert "data-dashboard-panel" in response.text
    assert "data-dashboard-user-metrics" in response.text
    assert "data-dashboard-admin" in response.text
    assert 'data-dashboard-action="admin"' in response.text


def test_web_static_js_loads_and_renders_dashboard() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert 'document.querySelector("[data-nav-dashboard]")' in response.text
    assert "async function loadDashboard()" in response.text
    assert 'apiFetch("/api/dashboard"' in response.text
    assert "function renderDashboard(payload)" in response.text
    assert "function showDashboardView()" in response.text


def test_web_static_js_resets_search_navigation() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert 'navSearchButton.addEventListener("click", () => {' in response.text
    assert "resetRadioBrowserView();" in response.text
