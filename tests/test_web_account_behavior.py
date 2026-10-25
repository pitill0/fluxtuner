# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Execute Account navigation and session behavior using Node.js."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def test_account_navigation_and_session_behavior() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for the Web behavior harness")

    root = Path(__file__).resolve().parents[1]
    script = root / "tests" / "web_account_behavior.mjs"
    result = subprocess.run(
        [node, str(script)],
        cwd=root,
        env={**os.environ, "WORK": str(root)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "BEHAVIOR_GATE=PASS" in result.stdout
