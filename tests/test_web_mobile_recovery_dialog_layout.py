# SPDX-License-Identifier: MIT
"""Regression contract for mobile recovery-dialog stacking."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "fluxtuner/web"


def test_recovery_modals_are_above_mobile_header_and_menu() -> None:
    dialogs = (ROOT / "static/dialogs.css").read_text()
    shell = (ROOT / "static/shell.css").read_text()
    markup = (ROOT / "templates/index.html").read_text()

    assert 'class="playlist-dialog recovery-codes-dialog"' in markup
    assert "data-recovery-codes-regenerate-dialog" in markup
    assert re.search(r"\.app-header\s*\{[^}]*z-index:\s*70;", shell, re.S)
    assert re.search(r"\.app-menu\s*\{[^}]*z-index:\s*90;", shell, re.S)
    assert re.search(
        r"\.recovery-codes-dialog\s*,\s*"
        r"\[data-recovery-codes-regenerate-dialog\]\s*"
        r"\{\s*z-index:\s*(\d+);\s*\}",
        dialogs,
    )
    match = re.search(
        r"\.recovery-codes-dialog\s*,\s*"
        r"\[data-recovery-codes-regenerate-dialog\]\s*"
        r"\{\s*z-index:\s*(\d+);\s*\}",
        dialogs,
    )
    assert int(match.group(1)) > 90


def test_recovery_dialog_retains_mobile_scrolling_and_close_control() -> None:
    dialogs = (ROOT / "static/dialogs.css").read_text()
    markup = (ROOT / "templates/index.html").read_text()
    assert "overflow-y: auto !important" in dialogs
    assert "max-height: calc(100dvh" in dialogs
    assert "data-recovery-codes-close" in markup
