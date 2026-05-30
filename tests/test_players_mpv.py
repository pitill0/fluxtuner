import logging
from pathlib import Path

import pytest

from fluxtuner.players.mpv import MpvController


class FinishedProcess:
    def poll(self):
        return 0


def test_mpv_play_uses_resolved_executable(monkeypatch) -> None:
    from fluxtuner.players.mpv import MpvController

    created_commands = []

    class FakePopen:
        def __init__(self, command, **_kwargs):
            created_commands.append(command)

        def poll(self):
            return None

    controller = MpvController()

    monkeypatch.setattr("fluxtuner.players.mpv.resolve_executable", lambda _name: "/usr/bin/mpv")
    monkeypatch.setattr("subprocess.Popen", FakePopen)
    monkeypatch.setattr(controller, "_wait_for_ipc_socket", lambda: None)

    controller.play("https://example.com/stream")

    assert created_commands
    assert created_commands[0][0] == "/usr/bin/mpv"
    assert created_commands[0][-1] == "https://example.com/stream"


def test_mpv_play_rejects_invalid_stream_url(monkeypatch) -> None:
    from fluxtuner.players.base import PlayerError
    from fluxtuner.players.mpv import MpvController

    controller = MpvController()

    monkeypatch.setattr("fluxtuner.players.mpv.resolve_executable", lambda _name: "/usr/bin/mpv")

    with pytest.raises(PlayerError):
        controller.play("file:///tmp/test.mp3")


def test_mpv_is_playing_cleans_up_finished_process(tmp_path: Path) -> None:
    controller = MpvController()
    ipc_path = tmp_path / "mpv.sock"
    ipc_path.write_text("", encoding="utf-8")

    controller.process = FinishedProcess()  # type: ignore[assignment]
    controller.ipc_path = ipc_path

    assert controller.is_playing() is False
    assert controller.process is None
    assert controller.ipc_path is None
    assert not ipc_path.exists()


class RunningProcess:
    def poll(self):
        return None


def test_mpv_is_playing_returns_true_for_running_process(tmp_path: Path) -> None:
    controller = MpvController()
    ipc_path = tmp_path / "mpv.sock"
    ipc_path.write_text("", encoding="utf-8")

    controller.process = RunningProcess()  # type: ignore[assignment]
    controller.ipc_path = ipc_path

    assert controller.is_playing() is True
    assert controller.process is not None
    assert controller.ipc_path == ipc_path
    assert ipc_path.exists()


def test_mpv_play_logs_without_stream_url(monkeypatch, caplog) -> None:
    from fluxtuner.players.mpv import MpvController

    created_commands = []

    class FakePopen:
        def __init__(self, command, **_kwargs):
            created_commands.append(command)

        def poll(self):
            return None

    controller = MpvController()

    monkeypatch.setattr("fluxtuner.players.mpv.resolve_executable", lambda _name: "/usr/bin/mpv")
    monkeypatch.setattr("subprocess.Popen", FakePopen)
    monkeypatch.setattr(controller, "_wait_for_ipc_socket", lambda: None)

    with caplog.at_level(logging.DEBUG):
        controller.play("https://example.com/private-stream")

    assert created_commands
    assert "Starting mpv playback" in caplog.text
    assert "https://example.com/private-stream" not in caplog.text
