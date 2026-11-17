"""Player logos use session-scoped refs without persisting them on stations."""

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_player_artwork_markup_is_passive_and_accessible() -> None:
    client = TestClient(create_app())
    page = client.get("/")
    assert page.status_code == 200
    assert 'data-player-artwork-image alt=""' in page.text
    assert "data-player-artwork-fallback" in page.text
    assert 'class="player-artwork" aria-hidden="true"' in page.text


def test_player_artwork_reference_is_separate_from_station_actions() -> None:
    client = TestClient(create_app())
    renderer = client.get("/static/js/station-renderer.js").text
    stations = client.get("/static/js/stations.js").text
    player = client.get("/static/js/player.js").text
    runtime = client.get("/static/js/player-runtime.js").text

    assert 'data-station-artwork-ref="${artworkRef}"' in renderer
    assert 'button.getAttribute("data-station-artwork-ref")' in renderer
    assert "delete actionStation.artwork_ref;" in stations
    assert 'function playStation(station, artworkRef = "")' in player
    assert 'function playStation(station, artworkRef = "")' in runtime
    assert "artworkController?.show(currentStationTitle(), artworkRef);" in player
    assert "artworkController?.clear();" in player


def test_player_artwork_accepts_only_signed_same_origin_paths() -> None:
    client = TestClient(create_app())
    script = client.get("/static/js/player-artwork.js")
    styles = client.get("/static/player.css")
    app = client.get("/static/app.js")

    assert script.status_code == 200
    assert styles.status_code == 200
    assert "^v1\\.[0-9]+\\.[A-Za-z0-9_-]+\\.[a-f0-9]{64}$" in script.text
    assert "`/api/artwork/${encodeURIComponent(token)}`" in script.text
    assert 'imageNode.removeAttribute("src")' in script.text
    assert ".player-artwork img[hidden]" in styles.text
    assert "import { createPlayerArtworkController }" in app.text
