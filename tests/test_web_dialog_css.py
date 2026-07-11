# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_css_completes_dialog_token_ownership() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    dialogs_response = client.get("/static/dialogs.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert dialogs_response.status_code == 200

    styles_link = '<link rel="stylesheet" href="/static/styles.css">'
    dialogs_link = '<link rel="stylesheet" href="/static/dialogs.css">'
    assert styles_link in page_response.text
    assert dialogs_link in page_response.text
    assert page_response.text.index(styles_link) < page_response.text.index(dialogs_link)

    for token in (
        "--dialog-backdrop",
        "--dialog-bg",
        "--dialog-glow",
        "--dialog-text",
        "--dialog-muted",
        "--dialog-shadow",
    ):
        assert dialogs_response.text.count(token) >= 2
        assert token not in styles_response.text

    assert "/* Dialog theme tokens */" in dialogs_response.text
    assert ":root {" in dialogs_response.text
    assert 'html[data-theme="light"] {' in dialogs_response.text
    assert "Shared form controls remain in forms.css." in dialogs_response.text
