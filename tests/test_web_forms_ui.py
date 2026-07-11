# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

import re

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app

FIELD_PROPERTIES = (
    "--field-bg",
    "--field-text",
    "--field-muted",
    "--field-border",
    "--field-border-focus",
    "--help-text",
)

FORM_SELECTORS = (
    'input[type="checkbox"]',
    "input::placeholder",
    "textarea::placeholder",
    "select:invalid",
    ".form-help",
    ".field-help",
    ".help-text",
    ".hint",
    ".dialog-help",
)


def test_web_css_extracts_shared_forms_domain() -> None:
    client = TestClient(create_app())

    page_response = client.get("/")
    styles_response = client.get("/static/styles.css")
    shell_response = client.get("/static/shell.css")
    forms_response = client.get("/static/forms.css")
    dialogs_response = client.get("/static/dialogs.css")

    assert page_response.status_code == 200
    assert styles_response.status_code == 200
    assert shell_response.status_code == 200
    assert forms_response.status_code == 200
    assert dialogs_response.status_code == 200

    shell_link = '<link rel="stylesheet" href="/static/shell.css">'
    forms_link = '<link rel="stylesheet" href="/static/forms.css">'
    dialogs_link = '<link rel="stylesheet" href="/static/dialogs.css">'
    assert shell_link in page_response.text
    assert forms_link in page_response.text
    assert dialogs_link in page_response.text
    assert page_response.text.index(shell_link) < page_response.text.index(forms_link)
    assert page_response.text.index(forms_link) < page_response.text.index(dialogs_link)

    for property_name in FIELD_PROPERTIES:
        declaration = re.compile(rf"(?m)^\s*{re.escape(property_name)}\s*:")
        assert declaration.search(forms_response.text)
        assert not declaration.search(styles_response.text)

    for selector in FORM_SELECTORS:
        assert selector in forms_response.text
        assert selector not in styles_response.text

    # Shared help-text consumers remain in the base stylesheet and may
    # legitimately reference the variable declared by forms.css.
    assert ".panel p" in styles_response.text
    assert "small" in styles_response.text
    assert "var(--help-text)" in styles_response.text

    # Dialog variables belong to dialogs.css, not the shared forms layer.
    assert "--dialog-bg" not in styles_response.text
    assert "--dialog-backdrop" not in styles_response.text
    assert "--dialog-bg" not in forms_response.text
    assert "--dialog-backdrop" not in forms_response.text

    assert "Shared form controls" in forms_response.text
