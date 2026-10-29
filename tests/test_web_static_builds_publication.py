"""Failure and race-condition tests for snapshot publication."""

from __future__ import annotations

from pathlib import Path

import pytest

from fluxtuner.web import static_builds
from fluxtuner.web.static_builds import (
    StaticBuildError,
    create_static_snapshot,
)


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "app.js").write_text("export const ready = true;\n", encoding="utf-8")
    return source


def test_external_destination_race_never_overwrites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"
    original_rename = static_builds._publish_exclusive
    created = []

    def competing_rename(src, dst):
        destination = Path(dst)
        destination.mkdir()
        created.append(destination)
        return original_rename(src, dst)

    monkeypatch.setattr(static_builds, "_publish_exclusive", competing_rename)

    with pytest.raises((StaticBuildError, FileExistsError)):
        create_static_snapshot(source, root)

    assert len(created) == 1
    assert created[0].is_dir()
    assert not (created[0] / "app.js").exists()
    assert not list(root.glob(".tmp-*"))


def test_failed_copy_does_not_publish_partial_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"
    original_read = Path.read_bytes
    reads = 0

    def failing_read(path: Path) -> bytes:
        nonlocal reads
        if path == source / "app.js":
            reads += 1
            if reads == 2:
                raise OSError("Simulated source read failure")
        return original_read(path)

    monkeypatch.setattr(Path, "read_bytes", failing_read)

    with pytest.raises((OSError, StaticBuildError)):
        create_static_snapshot(source, root)

    assert not list(root.glob("[0-9a-f]" * 16))
    assert not list(root.glob(".tmp-*"))


def test_existing_corrupt_destination_is_preserved(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"

    first = create_static_snapshot(source, root)
    original = first.directory / "app.js"
    original.write_text("corrupted\n", encoding="utf-8")

    with pytest.raises(StaticBuildError):
        create_static_snapshot(source, root)

    assert original.read_text(encoding="utf-8") == "corrupted\n"
    assert not list(root.glob(".tmp-*"))
