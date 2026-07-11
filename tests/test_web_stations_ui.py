# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_css_extracts_stations_domain() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    admin_response = client.get("/static/admin.css")
    stations_response = client.get("/static/stations.css")
    player_response = client.get("/static/player.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert admin_response.status_code == 200
    assert stations_response.status_code == 200
    assert player_response.status_code == 200

    admin_link = '<link rel="stylesheet" href="/static/admin.css">'
    stations_link = '<link rel="stylesheet" href="/static/stations.css">'
    player_link = '<link rel="stylesheet" href="/static/player.css">'
    assert admin_link in page_response.text
    assert stations_link in page_response.text
    assert player_link in page_response.text
    assert page_response.text.index(admin_link) < page_response.text.index(stations_link)
    assert page_response.text.index(stations_link) < page_response.text.index(player_link)

    for selector in (
        ".search-form",
        ".search-debug-label",
        ".search-debug-panel",
        ".results",
        ".station-card",
        ".station-meta",
        ".station-actions",
    ):
        assert selector in stations_response.text
        assert selector not in styles_response.text

    assert ".station-actions a.station-external-link" in stations_response.text
    assert ".station-actions button[data-play-station]" in stations_response.text
    assert 'html[data-theme="light"] .station-card' in stations_response.text
    assert 'html[data-theme="light"] .station-meta' in stations_response.text
    assert "@media (max-width: 58rem)" in stations_response.text
    assert "@media (max-width: 42rem)" in stations_response.text
    assert "Search controls, result lists" in stations_response.text
