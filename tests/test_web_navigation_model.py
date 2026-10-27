# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Behavioral checks for the UX-02 navigation model."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_navigation_model_behavior() -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js is not installed")

    result = subprocess.run(
        [node, "tests/web_navigation_model.mjs"],
        cwd=ROOT,
        env={**os.environ, "WORK": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "BEHAVIOR_GATE=PASS" in result.stdout
