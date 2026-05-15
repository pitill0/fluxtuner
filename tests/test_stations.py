from fluxtuner.core.stations import (
    all_station_tags,
    favorite_tags,
    same_station,
    station_bitrate,
    station_key,
    station_name,
    station_tags,
    station_url,
)


def test_station_key_prefers_resolved_url() -> None:
    station = {
        "url": "https://example.com/raw",
        "url_resolved": "https://example.com/resolved",
    }

    assert station_key(station) == "https://example.com/resolved"


def test_station_key_falls_back_to_url() -> None:
    station = {"url": "https://example.com/raw"}

    assert station_key(station) == "https://example.com/raw"


def test_station_name_fallback() -> None:
    assert station_name({}) == "Unknown station"
    assert station_name({"name": "  BBC Radio 1  "}) == "BBC Radio 1"


def test_station_tags_from_comma_separated_string() -> None:
    station = {"tags": "rock, pop, , indie"}

    assert station_tags(station) == ["rock", "pop", "indie"]


def test_station_tags_from_list() -> None:
    station = {"tags": [" rock ", "", "pop"]}

    assert station_tags(station) == ["rock", "pop"]


def test_favorite_tags_are_normalized_and_sorted() -> None:
    station = {"favorite_tags": [" Rock ", "jazz", "rock", ""]}

    assert favorite_tags(station) == ["Rock", "jazz", "rock"]


def test_all_station_tags_lowercases_stream_and_favorite_tags() -> None:
    station = {
        "tags": "Rock, Indie",
        "favorite_tags": ["Morning", "Favorites"],
    }

    assert all_station_tags(station) == {"rock", "indie", "morning", "favorites"}


def test_station_bitrate_handles_invalid_values() -> None:
    assert station_bitrate({"bitrate": "128"}) == 128
    assert station_bitrate({"bitrate": "nope"}) == 0
    assert station_bitrate({}) == 0


def test_same_station_compares_station_keys() -> None:
    first = {"url_resolved": "https://example.com/stream"}
    second = {"url": "https://example.com/stream"}

    assert same_station(first, second)


def test_station_url_strips_whitespace_and_rejects_empty_values() -> None:
    assert station_url({"url": "  https://example.com/stream  "}) == "https://example.com/stream"
    assert station_url({"url": "   "}) is None
