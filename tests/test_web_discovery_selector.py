# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from pathlib import Path


def test_web_search_form_exposes_all_discovery_sources(web_library) -> None:
    client, _users = web_library
    with client:
        response = client.get("/")
    assert response.status_code == 200
    html = response.text
    assert 'name="source"' in html
    assert 'value="radio-browser" selected' in html
    assert 'value="local"' in html
    assert 'value="all"' in html


def test_web_search_controller_invalidates_pending_requests_on_source_change() -> None:
    script = (Path(__file__).resolve().parents[1] / "fluxtuner/web/static/js/search.js").read_text()
    assert 'sourceSelector?.addEventListener("change"' in script
    assert "activeSearchController?.abort();" in script
    assert "++searchRequestId;" in script
    assert 'params.set("source", selectedSource());' in script
    assert 'setResultsHeader(sourceLabel, "Search stations");' in script
