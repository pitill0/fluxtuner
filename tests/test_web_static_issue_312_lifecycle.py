"""Regression tests for safe temporary snapshot maintenance."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from fluxtuner.web.static_builds import (
    StaticBuildError,
    create_static_snapshot,
    verify_static_snapshot,
)


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.js").write_text("export const ready = true;\n")
    return source


def test_old_temporary_removed_new_temporary_preserved(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"
    root.mkdir()

    old = root / ".tmp-old"
    recent = root / ".tmp-recent"
    old.mkdir()
    recent.mkdir()
    (old / "partial.js").write_text("old")
    (recent / "partial.js").write_text("recent")

    timestamp = time.time() - 7200
    os.utime(old, (timestamp, timestamp))

    build = create_static_snapshot(source, root)

    assert not old.exists()
    assert recent.is_dir()
    assert (recent / "partial.js").read_text() == "recent"
    assert verify_static_snapshot(build.directory, build.build_id)


def test_temporary_symlink_is_not_followed(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"
    root.mkdir()

    external = tmp_path / "external"
    external.mkdir()
    (external / "important.txt").write_text("preserve")

    link = root / ".tmp-external"
    link.symlink_to(external, target_is_directory=True)

    create_static_snapshot(source, root)

    assert link.is_symlink()
    assert (external / "important.txt").read_text() == "preserve"


def test_corrupt_build_is_preserved_with_diagnostic(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"

    build = create_static_snapshot(source, root)
    damaged_file = build.directory / "app.js"
    damaged_file.write_text("corrupt")

    with pytest.raises(StaticBuildError, match="manual recovery required") as error:
        create_static_snapshot(source, root)

    assert build.build_id in str(error.value)
    assert damaged_file.read_text() == "corrupt"
