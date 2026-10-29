"""Adversarial tests for persistent Web static snapshots."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
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
        'import "./js/module.js";\n',
        encoding="utf-8",
    )
    (source / "js" / "module.js").write_text(
        "export const ready = true;\n",
        encoding="utf-8",
    )
    return source


def _publish_in_process(source: str, root: str) -> str:
    return create_static_snapshot(Path(source), Path(root)).build_id


def test_concurrent_processes_publish_same_build(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"

    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(_publish_in_process, str(source), str(root)) for _ in range(2)]
        build_ids = [future.result(timeout=20) for future in futures]

    assert build_ids[0] == build_ids[1]
    assert verify_static_snapshot(root / build_ids[0], build_ids[0])
    assert len(list(root.glob("[0-9a-f]" * 16))) == 1


def test_published_file_symlink_fails_verification(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"
    build = create_static_snapshot(source, root)

    external = tmp_path / "external.js"
    external.write_text("export const altered = true;\n", encoding="utf-8")

    published_file = build.directory / "app.js"
    published_file.unlink()
    published_file.symlink_to(external)

    assert not verify_static_snapshot(build.directory, build.build_id)

    with pytest.raises(StaticBuildError):
        create_static_snapshot(source, root)


def test_missing_manifest_fails_verification(tmp_path: Path) -> None:
    source = _source(tmp_path)
    root = tmp_path / "builds"
    build = create_static_snapshot(source, root)

    (build.directory / ".fluxtuner-manifest.json").unlink()

    assert not verify_static_snapshot(build.directory, build.build_id)

    with pytest.raises(StaticBuildError):
        create_static_snapshot(source, root)


def test_symlinked_storage_parent_is_rejected(tmp_path: Path) -> None:
    source = _source(tmp_path)

    actual_parent = tmp_path / "actual-parent"
    actual_parent.mkdir()

    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(actual_parent, target_is_directory=True)

    with pytest.raises(StaticBuildError):
        create_static_snapshot(source, linked_parent / "builds")
