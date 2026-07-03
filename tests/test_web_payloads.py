# SPDX-License-Identifier: MIT

from __future__ import annotations

from fluxtuner.web.payloads import (
    admin_password_change_request_payload,
    admin_user_payload,
    public_user_payload,
    safe_int,
    station_payload,
)


def test_station_payload_normalizes_missing_and_numeric_values() -> None:
    payload = station_payload(
        {
            "name": "",
            "url": "https://example.test/stream.mp3",
            "country": None,
            "bitrate": "128",
            "play_count": "not-a-number",
            "favorite_tags": [" reggae ", "", 7],
        }
    )

    assert payload == {
        "name": "Unknown station",
        "url": "https://example.test/stream.mp3",
        "url_resolved": "https://example.test/stream.mp3",
        "country": "Unknown",
        "countrycode": "",
        "tags": "",
        "codec": "",
        "bitrate": 128,
        "homepage": "",
        "language": "",
        "last_played_at": "",
        "play_count": 0,
        "custom_name": "",
        "favorite_tags": ["reggae", "7"],
    }


def test_safe_int_handles_empty_invalid_and_numeric_values() -> None:
    assert safe_int(None) == 0
    assert safe_int("") == 0
    assert safe_int("invalid") == 0
    assert safe_int("42") == 42


def test_public_user_payload_exposes_safe_user_fields() -> None:
    assert public_user_payload(
        {
            "id": "5",
            "username": "laura",
            "display_name": "Laura",
            "is_admin": 1,
            "password_hash": "secret",
        }
    ) == {
        "id": 5,
        "username": "laura",
        "display_name": "Laura",
        "is_admin": True,
    }


def test_admin_user_payload_preserves_admin_management_fields() -> None:
    assert admin_user_payload(
        {
            "id": "7",
            "username": "admin",
            "display_name": "Admin",
            "is_admin": 1,
            "is_active": 0,
            "approval_status": "pending",
            "signup_note": "hello",
            "reviewed_at": None,
            "reviewed_by_user_id": None,
            "created_at": "2026-07-02T00:00:00Z",
            "updated_at": "2026-07-02T01:00:00Z",
        }
    ) == {
        "id": 7,
        "username": "admin",
        "display_name": "Admin",
        "is_admin": True,
        "is_active": False,
        "approval_status": "pending",
        "signup_note": "hello",
        "reviewed_at": None,
        "reviewed_by_user_id": None,
        "created_at": "2026-07-02T00:00:00Z",
        "updated_at": "2026-07-02T01:00:00Z",
    }


def test_admin_password_change_request_payload_preserves_review_fields() -> None:
    assert admin_password_change_request_payload(
        {
            "id": "3",
            "user_id": "8",
            "username": "user",
            "display_name": "User",
            "note": "reset please",
            "status": "pending",
            "created_at": "2026-07-02T00:00:00Z",
            "expires_at": "2026-07-03T00:00:00Z",
            "resolved_at": None,
            "resolved_by_user_id": None,
        }
    ) == {
        "id": 3,
        "user_id": 8,
        "username": "user",
        "display_name": "User",
        "note": "reset please",
        "status": "pending",
        "created_at": "2026-07-02T00:00:00Z",
        "expires_at": "2026-07-03T00:00:00Z",
        "resolved_at": None,
        "resolved_by_user_id": None,
    }
