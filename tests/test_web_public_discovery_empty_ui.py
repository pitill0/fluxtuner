"""Discovery remains visible before a server accumulates listening activity."""

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_featured_station_is_not_hidden_by_zero_public_stats() -> None:
    script = TestClient(create_app()).get("/static/js/public-stats.js")
    assert script.status_code == 200
    assert "!users && !featuredName" in script.text
    assert "No public activity yet." in script.text
    assert "No top stations yet." in script.text
    assert "featuredPayload?.station?.name" in script.text
    assert "data-featured-save" in script.text
