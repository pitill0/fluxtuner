# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from fluxtuner.web import auth
from fluxtuner.web.security import (
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    csrf_token_for_session_token,
    delete_session_cookie,
    session_cookie_max_age,
    set_session_cookie,
    web_secure_cookies,
)


class DummyResponse:
    def __init__(self) -> None:
        self.set_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []

    def set_cookie(self, **kwargs: object) -> None:
        self.set_calls.append(kwargs)

    def delete_cookie(self, **kwargs: object) -> None:
        self.delete_calls.append(kwargs)


def test_security_constants_match_public_web_contract() -> None:
    assert SESSION_COOKIE_NAME == "fluxtuner_session"
    assert CSRF_HEADER_NAME == "X-FluxTuner-CSRF"


def test_csrf_token_for_session_token_is_stable_and_opaque() -> None:
    token = csrf_token_for_session_token("session-token")

    assert token
    assert token == csrf_token_for_session_token("session-token")
    assert token != csrf_token_for_session_token("other-session-token")
    assert csrf_token_for_session_token(None) == ""
    assert csrf_token_for_session_token("") == ""


def test_web_secure_cookies_defaults_to_enabled(monkeypatch) -> None:
    monkeypatch.delenv("FLUXTUNER_WEB_SECURE_COOKIES", raising=False)
    assert web_secure_cookies() is True

    for value in ["0", "false", "no", "off", " FALSE "]:
        monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", value)
        assert web_secure_cookies() is False

    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "true")
    assert web_secure_cookies() is True


def test_session_cookie_max_age_uses_positive_override(monkeypatch) -> None:
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", "123")
    assert session_cookie_max_age() == 123


def test_session_cookie_max_age_falls_back_for_invalid_values(monkeypatch) -> None:
    for value in ["", "abc", "0", "-1"]:
        monkeypatch.setenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", value)
        assert session_cookie_max_age() == auth.DEFAULT_SESSION_MAX_AGE_SECONDS


def test_set_session_cookie_uses_web_session_settings(monkeypatch) -> None:
    monkeypatch.setenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", "42")
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    response = DummyResponse()

    set_session_cookie(response, "session-token")

    assert response.set_calls == [
        {
            "key": SESSION_COOKIE_NAME,
            "value": "session-token",
            "max_age": 42,
            "httponly": True,
            "secure": False,
            "samesite": "lax",
            "path": "/",
        }
    ]


def test_delete_session_cookie_uses_web_session_settings(monkeypatch) -> None:
    monkeypatch.setenv("FLUXTUNER_WEB_SECURE_COOKIES", "false")
    response = DummyResponse()

    delete_session_cookie(response)

    assert response.delete_calls == [
        {
            "key": SESSION_COOKIE_NAME,
            "path": "/",
            "secure": False,
            "httponly": True,
            "samesite": "lax",
        }
    ]
