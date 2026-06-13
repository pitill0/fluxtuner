from fluxtuner.__main__ import (
    PLAYER_BACKENDS,
    player_capabilities_summary,
    player_install_help,
    player_install_hint,
)
from fluxtuner.players.capabilities import PlayerCapabilities


def test_player_capabilities_summary_describes_general_purpose_backend(monkeypatch) -> None:
    class FakeBackend:
        @classmethod
        def capabilities(cls) -> PlayerCapabilities:
            return PlayerCapabilities(
                general_purpose=True,
                supports_pause=True,
                supports_volume=True,
                supports_mute=True,
            )

    monkeypatch.setitem(PLAYER_BACKENDS, "fake-general", FakeBackend)

    summary = player_capabilities_summary("fake-general")

    assert "general-purpose" in summary
    assert "controls: pause, volume, mute" in summary


def test_player_capabilities_summary_describes_specialized_backend(monkeypatch) -> None:
    class FakeBackend:
        @classmethod
        def capabilities(cls) -> PlayerCapabilities:
            return PlayerCapabilities(
                general_purpose=False,
                supported_codecs=frozenset({"mp3", "mpeg"}),
            )

    monkeypatch.setitem(PLAYER_BACKENDS, "fake-specialized", FakeBackend)

    summary = player_capabilities_summary("fake-specialized")

    assert "specialized" in summary
    assert "codecs: mp3, mpeg" in summary


def test_player_install_hint_returns_known_backend_hint() -> None:
    assert player_install_hint("mpv") == "install mpv"
    assert player_install_hint("ffplay") == "install FFmpeg / ffplay"
    assert player_install_hint("mpg123") == "install mpg123"
    assert player_install_hint("ogg123") == "install vorbis-tools / ogg123"


def test_player_install_hint_falls_back_to_backend_name() -> None:
    assert player_install_hint("custom") == "install custom"


def test_player_install_help_lists_all_registered_backends() -> None:
    help_text = player_install_help()

    for backend_name in PLAYER_BACKENDS:
        assert player_install_hint(backend_name) in help_text
