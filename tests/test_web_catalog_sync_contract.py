# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""UX-03 catalog management and navigation integration contracts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "fluxtuner/web/static"


def read(path: str) -> str:
    return (STATIC / path).read_text()


def test_catalog_management_remains_a_contextual_action():
    template = (ROOT / "fluxtuner/web/templates/index.html").read_text()
    elements = read("js/app-elements.js")

    assert "data-nav-catalogs" in template
    assert "data-nav-stations" in template
    assert "data-nav-manage-subscriptions" in template
    assert "data-nav-subscriptions" not in template

    assert ('openButton: root.querySelector("[data-nav-manage-subscriptions]")') in elements


def test_catalog_management_mutations_notify_application():
    remote = read("js/remote-subscriptions.js")
    app = read("app.js")

    assert "onChanged = () => {}" in remote
    assert 'onChanged({ type: "added" })' in remote
    assert 'onChanged({ type: "updated"' in remote
    assert 'onChanged({ type: "removed"' in remote
    assert "if (current(mark)) {" in remote

    assert "onChanged: ({ type, sourceId }) =>" in app
    assert 'if (view === "catalogs")' in app
    assert "void loadCatalogs()" in app
    assert "void loadCatalogStations(selected)" in app


def test_unified_library_uses_existing_playback_results():
    app = read("app.js")
    unified = read("js/unified-library.js")

    assert "createUnifiedLibraryController({" in app
    assert "renderResults," in app
    assert "renderResults(payload)" in unified
    assert "/api/stations/custom" in unified
    assert "/api/stations/subscriptions" in unified


def test_private_navigation_and_browser_routes_are_connected():
    app = read("app.js")
    events = read("js/app-events.js")
    browser = read("js/browser-navigation.js")

    assert "stations: () => navigateToPrivateView(loadMyStations)" in app
    assert "catalogs: () => navigateToPrivateView(loadCatalogs)" in app
    assert "catalog: (id) => navigateToPrivateView(" in app

    assert "navStationsButton.addEventListener(" in events
    assert "navCatalogsButton.addEventListener(" in events

    assert '"stations", "catalogs", "catalog"' in browser
    assert 'url.searchParams.delete("catalog")' in browser
