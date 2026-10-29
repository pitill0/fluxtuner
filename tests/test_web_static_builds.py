"""Tests for persistent, content-addressed static builds."""

from pathlib import Path

import pytest

from fluxtuner.web.static_builds import (
    StaticBuildError,
    create_static_snapshot,
    verify_static_snapshot,
)


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    (source / "js").mkdir(parents=True)
    (source / "app.js").write_text(
        'import { example } from "./js/example.js";\n',
        encoding="utf-8",
    )
    (source / "js" / "example.js").write_text(
        "export const example = 1;\n",
        encoding="utf-8",
    )
    return source


def test_snapshot_publishes_verified_tree(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"

    build = create_static_snapshot(source, root)

    assert len(build.build_id) == 16
    assert build.directory == root / build.build_id
    assert verify_static_snapshot(build.directory, build.build_id)
    assert (build.directory / "app.js").read_bytes() == (source / "app.js").read_bytes()


def test_snapshot_reuses_identical_build(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"

    first = create_static_snapshot(source, root)
    second = create_static_snapshot(source, root)

    assert first == second
    assert len(list(root.glob("[0-9a-f]" * 16))) == 1


def test_source_changes_create_new_build_without_overwrite(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"

    first = create_static_snapshot(source, root)
    old_bytes = (first.directory / "app.js").read_bytes()

    (source / "app.js").write_text("export const version = 2;\n", encoding="utf-8")
    second = create_static_snapshot(source, root)

    assert first.build_id != second.build_id
    assert (first.directory / "app.js").read_bytes() == old_bytes
    assert verify_static_snapshot(first.directory, first.build_id)
    assert verify_static_snapshot(second.directory, second.build_id)


def test_snapshot_detects_modified_published_bytes(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"
    build = create_static_snapshot(source, root)

    (build.directory / "app.js").write_text("modified\n", encoding="utf-8")

    assert not verify_static_snapshot(build.directory, build.build_id)
    with pytest.raises(StaticBuildError):
        create_static_snapshot(source, root)


def test_snapshot_rejects_source_symlink(tmp_path: Path) -> None:
    source = _source(tmp_path)
    (source / "js" / "external.js").symlink_to(source / "app.js")

    with pytest.raises(StaticBuildError):
        create_static_snapshot(source, tmp_path / "builds")


def test_snapshot_rejects_symlink_root(tmp_path: Path) -> None:
    source = _source(tmp_path)
    real_root = tmp_path / "real-builds"
    real_root.mkdir()
    linked_root = tmp_path / "linked-builds"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(StaticBuildError):
        create_static_snapshot(source, linked_root)


def test_snapshot_detects_unexpected_added_file(tmp_path: Path) -> None:
    source = _source(tmp_path)
    build = create_static_snapshot(source, tmp_path / "builds")

    (build.directory / "unexpected.js").write_text("export {};\n", encoding="utf-8")

    assert not verify_static_snapshot(build.directory, build.build_id)
