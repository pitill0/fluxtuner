from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_index_shows_password_requirements() -> None:
    client = TestClient(create_app())

    response = client.get("/")

    assert response.status_code == 200
    assert "Password must be at least 15 characters." in response.text
    assert 'minlength="15"' in response.text
    assert 'autocomplete="current-password"' in response.text


def test_web_static_css_styles_password_help() -> None:
    client = TestClient(create_app())

    response = client.get("/static/styles.css")

    assert response.status_code == 200
    assert ".field-help" in response.text
