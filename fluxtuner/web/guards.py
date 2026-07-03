# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import hmac
from typing import TYPE_CHECKING, Any

from fluxtuner.web import context as web_context
from fluxtuner.web.security import (
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    csrf_token_for_session_token,
)

if TYPE_CHECKING:
    from fastapi import Request


def require_csrf(request: Request, *, csrf_error_detail: str) -> None:
    """Require a valid CSRF header for the current session cookie."""
    from fastapi import HTTPException

    token = request.cookies.get(SESSION_COOKIE_NAME)
    expected = csrf_token_for_session_token(token)
    provided = request.headers.get(CSRF_HEADER_NAME, "")

    if not expected or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail=csrf_error_detail)


def require_authenticated_user(
    request: Request,
    *,
    auth_required_detail: str,
) -> dict[str, Any]:
    """Return the authenticated web user or raise a 401 HTTP error."""
    from fastapi import HTTPException

    user = web_context.authenticated_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail=auth_required_detail)
    return user


def require_admin_user(
    request: Request,
    *,
    auth_required_detail: str,
    admin_required_detail: str,
) -> dict[str, Any]:
    """Return the authenticated admin web user or raise a 401/403 HTTP error."""
    from fastapi import HTTPException

    user = require_authenticated_user(
        request,
        auth_required_detail=auth_required_detail,
    )
    if not bool(user["is_admin"]):
        raise HTTPException(status_code=403, detail=admin_required_detail)
    return user
