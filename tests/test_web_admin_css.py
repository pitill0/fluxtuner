# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_css_completes_admin_diagnostic_style_ownership() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    admin_response = client.get("/static/admin.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert admin_response.status_code == 200

    styles_link = '<link rel="stylesheet" href="/static/styles.css">'
    admin_link = '<link rel="stylesheet" href="/static/admin.css">'
    assert styles_link in page_response.text
    assert admin_link in page_response.text
    assert page_response.text.index(styles_link) < page_response.text.index(admin_link)

    for snippet in (
        "/* Completed admin diagnostic ownership */",
        ".player-debug-details",
        ".player-debug-section",
        ".player-debug-section h4",
        ".player-debug-section p",
        ".player-debug-section .status",
        ".player-debug-export-section:has(.player-debug-export[hidden])",
        ".admin-panel[hidden]",
    ):
        assert snippet in admin_response.text

    for snippet in (
        "\n.player-debug-details {",
        "\n.player-debug-section {",
        ".player-debug-export-section:has(.player-debug-export[hidden])",
        ".admin-panel[hidden]",
    ):
        assert snippet not in styles_response.text

    assert styles_response.text.count(".panel[hidden]") == 1
    assert "display: grid !important;" in admin_response.text
    assert "display: none !important;" in admin_response.text
    assert ".player-debug-section + .player-debug-section" in admin_response.text
    assert "margin-top: 0.75rem !important;" in admin_response.text
    assert 'html[data-theme="light"] .admin-health' in admin_response.text
    assert 'html[data-theme="light"] .admin-health' not in styles_response.text
    assert 'html[data-theme="light"] .panel' in styles_response.text
