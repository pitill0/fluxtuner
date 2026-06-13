from fluxtuner.__main__ import (
    PLAYER_BACKENDS,
    compatible_stations_for_player,
    station_supported_by_player,
)
from fluxtuner.players.capabilities import PlayerCapabilities


class Mp3OnlyBackend:
    @classmethod
    def capabilities(cls) -> PlayerCapabilities:
        return PlayerCapabilities(
            general_purpose=False,
            supported_codecs=frozenset({"mp3"}),
        )


class GeneralBackend:
    @classmethod
    def capabilities(cls) -> PlayerCapabilities:
        return PlayerCapabilities(general_purpose=True)


def test_legacy_cli_filters_incompatible_stations(monkeypatch) -> None:
    stations = [
        {"name": "MP3 station", "codec": "MP3", "url": "https://example.com/a.mp3"},
        {"name": "AAC station", "codec": "AAC", "url": "https://example.com/aac"},
        {"name": "Unknown station", "codec": "?", "url": "https://example.com/unknown"},
    ]
    monkeypatch.setitem(PLAYER_BACKENDS, "mp3-only", Mp3OnlyBackend)

    assert compatible_stations_for_player(stations, "mp3-only") == [stations[0]]


def test_legacy_cli_keeps_all_stations_for_general_backend(monkeypatch) -> None:
    stations = [
        {"name": "MP3 station", "codec": "MP3", "url": "https://example.com/a.mp3"},
        {"name": "Unknown station", "codec": "?", "url": "https://example.com/unknown"},
    ]
    monkeypatch.setitem(PLAYER_BACKENDS, "general", GeneralBackend)

    assert compatible_stations_for_player(stations, "general") == stations


def test_legacy_cli_station_support_uses_existing_player_when_available(monkeypatch) -> None:
    class FakePlayer:
        @classmethod
        def capabilities(cls) -> PlayerCapabilities:
            return PlayerCapabilities(
                general_purpose=False,
                supported_codecs=frozenset({"ogg"}),
            )

    monkeypatch.setitem(PLAYER_BACKENDS, "mp3-only", Mp3OnlyBackend)

    assert (
        station_supported_by_player(
            {"name": "Ogg station", "codec": "OGG", "url": "https://example.com/a.ogg"},
            "mp3-only",
            FakePlayer(),
        )
        is True
    )
