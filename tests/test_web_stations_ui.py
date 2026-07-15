# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_css_extracts_stations_domain() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    admin_response = client.get("/static/admin.css")
    search_response = client.get("/static/search.css")
    stations_response = client.get("/static/stations.css")
    actions_response = client.get("/static/station-actions.css")
    player_response = client.get("/static/player.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert admin_response.status_code == 200
    assert search_response.status_code == 200
    assert stations_response.status_code == 200
    assert actions_response.status_code == 200
    assert player_response.status_code == 200

    admin_link = '<link rel="stylesheet" href="/static/admin.css">'
    search_link = '<link rel="stylesheet" href="/static/search.css">'
    stations_link = '<link rel="stylesheet" href="/static/stations.css">'
    actions_link = '<link rel="stylesheet" href="/static/station-actions.css">'
    player_link = '<link rel="stylesheet" href="/static/player.css">'
    assert admin_link in page_response.text
    assert search_link in page_response.text
    assert stations_link in page_response.text
    assert actions_link in page_response.text
    assert player_link in page_response.text
    assert page_response.text.index(admin_link) < page_response.text.index(search_link)
    assert page_response.text.index(search_link) < page_response.text.index(stations_link)
    assert page_response.text.index(stations_link) < page_response.text.index(actions_link)
    assert page_response.text.index(actions_link) < page_response.text.index(player_link)

    for selector in (
        ".results",
        ".station-card",
        ".station-meta",
    ):
        assert selector in stations_response.text
        assert selector not in actions_response.text
        assert selector not in search_response.text
        assert selector not in styles_response.text

    for selector in (
        ".station-actions",
        ".station-actions a.station-external-link",
        ".station-actions button[data-play-station]",
    ):
        assert selector in actions_response.text
        assert selector not in stations_response.text
        assert selector not in search_response.text
        assert selector not in styles_response.text

    for selector in (
        ".search-form",
        ".search-debug-label",
        ".search-debug-panel",
    ):
        assert selector in search_response.text
        assert selector not in stations_response.text
        assert selector not in styles_response.text

    assert 'html[data-theme="light"] .station-actions a' in actions_response.text
    assert 'html[data-theme="light"] .station-card' in stations_response.text
    assert 'html[data-theme="light"] .station-meta' in stations_response.text
    assert "@media (max-width: 58rem)" in search_response.text
    assert "@media (max-width: 58rem)" not in stations_response.text
    assert "@media (max-width: 42rem)" in stations_response.text
    assert "@media (max-width: 42rem)" in actions_response.text
    assert "Search controls and diagnostics" in search_response.text
    assert "Result lists, station cards and responsive behavior" in stations_response.text
    assert "Station action controls and responsive behavior" in actions_response.text
