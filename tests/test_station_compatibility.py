from fluxtuner.core.compatibility import (
    filter_supported_stations,
    normalize_codec,
    station_codec_candidates,
    station_is_supported,
)
from fluxtuner.players.capabilities import PlayerCapabilities

GENERAL = PlayerCapabilities(general_purpose=True)
MP3_ONLY = PlayerCapabilities(supported_codecs=frozenset({"mp3"}))
OGG_ONLY = PlayerCapabilities(supported_codecs=frozenset({"ogg", "vorbis", "opus", "flac"}))


def test_normalize_codec_handles_common_aliases() -> None:
    assert normalize_codec("MP3") == "mp3"
    assert normalize_codec("audio/mpeg") == "mp3"
    assert normalize_codec("AAC+") == "aac"
    assert normalize_codec("application/ogg") == "ogg"
    assert normalize_codec("audio/flac") == "flac"


def test_station_codec_candidates_uses_codec_and_url_hint() -> None:
    station = {"codec": "?", "url_resolved": "https://example.com/live.mp3"}

    assert "mp3" in station_codec_candidates(station)


def test_general_purpose_backend_accepts_unknown_station() -> None:
    assert station_is_supported({"codec": "?"}, GENERAL) is True


def test_specialized_backend_accepts_matching_codec() -> None:
    assert station_is_supported({"codec": "MP3"}, MP3_ONLY) is True


def test_specialized_backend_rejects_unknown_codec() -> None:
    assert station_is_supported({"codec": "?"}, MP3_ONLY) is False


def test_specialized_backend_rejects_incompatible_codec() -> None:
    assert station_is_supported({"codec": "AAC"}, MP3_ONLY) is False


def test_ogg_backend_accepts_ogg_family_codecs() -> None:
    assert station_is_supported({"codec": "Ogg Vorbis"}, OGG_ONLY) is True
    assert station_is_supported({"codec": "Opus"}, OGG_ONLY) is True
    assert station_is_supported({"codec": "FLAC"}, OGG_ONLY) is True


def test_filter_supported_stations_keeps_only_compatible_items() -> None:
    stations = [
        {"name": "A", "codec": "MP3"},
        {"name": "B", "codec": "AAC"},
        {"name": "C", "codec": "?"},
    ]

    assert filter_supported_stations(stations, MP3_ONLY) == [stations[0]]
    assert filter_supported_stations(stations, GENERAL) == stations
