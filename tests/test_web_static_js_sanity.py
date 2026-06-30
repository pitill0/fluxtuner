from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_static_js_initializes_setup_before_auth() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "loadAuthState();\nasync function initializeAuthFlow" not in response.text
    assert "await loadSetupState();" in response.text
    assert "if (setupAvailable)" in response.text
    assert "await loadAuthState();" in response.text


def test_web_static_js_sanitizes_external_station_urls() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "function safeExternalUrl(value)" in response.text
    assert "/^https?:\\/\\//i.test(rawUrl)" in response.text
    assert '["http:", "https:"].includes(parsed.protocol)' in response.text
    assert "function stationHomepage(station)" in response.text
    assert "const homepage = stationHomepage(station);" in response.text


def test_web_static_js_limits_playlist_names_client_side() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "const MAX_PLAYLIST_NAME_LENGTH = 120;" in response.text
    assert "playlistName.length > MAX_PLAYLIST_NAME_LENGTH" in response.text
    assert "cleanPlaylistName.length > MAX_PLAYLIST_NAME_LENGTH" in response.text
