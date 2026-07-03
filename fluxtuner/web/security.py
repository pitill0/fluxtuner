# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Small Web security helpers for sessions, cookies, and CSRF tokens."""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Any

from fluxtuner.web import auth

SESSION_COOKIE_NAME = "fluxtuner_session"
CSRF_HEADER_NAME = "X-FluxTuner-CSRF"


def web_secure_cookies() -> bool:
    value = os.getenv("FLUXTUNER_WEB_SECURE_COOKIES", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def session_cookie_max_age() -> int:
    value = os.getenv("FLUXTUNER_WEB_SESSION_MAX_AGE_SECONDS", "")
    try:
        max_age = int(value)
    except ValueError:
        return auth.DEFAULT_SESSION_MAX_AGE_SECONDS
    return max_age if max_age > 0 else auth.DEFAULT_SESSION_MAX_AGE_SECONDS


def csrf_token_for_session_token(token: str | None) -> str:
    """Return a CSRF token derived from the opaque session token."""
    if not token:
        return ""

    return hmac.new(
        token.encode("utf-8"),
        b"fluxtuner-web-csrf-v1",
        hashlib.sha256,
    ).hexdigest()


def set_session_cookie(response: Any, token: str) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=session_cookie_max_age(),
        httponly=True,
        secure=web_secure_cookies(),
        samesite="lax",
        path="/",
    )


def delete_session_cookie(response: Any) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=web_secure_cookies(),
        httponly=True,
        samesite="lax",
    )
