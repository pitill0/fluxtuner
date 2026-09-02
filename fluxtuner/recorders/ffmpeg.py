from __future__ import annotations

import os
import signal
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

from fluxtuner.core.recording import RecordingError
from fluxtuner.logging_config import get_logger
from fluxtuner.players.base import PlayerError
from fluxtuner.players.security import resolve_executable, validate_stream_url

logger = get_logger(__name__)


class FfmpegRecorder:
    """Record one radio stream with FFmpeg stream copy."""

    def __init__(self) -> None:
        self.process: subprocess.Popen[Any] | None = None

    @classmethod
    def is_available(cls) -> bool:
        try:
            resolve_executable("ffmpeg")
            return True
        except PlayerError:
            logger.debug("ffmpeg recorder is not available")
            return False

    def start(self, source_url: str, output_path: Path) -> None:
        """Start recording a stream into a Matroska audio file."""
        if self.is_recording():
            raise RecordingError("FFmpeg recording is already active.")

        try:
            ffmpeg_path = resolve_executable("ffmpeg")
            safe_url = validate_stream_url(source_url)
        except PlayerError as exc:
            raise RecordingError(str(exc)) from exc

        output_path = output_path.expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        command = [
            ffmpeg_path,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-readrate",
            "1",
            "-i",
            safe_url,
            "-map",
            "0:a:0",
            "-c",
            "copy",
            "-f",
            "matroska",
            "-y",
            str(output_path),
        ]

        logger.debug("Starting FFmpeg recording")
        try:
            self.process = subprocess.Popen(  # noqa: S603  # nosec B603
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise RecordingError(f"Could not start ffmpeg: {exc}") from exc

        logger.debug("FFmpeg recording process started")

    def stop(self) -> None:
        """Stop recording gracefully so FFmpeg can finalize the container."""
        if self.process is None:
            logger.debug("FFmpeg stop requested without active recording")
            return

        process = self.process

        try:
            if process.poll() is None:
                logger.debug("Stopping FFmpeg recording process")
                try:
                    os.killpg(os.getpgid(process.pid), signal.SIGINT)
                    process.wait(timeout=5)
                except Exception:  # noqa: BLE001
                    logger.debug(
                        "Graceful FFmpeg stop failed; killing process group",
                        exc_info=True,
                    )
                    try:
                        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                    except Exception:  # noqa: BLE001
                        logger.debug(
                            "Could not kill FFmpeg process group; killing process",
                            exc_info=True,
                        )
                        process.kill()
                    process.wait(timeout=3)
        finally:
            self.process = None
            logger.debug("FFmpeg recording process stopped")

    def is_recording(self) -> bool:
        return self.process is not None and self.process.poll() is None
