from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def test_web_static_js_initializes_setup_before_auth() -> None:
    client = TestClient(create_app())

    response = client.get("/static/app.js")

    assert response.status_code == 200
    assert "loadAuthState();\nasync function initializeAuthFlow" not in response.text
    assert "await loadSetupState();" in response.text
    assert "if (setupAvailable)" in response.text
    assert "await loadAuthState();" in response.text
