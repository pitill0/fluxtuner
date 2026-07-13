# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_player_loads_metadata_controller() -> None:
    client = TestClient(create_app())

    page = client.get("/")
    app = client.get("/static/app.js")
    module = client.get("/static/js/metadata.js")
    elements = client.get("/static/js/app-elements.js")
    player = client.get("/static/js/player.js")
    styles = client.get("/static/player.css")

    assert page.status_code == 200
    assert app.status_code == 200
    assert module.status_code == 200
    assert elements.status_code == 200
    assert player.status_code == 200
    assert styles.status_code == 200

    assert "data-player-station" in page.text
    assert 'root.querySelector("[data-player-station]")' in elements.text
    assert 'import { createMetadataController } from "/static/js/metadata.js";' in app.text
    assert "const metadataController = createMetadataController({" in app.text
    assert "metadataController," in app.text
    assert "export function createMetadataController" in module.text
    assert "/api/metadata?url=${encodeURIComponent(requestedUrl)}" in module.text
    assert "apiFetch(" in module.text
    assert 'state !== "playing"' in module.text
    assert "requestGeneration" in module.text
    assert "metadataController?.updatePlaybackState" in player.text
    assert "metadataController?.setStation" in player.text
    assert "metadataController?.clear" in player.text
    assert ".player-station" in styles.text


def test_metadata_ui_uses_safe_text_rendering_and_bounded_polling() -> None:
    client = TestClient(create_app())
    module = client.get("/static/js/metadata.js").text

    assert "textContent =" in module
    assert "innerHTML" not in module
    assert "DEFAULT_POLL_INTERVAL_MS = 5000" in module
    assert "windowRef.setTimeout" in module
    assert "windowRef.clearTimeout" in module
    assert 'payload?.status === "fresh"' in module
    assert '{ cache: "no-store" }' in module
    assert module.index("generation !== requestGeneration) return;") < module.index(
        "clearTimer();", module.index("function scheduleNext")
    )
    assert "if (requestInFlight) {" in module
    assert "scheduleNext(requestGeneration);" in module
    assert "scheduleNext(generation);" not in module
    assert "requestInFlight = false;" in module
    assert module.count("requestInFlight = false;") == 2
