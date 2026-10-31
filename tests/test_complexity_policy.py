# SPDX-License-Identifier: MIT
"""Keep C901 exceptions explicit and prevent their complexity from increasing."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path


def test_python_complexity_matches_reviewed_exception_budgets() -> None:
    root = Path(__file__).resolve().parents[1]
    policy = json.loads((root / "docs/complexity-baseline.json").read_text())
    config = tomllib.loads((root / "pyproject.toml").read_text())
    lint = config["tool"]["ruff"]["lint"]
    threshold = policy["max_complexity"]
    assert threshold == lint["mccabe"]["max-complexity"] == 15
    assert "C901" in lint["select"]

    # Isolated scanning prevents noqa or per-file ignores from hiding new debt.
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--no-cache",
            "--ignore-noqa",
            "--select",
            "C901",
            "--config",
            f"lint.mccabe.max-complexity={threshold}",
            "--output-format",
            "json",
            ".",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode in (0, 1), completed.stderr
    actual = {}
    for row in json.loads(completed.stdout):
        assert row["code"] == "C901", row
        match = re.fullmatch(r"`([^`]+)` is too complex \((\d+) > (\d+)\)", row["message"])
        assert match is not None, row
        relative = Path(row["filename"]).relative_to(root).as_posix()
        key = (relative, match.group(1))
        assert key not in actual, f"Ambiguous function identity: {key}"
        actual[key] = int(match.group(2))

    expected = {}
    for entry in policy["exceptions"]:
        key = (entry["path"], entry["function"])
        assert key not in expected, f"Duplicate exception: {key}"
        assert entry["reason"].strip(), f"Missing exception justification: {key}"
        assert entry["max_complexity"] > threshold, f"Obsolete exception budget: {key}"
        expected[key] = entry["max_complexity"]

    assert actual.keys() == expected.keys(), (
        f"New exceptions: {actual.keys() - expected.keys()}; "
        f"Remove resolved exceptions: {expected.keys() - actual.keys()}"
    )
    for key, complexity in actual.items():
        assert complexity <= expected[key], (
            f"{key}: complexity {complexity} exceeds reviewed budget {expected[key]}"
        )
