# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_css_completes_auth_style_ownership() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    panels_response = client.get("/static/panels.css")
    auth_response = client.get("/static/auth.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert panels_response.status_code == 200
    assert auth_response.status_code == 200

    auth_link = '<link rel="stylesheet" href="/static/auth.css">'
    public_link = '<link rel="stylesheet" href="/static/public.css">'
    assert auth_link in page_response.text
    assert public_link in page_response.text
    assert page_response.text.index(auth_link) < page_response.text.index(public_link)

    for snippet in (
        "/* Completed authentication ownership */",
        ".auth-form button",
        ".setup-form button",
        ".auth-secondary-actions",
        ".auth-note",
        'html[data-theme="light"] .auth-note',
        ".auth-panel[hidden]",
        ".setup-panel[hidden]",
    ):
        assert snippet in auth_response.text

    for selector in (
        "\n.auth-form button",
        "\n.setup-form button",
        "\n.auth-secondary-actions",
        "\n.auth-note",
        'html[data-theme="light"] .auth-note',
        ".auth-panel[hidden]",
        ".setup-panel[hidden]",
    ):
        assert selector not in styles_response.text

    assert ".panel[hidden]" not in styles_response.text
    assert ".panel[hidden]" in panels_response.text
    assert ".admin-panel[hidden]" not in styles_response.text
    assert "Shared form controls remain in forms.css." in auth_response.text
