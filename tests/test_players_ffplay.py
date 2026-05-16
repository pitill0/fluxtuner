import pytest

from fluxtuner.players.base import PlayerError
from fluxtuner.players.ffplay import FfplayController


def test_ffplay_reports_live_capabilities() -> None:
    player = FfplayController()

    assert player.supports_pause() is False
    assert player.supports_volume() is False
    assert player.supports_mute() is False


def test_ffplay_stores_startup_volume_preference() -> None:
    player = FfplayController()

    player.set_volume(250)
    assert player.get_state()["volume"] == 100

    player.set_volume(-10)
    assert player.get_state()["volume"] == 0

    player.set_volume(42.6)
    assert player.get_state()["volume"] == 43


def test_ffplay_stores_startup_mute_preference() -> None:
    player = FfplayController()

    player.set_mute(True)
    assert player.get_state()["muted"] is True

    player.set_mute(False)
    assert player.get_state()["muted"] is False


def test_ffplay_does_not_support_live_mute_toggle() -> None:
    player = FfplayController()

    with pytest.raises(PlayerError, match="Mute is not supported"):
        player.toggle_mute()
