"""Signed artwork references are session-scoped but do not own cache entries."""

from __future__ import annotations

import base64

import pytest

from fluxtuner.web.artwork_tokens import issue_artwork_reference, verify_artwork_reference

KEY = b"server-secret-only-not-a-session-token-32-bytes"
OTHER_KEY = b"different-server-key-not-a-session-token-32-bytes"
URL = "https://radio.example/images/station.png?size=64"


def test_roundtrip_and_session_isolation() -> None:
    reference = issue_artwork_reference(URL, "session-a", KEY, now=1000)
    assert verify_artwork_reference(reference, "session-a", KEY, now=1000) == URL
    assert verify_artwork_reference(reference, "session-b", KEY, now=1000) is None
    assert verify_artwork_reference(reference, "session-a", OTHER_KEY, now=1000) is None


def test_expiration_and_future_dated_reference() -> None:
    reference = issue_artwork_reference(URL, "session-a", KEY, now=1000, ttl_seconds=60)
    assert verify_artwork_reference(reference, "session-a", KEY, now=1060) == URL
    assert verify_artwork_reference(reference, "session-a", KEY, now=1061) is None
    assert verify_artwork_reference(reference, "session-a", KEY, now=100) is None


def test_tampering_cannot_change_source_or_expiry() -> None:
    reference = issue_artwork_reference(URL, "session-a", KEY, now=1000)
    fields = reference.split(".")
    replacement = (
        base64.urlsafe_b64encode(b"https://attacker.example/logo.png").rstrip(b"=").decode()
    )
    for modified in (
        ".".join((fields[0], fields[1], replacement, fields[3])),
        ".".join((fields[0], "1700", fields[2], fields[3])),
        ".".join((fields[0], fields[1], fields[2], "0" * 64)),
    ):
        assert verify_artwork_reference(modified, "session-a", KEY, now=1000) is None


@pytest.mark.parametrize(
    "url",
    [
        "",
        "file:///etc/passwd",
        "https://user:password@radio.example/logo.png",
        "https://radio.example/logo.png#fragment",
        "https://radio.example/line\nbreak",
        "https://radio.example:0/logo.png",
        "https://radio.example/" + "x" * 2048,
    ],
)
def test_rejects_malformed_source_urls(url: str) -> None:
    with pytest.raises(ValueError):
        issue_artwork_reference(url, "session-a", KEY, now=1000)


def test_requires_server_only_key_and_bounded_lifetime() -> None:
    with pytest.raises(ValueError):
        issue_artwork_reference(URL, "session-a", b"short", now=1000)
    with pytest.raises(ValueError):
        issue_artwork_reference(URL, "session-a", KEY, now=1000, ttl_seconds=901)
    with pytest.raises(ValueError):
        issue_artwork_reference(URL, "", KEY, now=1000)


def test_invalid_reference_is_fail_closed() -> None:
    assert verify_artwork_reference("invalid", "session-a", KEY, now=1000) is None
    assert verify_artwork_reference("x" * 4097, "session-a", KEY, now=1000) is None
    assert verify_artwork_reference("invalid", "session-a", b"short", now=1000) is None


def test_two_sessions_sign_same_source_independently() -> None:
    first = issue_artwork_reference(URL, "session-a", KEY, now=1000)
    second = issue_artwork_reference(URL, "session-b", KEY, now=1000)
    assert first != second
    assert verify_artwork_reference(first, "session-a", KEY, now=1000) == URL
    assert verify_artwork_reference(second, "session-b", KEY, now=1000) == URL
