# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Cross-controller races using shared Web result elements."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_shared_results_concurrency() -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed")

    result = subprocess.run(
        [node, "tests/web_shared_results_race.mjs"],
        cwd=ROOT,
        env={**os.environ, "WORK": str(ROOT)},
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "BEHAVIOR_GATE=PASS" in result.stdout
