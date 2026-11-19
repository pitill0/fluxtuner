# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Security and compatibility boundaries for recommendation URL sharing."""

from __future__ import annotations

import pytest

from fluxtuner.core.custom_stations import _validate_url
from fluxtuner.core.m3u_import import M3UEntry
from fluxtuner.core.share_snapshots import build_share_snapshot


def share(url: str) -> str:
    return build_share_snapshot(
        kind="station",
        entries=[M3UEntry("Example Radio", url)],
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://radio.example/live",
        "https://radio.example/stream/live",
        "https://radio.example/archive/2026/live.aac",
        "https://radio.example/channel/keymusic/live",
        "https://radio.example/authorization/live",
        "https://radio.example/path/%40channel/live",
        "http://radio.example/live",
        "http://127.0.0.1:8000/live",
    ],
)
def test_safe_or_noncredential_paths_remain_shareable(url):
    assert share(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://radio.example/live?token=private",
        "https://radio.example/live#fragment",
        "https://user:password@radio.example/live",
        "https://radio.example/token/fake123/live",
        "https://radio.example/access_token/fake123",
        "https://radio.example/api_key=fake123/live",
        "https://radio.example/password/fake123",
        "https://radio.example/secret/fake123",
        "https://radio.example/live%3Ftoken%3Dfake123",
        "https://radio.example/live%23fragment",
        "https://radio.example/live%253Ftoken%253Dfake123",
        "https://radio.example/%74oken/fake123/live",
        "https://radio.example/token%2Ffake123/live",
    ],
)
def test_obvious_sensitive_url_patterns_are_not_shared(url):
    with pytest.raises(ValueError, match="cannot be shared safely|Credentials"):
        share(url)


@pytest.mark.parametrize(
    "url",
    [
        "https://radio.example/live?token=private",
        "https://radio.example/token/fake123/live",
        "https://radio.example/live%3Ftoken%3Dfake123",
    ],
)
def test_sharing_policy_does_not_change_normal_stream_validation(url):
    assert _validate_url(url) == url


def test_rejected_url_is_not_in_exception_message():
    secret = "synthetic-secret-do-not-log"
    url = f"https://radio.example/token/{secret}"

    with pytest.raises(ValueError) as failure:
        share(url)

    assert secret not in str(failure.value)
    assert url not in str(failure.value)
