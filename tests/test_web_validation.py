# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from __future__ import annotations

from fluxtuner.web.validation import (
    is_supported_web_url,
    playlist_name,
    playlist_name_too_long,
    station_stream_url,
    text_too_long,
)


def test_text_too_long_handles_none_and_boundaries() -> None:
    assert not text_too_long(None, 3)
    assert not text_too_long("abc", 3)
    assert text_too_long("abcd", 3)


def test_is_supported_web_url_accepts_http_and_https_urls() -> None:
    assert is_supported_web_url("http://example.com/stream.mp3")
    assert is_supported_web_url(" https://example.com/radio ")


def test_is_supported_web_url_rejects_unsupported_or_incomplete_urls() -> None:
    assert not is_supported_web_url("")
    assert not is_supported_web_url("example.com/stream.mp3")
    assert not is_supported_web_url("ftp://example.com/stream.mp3")
    assert not is_supported_web_url("https:///missing-host")


def test_station_stream_url_prefers_resolved_url() -> None:
    station = {"url": "http://example.com/raw", "url_resolved": "https://cdn.example.com/live"}

    assert station_stream_url(station) == "https://cdn.example.com/live"


def test_station_stream_url_falls_back_to_url_and_strips() -> None:
    station = {"url": " http://example.com/raw ", "url_resolved": ""}

    assert station_stream_url(station) == "http://example.com/raw"


def test_playlist_name_normalizes_missing_and_whitespace() -> None:
    assert playlist_name({}) == ""
    assert playlist_name({"name": "  Favorites  "}) == "Favorites"


def test_playlist_name_too_long_uses_default_or_custom_limit() -> None:
    assert not playlist_name_too_long("a" * 120)
    assert playlist_name_too_long("a" * 121)
    assert playlist_name_too_long("abcdef", max_length=5)
