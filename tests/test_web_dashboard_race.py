# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Dashboard asynchronous navigation regression coverage."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_async_guards() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed")

    result = subprocess.run(
        [node, "tests/web_dashboard_race.mjs"],
        cwd=ROOT,
        env={**os.environ, "WORK": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "BEHAVIOR_GATE=PASS" in result.stdout
