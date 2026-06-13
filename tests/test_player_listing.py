from fluxtuner.__main__ import PLAYER_BACKENDS, player_capabilities_summary
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
