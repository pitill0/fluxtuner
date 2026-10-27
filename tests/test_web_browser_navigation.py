# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Browser URL navigation and history behavior."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_browser_navigation_behavior() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed")
    result = subprocess.run(
        [node, "tests/web_browser_navigation.mjs"],
        cwd=ROOT,
        env={**os.environ, "WORK": str(ROOT)},
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "BEHAVIOR_GATE=PASS" in result.stdout
