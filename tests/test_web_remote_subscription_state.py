"""Regression checks for remote subscription dialog state."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def test_remote_subscription_dialog_state() -> None:
    node = shutil.which("node")
    assert node, "Node.js is required for Web JavaScript tests"

    script = Path(__file__).with_name("web_remote_subscription_state.mjs")

    result = subprocess.run(
        [node, str(script)],
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
