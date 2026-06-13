from fluxtuner.players import PLAYER_BACKENDS
from fluxtuner.players.capabilities import PlayerCapabilities


def test_all_registered_backends_declare_capabilities() -> None:
    for controller_class in PLAYER_BACKENDS.values():
        assert isinstance(controller_class.capabilities(), PlayerCapabilities)


def test_mpv_is_general_purpose_with_live_controls() -> None:
    capabilities = PLAYER_BACKENDS["mpv"].capabilities()

    assert capabilities.general_purpose is True
    assert capabilities.supports_volume is True
    assert capabilities.supports_mute is True


def test_ffplay_is_general_purpose_without_live_controls() -> None:
    capabilities = PLAYER_BACKENDS["ffplay"].capabilities()

    assert capabilities.general_purpose is True
    assert capabilities.supports_volume is False
    assert capabilities.supports_mute is False


def test_specialized_backends_are_not_general_purpose() -> None:
    mpg123 = PLAYER_BACKENDS["mpg123"].capabilities()
    ogg123 = PLAYER_BACKENDS["ogg123"].capabilities()

    assert mpg123.general_purpose is False
    assert "mp3" in mpg123.supported_codecs
    assert ogg123.general_purpose is False
    assert {"ogg", "vorbis", "opus", "flac"} <= ogg123.supported_codecs
