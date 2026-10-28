# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""UX-03 browser-independent JavaScript controller contract."""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_unified_library_controller() -> None:
    root = Path(__file__).resolve().parents[1]
    subprocess.run(
        ["node", "tests/web_unified_library.mjs"],
        cwd=root,
        check=True,
        timeout=30,
    )
