from pathlib import Path

from fluxtuner.players.mpv import MpvController


class FinishedProcess:
    def poll(self):
        return 0


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
