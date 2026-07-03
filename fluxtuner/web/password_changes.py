# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from typing import Any

from fluxtuner.web import auth

ACCOUNT_CHANGE_REQUEST_MAX_AGE_SECONDS = 60 * 60 * 24
ACCOUNT_CHANGE_RATE_LIMIT_KEY = "__password_change__"
ACCOUNT_CHANGE_INVALID_DETAIL = "Username and new password are required."
ACCOUNT_CHANGE_RECEIVED_MESSAGE = "If the account exists, the password change request was recorded."
ACCOUNT_CHANGE_NOT_FOUND_DETAIL = "Password change request not found."
ACCOUNT_CHANGE_NOT_PENDING_DETAIL = "Password change request is not pending."
ACCOUNT_CHANGE_PENDING_DETAIL = "Password change request pending approval."
ACCOUNT_CHANGE_EXPIRED_DETAIL = "Password change request has expired."


def password_change_expires_at() -> str:
    return auth.encode_datetime(
        auth.utc_now() + auth.timedelta(seconds=ACCOUNT_CHANGE_REQUEST_MAX_AGE_SECONDS)
    )


def password_change_is_expired(request_payload: dict[str, Any]) -> bool:
    try:
        return auth.parse_datetime(str(request_payload["expires_at"])) <= auth.utc_now()
    except (KeyError, TypeError, ValueError):
        return True
