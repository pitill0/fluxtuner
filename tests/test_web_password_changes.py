# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fluxtuner.web import auth
from fluxtuner.web.password_changes import (
    ACCOUNT_CHANGE_EXPIRED_DETAIL,
    ACCOUNT_CHANGE_INVALID_DETAIL,
    ACCOUNT_CHANGE_NOT_FOUND_DETAIL,
    ACCOUNT_CHANGE_NOT_PENDING_DETAIL,
    ACCOUNT_CHANGE_PENDING_DETAIL,
    ACCOUNT_CHANGE_RATE_LIMIT_KEY,
    ACCOUNT_CHANGE_RECEIVED_MESSAGE,
    ACCOUNT_CHANGE_REQUEST_MAX_AGE_SECONDS,
    password_change_expires_at,
    password_change_is_expired,
)


def test_password_change_constants_are_public() -> None:
    assert ACCOUNT_CHANGE_REQUEST_MAX_AGE_SECONDS == 60 * 60 * 24
    assert ACCOUNT_CHANGE_RATE_LIMIT_KEY == "__password_change__"
    assert ACCOUNT_CHANGE_INVALID_DETAIL == "Username and new password are required."
    assert ACCOUNT_CHANGE_RECEIVED_MESSAGE.startswith("If the account exists")
    assert ACCOUNT_CHANGE_NOT_FOUND_DETAIL == "Password change request not found."
    assert ACCOUNT_CHANGE_NOT_PENDING_DETAIL == "Password change request is not pending."
    assert ACCOUNT_CHANGE_PENDING_DETAIL == "Password change request pending approval."
    assert ACCOUNT_CHANGE_EXPIRED_DETAIL == "Password change request has expired."


def test_password_change_expires_at_is_in_the_future() -> None:
    expires_at = auth.parse_datetime(password_change_expires_at())

    assert expires_at > auth.utc_now()


def test_password_change_is_expired_for_past_timestamp() -> None:
    assert password_change_is_expired({"expires_at": "2000-01-01T00:00:00+00:00"}) is True


def test_password_change_is_not_expired_for_future_timestamp() -> None:
    future = auth.encode_datetime(auth.utc_now() + auth.timedelta(minutes=5))

    assert password_change_is_expired({"expires_at": future}) is False


def test_password_change_is_expired_for_invalid_payload() -> None:
    assert password_change_is_expired({}) is True
    assert password_change_is_expired({"expires_at": "not-a-date"}) is True
