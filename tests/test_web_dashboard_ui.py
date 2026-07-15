# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_panel_styles_are_isolated() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    shell_response = client.get("/static/shell.css")
    panels_response = client.get("/static/panels.css")
    buttons_response = client.get("/static/buttons.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert shell_response.status_code == 200
    assert panels_response.status_code == 200
    assert buttons_response.status_code == 200

    shell_link = '<link rel="stylesheet" href="/static/shell.css">'
    panels_link = '<link rel="stylesheet" href="/static/panels.css">'
    buttons_link = '<link rel="stylesheet" href="/static/buttons.css">'
    forms_link = '<link rel="stylesheet" href="/static/forms.css">'
    assert shell_link in page_response.text
    assert panels_link in page_response.text
    assert buttons_link in page_response.text
    assert forms_link in page_response.text
    assert page_response.text.index(shell_link) < page_response.text.index(buttons_link)
    assert page_response.text.index(buttons_link) < page_response.text.index(panels_link)
    assert page_response.text.index(panels_link) < page_response.text.index(forms_link)

    for selector in (
        "\n.panel,",
        "\n.panel-heading {",
        "\n.panel-tools {",
        "\n.panel[hidden] {",
        "\n.hero {",
        "\n.app-hero {",
        "\n.hero-card {",
        "\n.hero-actions {",
        "\n.eyebrow {",
        "\n.lede {",
        "\n.panel p {",
    ):
        assert selector in panels_response.text
        assert selector not in styles_response.text
        assert selector not in shell_response.text

    assert "@media (max-width: 58rem)" in panels_response.text
    assert "@media (max-width: 42rem)" in panels_response.text
    assert 'html[data-theme="light"] .panel' in panels_response.text
    assert "button," not in styles_response.text
    assert "button," in buttons_response.text
    assert ".empty," in styles_response.text


def test_web_button_styles_are_isolated() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    panels_response = client.get("/static/panels.css")
    buttons_response = client.get("/static/buttons.css")
    forms_response = client.get("/static/forms.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert panels_response.status_code == 200
    assert buttons_response.status_code == 200
    assert forms_response.status_code == 200

    panels_link = '<link rel="stylesheet" href="/static/panels.css">'
    buttons_link = '<link rel="stylesheet" href="/static/buttons.css">'
    forms_link = '<link rel="stylesheet" href="/static/forms.css">'
    assert panels_link in page_response.text
    assert buttons_link in page_response.text
    assert forms_link in page_response.text
    assert page_response.text.index(buttons_link) < page_response.text.index(panels_link)
    assert page_response.text.index(panels_link) < page_response.text.index(forms_link)

    for selector in (
        "\nbutton,",
        "\na.button,",
        "\n.hero-actions a {",
        "\nbutton:not(:disabled):hover,",
        "\nbutton:disabled {",
        'html[data-theme="light"] button,',
        'html[data-theme="light"] button:not(:disabled):hover,',
    ):
        assert selector in buttons_response.text
        assert selector not in styles_response.text

    assert "\n.hero-actions {" in panels_response.text
    assert "\n.hero-actions a:first-child {" in panels_response.text
    assert "\n.hero-actions a {" not in panels_response.text
    assert "Shared button and button-link behavior" in buttons_response.text


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

    app_response = client.get("/static/app.js")
    dashboard_response = client.get("/static/js/dashboard.js")
    ui_shell_response = client.get("/static/js/ui-shell.js")

    assert app_response.status_code == 200
    assert dashboard_response.status_code == 200
    assert ui_shell_response.status_code == 200
    elements_response = client.get("/static/js/app-elements.js")
    assert elements_response.status_code == 200
    assert 'root.querySelector("[data-nav-dashboard]")' in elements_response.text
    assert (
        'import { createDashboardController } from "/static/js/dashboard.js";' in app_response.text
    )
    assert "const { loadDashboard } = dashboardController;" in app_response.text
    assert "export function createDashboardController" in dashboard_response.text
    assert "async function loadDashboard(options = {})" in dashboard_response.text
    assert "const preserveView = Boolean(options.preserveView);" in dashboard_response.text
    assert "const silent = Boolean(options.silent);" in dashboard_response.text
    assert 'apiFetch("/api/dashboard"' in dashboard_response.text
    assert "function renderDashboard(payload)" in dashboard_response.text
    assert "function showDashboardView()" in ui_shell_response.text
    assert "function showDashboardView()" not in app_response.text
    assert "function renderDashboard(payload)" not in app_response.text


def test_web_search_controller_is_loaded_as_a_module() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    search_response = client.get("/static/js/search.js")

    assert app_response.status_code == 200
    assert search_response.status_code == 200
    assert 'import { createSearchController } from "/static/js/search.js";' in app_response.text
    assert "export function createSearchController" in search_response.text
    assert "const searchController = createSearchController({" in app_response.text
    assert "function renderSearchError(" not in app_response.text
    assert "renderResults(payload)" not in app_response.text


def test_web_static_js_resets_search_navigation() -> None:
    client = TestClient(create_app())

    app_response = client.get("/static/app.js")
    events_response = client.get("/static/js/app-events.js")
    navigation_response = client.get("/static/js/navigation.js")

    assert app_response.status_code == 200
    assert events_response.status_code == 200
    assert navigation_response.status_code == 200
    assert 'navSearchButton.addEventListener("click", navigateToSearch);' in events_response.text
    assert "function navigateToSearch()" in navigation_response.text
    assert "resetRadioBrowserView();" in navigation_response.text


def test_web_search_styles_are_isolated() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    search_response = client.get("/static/search.css")
    stations_response = client.get("/static/stations.css")
    actions_response = client.get("/static/station-actions.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert search_response.status_code == 200
    assert stations_response.status_code == 200
    assert actions_response.status_code == 200

    search_link = '<link rel="stylesheet" href="/static/search.css">'
    stations_link = '<link rel="stylesheet" href="/static/stations.css">'
    assert search_link in page_response.text
    assert stations_link in page_response.text
    assert page_response.text.index(search_link) < page_response.text.index(stations_link)

    for selector in [
        ".search-form",
        ".search-form label",
        ".search-debug-label",
        ".search-debug-panel",
        ".search-debug-panel summary",
        ".search-debug-panel dl",
        ".search-debug-panel dt",
        ".search-debug-panel dd",
        ".search-form button",
    ]:
        assert selector in search_response.text
        assert selector not in stations_response.text
        assert selector not in styles_response.text

    assert "@media (max-width: 58rem)" in search_response.text
    assert ".station-card" in stations_response.text
    assert ".station-actions" in actions_response.text
    assert ".station-actions" not in stations_response.text


def test_web_dashboard_styles_are_isolated() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    dashboard_response = client.get("/static/dashboard.css")
    stations_response = client.get("/static/stations.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert dashboard_response.status_code == 200
    assert stations_response.status_code == 200

    dashboard_link = '<link rel="stylesheet" href="/static/dashboard.css">'
    admin_link = '<link rel="stylesheet" href="/static/admin.css">'
    stations_link = '<link rel="stylesheet" href="/static/stations.css">'
    assert dashboard_link in page_response.text
    assert admin_link in page_response.text
    assert stations_link in page_response.text
    assert page_response.text.index(dashboard_link) < page_response.text.index(admin_link)
    assert page_response.text.index(admin_link) < page_response.text.index(stations_link)

    for selector in [
        ".dashboard-panel",
        ".dashboard-grid",
        ".dashboard-metric",
        ".dashboard-sections",
        ".dashboard-card",
        ".dashboard-quick-actions",
        ".dashboard-panel[hidden]",
    ]:
        assert selector in dashboard_response.text

    assert 'html[data-theme="light"] .dashboard-metric' in dashboard_response.text
    assert 'html[data-theme="light"] .dashboard-card' in dashboard_response.text
    assert "@media (max-width: 760px)" in dashboard_response.text

    for selector in [
        "\n.dashboard-panel {",
        "\n.dashboard-grid {",
        "\n.dashboard-metric {",
        "\n.dashboard-sections {",
        "\n.dashboard-card {",
        "\n.dashboard-quick-actions {",
        ".dashboard-panel[hidden]",
    ]:
        assert selector not in styles_response.text

    assert ".station-card" in stations_response.text
    assert ".station-card" not in styles_response.text
    assert ".station-card" not in dashboard_response.text
