"""Regression checks for the mandatory Brynse CI contract gate."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _contract_gate_command() -> str:
    """Extract the checker from the actual GitHub Actions workflow."""
    source = WORKFLOW.read_text(encoding="utf-8")
    marker = "      - name: Reject skipped or missing contracts\n"
    assert source.count(marker) == 1

    section = source.split(marker, 1)[1]
    assert section.startswith("        run: |\n")

    lines = []
    for line in section.splitlines()[1:]:
        if line and not line.startswith("          "):
            break
        if line:
            lines.append(line[10:])
        else:
            lines.append("")

    command = "\n".join(lines).strip()
    assert command.startswith("python - <<'PYVERIFY'")
    assert command.endswith("\nPYVERIFY")
    return command


@pytest.mark.parametrize(
    ("summary", "accepted"),
    [
        ({"collected": 7, "total": 7, "passed": 7}, True),
        ({"collected": 8, "total": 8, "passed": 8}, True),
        ({"collected": 7, "total": 7, "passed": 6, "skipped": 1}, False),
        ({"collected": 7, "total": 7, "passed": 6, "failed": 1}, False),
        ({"collected": 7, "total": 7, "passed": 6, "error": 1}, False),
        ({"collected": 6, "total": 6, "passed": 6}, False),
        ({"collected": 7, "total": 6, "passed": 6}, False),
        ({"collected": 0, "total": 0, "passed": 0}, False),
    ],
)
def test_brynse_ci_contract_gate_rejects_incomplete_coverage(
    tmp_path: Path,
    summary: dict[str, int],
    accepted: bool,
) -> None:
    (tmp_path / "brynse-contracts.json").write_text(
        json.dumps({"summary": summary}),
        encoding="utf-8",
    )

    command = _contract_gate_command()

    result = subprocess.run(
        ["bash", "-c", command],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert (result.returncode == 0) is accepted, (
        result.returncode,
        result.stdout,
        result.stderr,
    )
