# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fluxtuner.core import db
from fluxtuner.core.profiles import resolve_effective_profile_name
from fluxtuner.web import auth
from fluxtuner.web.security import (
    SESSION_COOKIE_NAME,
    session_absolute_max_age,
)

AUTHENTICATED_USER_STATE_KEY = "fluxtuner_authenticated_user"


def ensure_web_schema(conn: Any) -> None:
    """Ensure the Web database schema and migrations are available."""
    db.create_schema(conn)
    db.ensure_user_approval_schema(conn)
    db.ensure_profile_user_schema(conn)


def authenticated_user(request: Any) -> dict[str, Any] | None:
    """Return the Web user associated with the request session cookie, if any."""
    state = getattr(request, "state", None)
    if state is not None and hasattr(state, AUTHENTICATED_USER_STATE_KEY):
        return getattr(state, AUTHENTICATED_USER_STATE_KEY)

    token = request.cookies.get(SESSION_COOKIE_NAME)
    with db.connect() as conn:
        ensure_web_schema(conn)
        return auth.get_session_user(
            conn,
            token,
            absolute_max_age_seconds=session_absolute_max_age(),
        )


def effective_profile_name(profile: str | None = None) -> str | None:
    """Resolve the profile selected by a Web request."""
    return resolve_effective_profile_name(profile)
