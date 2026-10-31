#!/usr/bin/env python3
"""Run GTK contracts with real PyGObject bindings and a working display."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from types import ModuleType


def _configure_paths(bindings_dir: Path | None) -> Path:
    root = Path(__file__).resolve().parents[1]
    if bindings_dir is not None:
        bindings_dir = bindings_dir.resolve()
        if not (bindings_dir / "gi" / "__init__.py").is_file():
            raise RuntimeError("--bindings-dir must contain the real gi package")
        sys.path.insert(0, str(bindings_dir))
    sys.path.insert(0, str(root))
    return root


def _initialize_gtk() -> tuple[ModuleType, ModuleType]:
    try:
        import gi
    except ImportError as exc:
        raise RuntimeError(
            "PyGObject is unavailable. Use a compatible GTK environment or "
            "--bindings-dir with ABI-compatible gi/Cairo packages."
        ) from exc

    gi.require_version("Gtk", "4.0")
    from gi.repository import Gtk

    if not Gtk.init_check():
        raise RuntimeError("GTK could not initialize a display for this test run")
    print(f"PyGObject: {gi.__version__} ({gi.__file__})", flush=True)
    print(
        f"GTK: {Gtk.get_major_version()}.{Gtk.get_minor_version()}.{Gtk.get_micro_version()}",
        flush=True,
    )
    return gi, Gtk


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindings-dir", type=Path)
    options, pytest_args = parser.parse_known_args(argv)
    root = _configure_paths(options.bindings_dir)
    real_gi, real_gtk = _initialize_gtk()

    import pytest

    if pytest_args[:1] == ["--"]:
        pytest_args = pytest_args[1:]
    if not pytest_args:
        pytest_args = [str(path) for path in sorted((root / "tests").glob("test_gtk*.py"))]
        if not pytest_args:
            raise RuntimeError("No GTK contract tests found")
    result = pytest.main(["-ra", *pytest_args])
    if sys.modules.get("gi") is not real_gi or sys.modules.get("gi.repository.Gtk") is not real_gtk:
        raise RuntimeError("The test run replaced the real GTK bindings")
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
