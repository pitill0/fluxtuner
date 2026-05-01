from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field


class PlayerError(RuntimeError):
    """Raised when the external audio player cannot be used."""


def is_mpv_available() -> bool:
    """Return True when mpv is installed and available in PATH."""
    return shutil.which("mpv") is not None


def ensure_mpv_available() -> None:
    """Fail early if mpv is not installed or not available in PATH."""
    if not is_mpv_available():
        raise PlayerError(
            "mpv is required but was not found in PATH. "
            "Please install mpv and try again."
        )


def play_stream(url: str) -> None:
    """Play a stream URL using mpv and block until mpv exits."""
    ensure_mpv_available()

    try:
        subprocess.run(["mpv", "--no-video", url], check=False)
    except KeyboardInterrupt:
        pass


@dataclass
class MpvController:
    """Small non-blocking controller for mpv, useful for TUI usage."""

    process: subprocess.Popen[bytes] | None = field(default=None, init=False)

    def play(self, url: str) -> None:
        """Start playing a stream URL, stopping any previous stream first."""
        ensure_mpv_available()
        self.stop()
        self.process = subprocess.Popen(  # noqa: S603
            ["mpv", "--no-video", "--really-quiet", url],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop(self) -> None:
        """Stop the current mpv process if it is still running."""
        if not self.process:
            return

        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)

        self.process = None

    def is_playing(self) -> bool:
        """Return True if mpv is currently running."""
        return self.process is not None and self.process.poll() is None
