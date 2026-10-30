"""Adversarial temporary snapshot cleanup contracts."""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

import pytest

from fluxtuner.web import static_builds


def test_cleanup_refuses_symlink_substitution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "builds"
    root.mkdir()

    temporary = root / ".tmp-stale"
    temporary.mkdir()
    (temporary / "partial.js").write_text("partial")

    timestamp = time.time() - 7200
    os.utime(temporary, (timestamp, timestamp))

    external = tmp_path / "external"
    external.mkdir()
    important = external / "important.txt"
    important.write_text("must survive")

    original_rmtree = shutil.rmtree

    def substitute_before_delete(path: Path, *args: object, **kwargs: object) -> None:
        candidate = Path(path)
        assert candidate == temporary

        candidate.rename(root / ".moved-original")
        candidate.symlink_to(external, target_is_directory=True)

        original_rmtree(candidate, *args, **kwargs)

    monkeypatch.setattr(
        static_builds.shutil,
        "rmtree",
        substitute_before_delete,
    )

    with pytest.raises(OSError):
        static_builds._clean_stale_temporaries(root)

    assert important.read_text() == "must survive"
    assert temporary.is_symlink()
    assert (root / ".moved-original" / "partial.js").read_text() == "partial"
