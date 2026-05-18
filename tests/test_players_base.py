import pytest

from fluxtuner.players.base import PlayerAdapter, PlayerError


class DummyPlayer(PlayerAdapter):
    def __init__(self) -> None:
        self.played_url = None
        self.stopped = False
        self.playing = False

    def play(self, url: str) -> None:
        self.played_url = url
        self.playing = True

    def stop(self) -> None:
        self.stopped = True
        self.playing = False

    def is_playing(self) -> bool:
        return self.playing


def test_player_adapter_default_capabilities_are_false() -> None:
    player = DummyPlayer()

    assert player.supports_pause() is False
    assert player.supports_volume() is False
    assert player.supports_mute() is False


def test_player_adapter_default_controls_raise_player_error() -> None:
    player = DummyPlayer()

    with pytest.raises(PlayerError, match="Pause is not supported"):
        player.toggle_pause()

    with pytest.raises(PlayerError, match="Mute is not supported"):
        player.toggle_mute()

    with pytest.raises(PlayerError, match="Volume control is not supported"):
        player.volume_up()

    with pytest.raises(PlayerError, match="Volume control is not supported"):
        player.volume_down()

    with pytest.raises(PlayerError, match="Volume control is not supported"):
        player.set_volume(50)

    with pytest.raises(PlayerError, match="Mute is not supported"):
        player.set_mute(True)


def test_player_adapter_default_state_uses_is_playing() -> None:
    player = DummyPlayer()

    assert player.get_state() == {"playing": False}

    player.play("https://example.com/stream")

    assert player.get_state() == {"playing": True}
