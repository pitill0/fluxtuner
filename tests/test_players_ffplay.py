import pytest

from fluxtuner.players.base import PlayerError
from fluxtuner.players.ffplay import FfplayController


def test_ffplay_play_uses_resolved_executable(monkeypatch) -> None:
    from fluxtuner.players.ffplay import FfplayController

    created_commands = []

    class FakePopen:
        def __init__(self, command, **_kwargs):
            created_commands.append(command)

        def poll(self):
            return None

    monkeypatch.setattr(
        "fluxtuner.players.ffplay.resolve_executable", lambda _name: "/usr/bin/ffplay"
    )
    monkeypatch.setattr("subprocess.Popen", FakePopen)

    controller = FfplayController()
    controller.play("https://example.com/stream")

    assert created_commands
    assert created_commands[0][0] == "/usr/bin/ffplay"
    assert created_commands[0][-1] == "https://example.com/stream"


def test_ffplay_play_rejects_invalid_stream_url(monkeypatch) -> None:
    import pytest

    from fluxtuner.players.base import PlayerError
    from fluxtuner.players.ffplay import FfplayController

    monkeypatch.setattr(
        "fluxtuner.players.ffplay.resolve_executable", lambda _name: "/usr/bin/ffplay"
    )

    controller = FfplayController()

    with pytest.raises(PlayerError):
        controller.play("file:///tmp/test.mp3")


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


class AlreadyFinishedProcess:
    pid = 123

    def poll(self):
        return 0


def test_ffplay_stop_clears_finished_process() -> None:
    controller = FfplayController()
    controller.process = AlreadyFinishedProcess()  # type: ignore[assignment]

    controller.stop()

    assert controller.process is None


class WaitFailingProcess:
    pid = 123

    def __init__(self) -> None:
        self.killed = False

    def poll(self):
        return None

    def wait(self, timeout=None):
        raise RuntimeError("wait failed")

    def kill(self):
        self.killed = True


def test_ffplay_stop_clears_process_when_wait_fails(monkeypatch) -> None:
    controller = FfplayController()
    process = WaitFailingProcess()
    controller.process = process  # type: ignore[assignment]

    monkeypatch.setattr("os.getpgid", lambda _pid: 123)
    monkeypatch.setattr("os.killpg", lambda _pgid, _signal: None)

    with pytest.raises(RuntimeError):
        controller.stop()

    assert controller.process is None


def test_ffplay_play_continues_when_previous_stop_fails(monkeypatch) -> None:
    controller = FfplayController()

    class StopFailingProcess:
        pid = 123

        def poll(self):
            return None

        def wait(self, timeout=None):
            raise RuntimeError("wait failed")

        def kill(self):
            pass

    created_commands = []

    class FakePopen:
        def __init__(self, command, **_kwargs):
            created_commands.append(command)

        def poll(self):
            return None

    controller.process = StopFailingProcess()  # type: ignore[assignment]

    monkeypatch.setattr("os.getpgid", lambda _pid: 123)
    monkeypatch.setattr("os.killpg", lambda _pgid, _signal: None)
    monkeypatch.setattr("subprocess.Popen", FakePopen)

    controller.play("https://example.com/stream")

    assert created_commands
    assert created_commands[0][-1] == "https://example.com/stream"
    assert isinstance(controller.process, FakePopen)
