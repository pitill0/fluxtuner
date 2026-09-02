from pathlib import Path

import pytest

from fluxtuner.core.recording import RecordingError
from fluxtuner.recorders.ffmpeg import FfmpegRecorder


def test_ffmpeg_recorder_reports_availability(monkeypatch) -> None:
    monkeypatch.setattr(
        "fluxtuner.recorders.ffmpeg.resolve_executable",
        lambda _name: "/usr/bin/ffmpeg",
    )

    assert FfmpegRecorder.is_available() is True


def test_ffmpeg_recorder_reports_missing_executable(monkeypatch) -> None:
    from fluxtuner.players.base import PlayerError

    def missing(_name: str) -> str:
        raise PlayerError("ffmpeg missing")

    monkeypatch.setattr("fluxtuner.recorders.ffmpeg.resolve_executable", missing)

    assert FfmpegRecorder.is_available() is False


def test_ffmpeg_recorder_start_uses_stream_copy_and_matroska(
    monkeypatch,
    tmp_path: Path,
) -> None:
    created_commands: list[list[str]] = []

    class FakePopen:
        pid = 123

        def __init__(self, command, **kwargs):
            created_commands.append(command)
            self.kwargs = kwargs

        def poll(self):
            return None

    monkeypatch.setattr(
        "fluxtuner.recorders.ffmpeg.resolve_executable",
        lambda _name: "/usr/bin/ffmpeg",
    )
    monkeypatch.setattr("subprocess.Popen", FakePopen)

    output = tmp_path / "session.mka"
    recorder = FfmpegRecorder()
    recorder.start("https://example.com/stream", output)

    assert created_commands == [
        [
            "/usr/bin/ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-i",
            "https://example.com/stream",
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-f",
            "matroska",
            "-y",
            str(output),
        ]
    ]
    assert recorder.is_recording() is True


def test_ffmpeg_recorder_rejects_invalid_stream_url(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "fluxtuner.recorders.ffmpeg.resolve_executable",
        lambda _name: "/usr/bin/ffmpeg",
    )
    recorder = FfmpegRecorder()

    with pytest.raises(RecordingError, match="Unsupported or invalid stream URL"):
        recorder.start("file:///tmp/source.mp3", tmp_path / "session.mka")


def test_ffmpeg_recorder_rejects_parallel_start(
    monkeypatch,
    tmp_path: Path,
) -> None:
    class RunningProcess:
        pid = 123

        def poll(self):
            return None

    recorder = FfmpegRecorder()
    recorder.process = RunningProcess()  # type: ignore[assignment]

    with pytest.raises(RecordingError, match="already active"):
        recorder.start("https://example.com/stream", tmp_path / "session.mka")


class FinishedProcess:
    pid = 123

    def poll(self):
        return 0


def test_ffmpeg_recorder_stop_clears_finished_process() -> None:
    recorder = FfmpegRecorder()
    recorder.process = FinishedProcess()  # type: ignore[assignment]

    recorder.stop()

    assert recorder.process is None


def test_ffmpeg_recorder_stop_sends_sigint_before_kill(
    monkeypatch,
) -> None:
    events: list[tuple[str, object]] = []

    class RunningProcess:
        pid = 123

        def poll(self):
            return None

        def wait(self, timeout=None):
            events.append(("wait", timeout))
            return 0

        def kill(self):
            events.append(("kill", None))

    recorder = FfmpegRecorder()
    recorder.process = RunningProcess()  # type: ignore[assignment]

    monkeypatch.setattr("os.getpgid", lambda _pid: 456)
    monkeypatch.setattr(
        "os.killpg",
        lambda pgid, sig: events.append(("signal", (pgid, sig))),
    )

    recorder.stop()

    import signal

    assert events == [
        ("signal", (456, signal.SIGINT)),
        ("wait", 5),
    ]
    assert recorder.process is None


def test_ffmpeg_recorder_start_failure_leaves_recorder_idle(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(
        "fluxtuner.recorders.ffmpeg.resolve_executable",
        lambda _name: "/usr/bin/ffmpeg",
    )

    def fail_popen(*_args, **_kwargs):
        raise OSError("cannot execute")

    monkeypatch.setattr("subprocess.Popen", fail_popen)

    recorder = FfmpegRecorder()

    with pytest.raises(RecordingError, match="Could not start ffmpeg"):
        recorder.start("https://example.com/stream", tmp_path / "session.mka")

    assert recorder.process is None


def test_ffmpeg_recorder_logs_without_stream_url(
    monkeypatch,
    caplog,
    tmp_path: Path,
) -> None:
    import logging

    class FakePopen:
        pid = 123

        def __init__(self, _command, **_kwargs):
            pass

        def poll(self):
            return None

    monkeypatch.setattr(
        "fluxtuner.recorders.ffmpeg.resolve_executable",
        lambda _name: "/usr/bin/ffmpeg",
    )
    monkeypatch.setattr("subprocess.Popen", FakePopen)

    recorder = FfmpegRecorder()
    with caplog.at_level(logging.DEBUG):
        recorder.start(
            "https://example.com/private-stream",
            tmp_path / "session.mka",
        )

    assert "Starting FFmpeg recording" in caplog.text
    assert "https://example.com/private-stream" not in caplog.text
