from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fluxtuner.players.base import PlayerAdapter, PlayerError


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

    with suppress(KeyboardInterrupt):
        subprocess.run(["mpv", "--no-video", url], check=False)  # noqa: S603


@dataclass
class MpvController(PlayerAdapter):
    """Non-blocking mpv controller using mpv's JSON IPC socket."""

    process: subprocess.Popen[bytes] | None = field(default=None, init=False)
    ipc_path: Path | None = field(default=None, init=False)
    volume_step: int = 5
    _request_id: int = field(default=0, init=False)

    @classmethod
    def is_available(cls) -> bool:
        try:
            ensure_mpv_available()
            return True
        except Exception:
            return False

    def play(self, url: str) -> None:
        """Play a stream URL.

        If mpv is already running, replace the stream using IPC. This keeps the
        session alive and makes switching stations feel much smoother.
        """
        ensure_mpv_available()

        if self.is_playing():
            self.load(url)
            return

        self.ipc_path = self._new_ipc_path()
        self.process = subprocess.Popen(  # noqa: S603
            [
                "mpv",
                "--no-video",
                "--really-quiet",
                "--force-window=no",
                f"--input-ipc-server={self.ipc_path}",
                url,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._wait_for_ipc_socket()

    def load(self, url: str) -> None:
        """Replace the currently playing URL without restarting mpv."""
        self.command(["loadfile", url, "replace"])

    def stop(self) -> None:
        """Stop the current mpv process if it is still running."""
        if not self.process:
            self._cleanup_ipc_socket()
            return

        if self.process.poll() is None:
            try:
                self.command(["quit"])
                self.process.wait(timeout=2)
            except Exception:  # noqa: BLE001
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=3)

        self.process = None
        self._cleanup_ipc_socket()

    def is_playing(self) -> bool:
        """Return True if mpv is currently running."""
        return self.process is not None and self.process.poll() is None

    def toggle_pause(self) -> None:
        """Toggle pause/resume in the current mpv instance."""
        self.command(["cycle", "pause"])

    def toggle_mute(self) -> None:
        """Toggle mute in the current mpv instance."""
        self.command(["cycle", "mute"])

    def volume_up(self) -> None:
        """Increase playback volume."""
        self.command(["add", "volume", self.volume_step])

    def volume_down(self) -> None:
        """Decrease playback volume."""
        self.command(["add", "volume", -self.volume_step])

    def set_volume(self, volume: int | float) -> None:
        """Set playback volume to an absolute value."""
        safe_volume = max(0, min(100, int(round(volume))))
        self.command(["set_property", "volume", safe_volume])

    def set_mute(self, muted: bool) -> None:
        """Set mute to an absolute value."""
        self.command(["set_property", "mute", bool(muted)])

    def get_property(self, name: str) -> Any:
        """Return an mpv property through JSON IPC."""
        response = self.command(["get_property", name])
        if not response or response.get("error") != "success":
            return None
        return response.get("data")

    def get_state(self) -> dict[str, Any]:
        """Return a compact snapshot of the current mpv state."""
        if not self.is_playing():
            return {"playing": False}
        return {
            "playing": True,
            "paused": bool(self.get_property("pause")),
            "muted": bool(self.get_property("mute")),
            "volume": self.get_property("volume"),
        }

    def command(self, command: list[Any]) -> dict[str, Any] | None:
        """Send a JSON IPC command to mpv and return the matching response.

        mpv can emit async event messages on the IPC socket. A request_id lets us
        ignore those events and read until the response for this command arrives.
        """
        if not self.is_playing() or not self.ipc_path:
            raise PlayerError("No active mpv playback session.")

        self._request_id += 1
        request_id = self._request_id
        payload = json.dumps({"command": command, "request_id": request_id}).encode("utf-8") + b"\n"

        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(1.5)
            client.connect(str(self.ipc_path))
            client.sendall(payload)

            buffer = b""
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    return None
                buffer += chunk

                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        message = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError:
                        continue
                    if message.get("request_id") == request_id:
                        return message

    def _new_ipc_path(self) -> Path:
        runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or tempfile.gettempdir()
        return Path(runtime_dir) / f"fluxtuner-mpv-{os.getpid()}.sock"

    def _wait_for_ipc_socket(self, timeout: float = 2.0) -> None:
        if not self.ipc_path:
            return

        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ipc_path.exists():
                return
            if self.process and self.process.poll() is not None:
                raise PlayerError("mpv exited before the IPC socket was ready.")
            time.sleep(0.05)

    def _cleanup_ipc_socket(self) -> None:
        if self.ipc_path and self.ipc_path.exists():
            with suppress(OSError):
                self.ipc_path.unlink()
        self.ipc_path = None


    def supports_pause(self) -> bool:
        return True

    def supports_volume(self) -> bool:
        return True

    def supports_mute(self) -> bool:
        return True
