# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

import hmac
import os
from typing import Any

from fluxtuner.web import auth

SETUP_TOKEN_ENV = "FLUXTUNER_WEB_SETUP_TOKEN"  # nosec B105 - env var name, not a secret value
LOCAL_SETUP_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def configured_admin_exists(conn: Any) -> bool:
    """Return whether a real active web admin has been configured."""
    row = conn.execute(
        """
        SELECT 1
        FROM users
        WHERE
            is_admin = 1
            AND is_active = 1
            AND password_hash IS NOT NULL
            AND length(trim(password_hash)) > 0
        LIMIT 1
        """
    ).fetchone()
    return row is not None


def setup_token() -> str:
    return os.getenv(SETUP_TOKEN_ENV, "").strip()


def setup_token_required() -> bool:
    return bool(setup_token())


def valid_setup_token(provided_token: str) -> bool:
    expected_token = setup_token()
    if not expected_token:
        return True

    return hmac.compare_digest(provided_token, expected_token)


def request_client_host(request: Any) -> str:
    client = getattr(request, "client", None)
    host = getattr(client, "host", None)
    return auth.client_key_from_host(str(host) if host else None)


def setup_request_is_local(request: Any) -> bool:
    client = getattr(request, "client", None)
    host = str(getattr(client, "host", "") or "").strip().lower()
    return host in LOCAL_SETUP_HOSTS
