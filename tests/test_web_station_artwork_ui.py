"""Station artwork UI uses only authenticated same-origin image references."""

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_station_cards_use_signed_same_origin_artwork_only() -> None:
    client = TestClient(create_app())
    response = client.get("/static/js/station-renderer.js")

    assert response.status_code == 200
    script = response.text
    assert "station.artwork_ref" in script
    assert "^v1\\.[0-9]+\\.[A-Za-z0-9_-]+\\.[a-f0-9]{64}$" in script
    assert "`/api/artwork/${encodeURIComponent(artworkRef)}`" in script
    assert 'loading="lazy"' in script
    assert 'decoding="async"' in script
    assert 'referrerpolicy="no-referrer"' in script
    assert 'image.addEventListener("error"' in script
    assert "image.hidden = true" in script
    assert "station.favicon" not in script


def test_artwork_refs_are_not_copied_into_station_actions() -> None:
    client = TestClient(create_app())
    response = client.get("/static/js/stations.js")

    assert response.status_code == 200
    assert "const actionStation = { ...station };" in response.text
    assert "delete actionStation.artwork_ref;" in response.text
    assert "JSON.stringify(actionStation)" in response.text


def test_artwork_fallback_and_light_theme_styles() -> None:
    client = TestClient(create_app())
    response = client.get("/static/stations.css")

    assert response.status_code == 200
    assert ".station-artwork-fallback" in response.text
    assert ".station-artwork img[hidden]" in response.text
    assert "object-fit: contain" in response.text
