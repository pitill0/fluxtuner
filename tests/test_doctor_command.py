from pathlib import Path

from fluxtuner.__main__ import path_diagnostic_status


def test_path_diagnostic_status_reports_present_path(tmp_path: Path) -> None:
    target = tmp_path / "existing"
    target.mkdir()

    assert path_diagnostic_status(target) == "present"


def test_path_diagnostic_status_reports_missing_path_with_present_parent(tmp_path: Path) -> None:
    target = tmp_path / "missing"

    assert path_diagnostic_status(target) == "missing"


def test_path_diagnostic_status_reports_missing_parent(tmp_path: Path) -> None:
    target = tmp_path / "missing-parent" / "child"

    assert path_diagnostic_status(target) == "parent missing"
