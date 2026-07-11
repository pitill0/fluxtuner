# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_css_extracts_player_domain() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    admin_response = client.get("/static/admin.css")
    player_response = client.get("/static/player.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert admin_response.status_code == 200
    assert player_response.status_code == 200

    admin_link = '<link rel="stylesheet" href="/static/admin.css">'
    player_link = '<link rel="stylesheet" href="/static/player.css">'
    assert admin_link in page_response.text
    assert player_link in page_response.text
    assert page_response.text.index(admin_link) < page_response.text.index(player_link)

    owned_selectors = (
        ".player-bar",
        ".player-info",
        ".player-actions",
    )
    for selector in owned_selectors:
        assert selector in player_response.text
        assert selector not in styles_response.text

    assert ".player-bar[hidden]" in player_response.text
    assert ".player-bar::before" in player_response.text
    assert '.player-bar[data-state="loading"]' in player_response.text
    assert '.player-bar[data-state="playing"]' in player_response.text
    assert '.player-bar[data-state="paused"]' in player_response.text
    assert '.player-bar[data-state="error"]' in player_response.text
    assert 'html[data-theme="light"] .player-bar' in player_response.text
    assert "@media (max-width: 58rem)" in player_response.text
    assert "@media (max-width: 42rem)" in player_response.text
    assert "Persistent player layout" in player_response.text
