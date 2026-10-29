"""Verify that Web ESM imports remain relative and resolvable."""

from __future__ import annotations

import re
from pathlib import Path

STATIC_ROOT = Path(__file__).resolve().parents[1] / "fluxtuner" / "web" / "static"

IMPORT_PATTERN = re.compile(
    r"""(?:\b(?:import|export)\s+[\s\S]*?\bfrom\s*"""
    r"""|\bimport\s*)"""
    r"""["']([^"']+\.js)["']"""
)


def test_web_es_module_imports_are_relative_and_resolvable() -> None:
    root = STATIC_ROOT.resolve()
    modules = sorted(root.rglob("*.js"))
    assert modules, "No Web JavaScript modules found"

    imports_checked = 0

    for source in modules:
        content = source.read_text(encoding="utf-8")

        for specifier in IMPORT_PATTERN.findall(content):
            imports_checked += 1

            assert specifier.startswith("./"), f"{source}: non-relative import {specifier}"

            target = (source.parent / specifier).resolve()

            assert target.is_relative_to(root), f"{source}: import escapes static root: {specifier}"

            assert target.is_file(), f"{source}: missing import target: {specifier}"

    assert imports_checked > 0, "No ESM imports inspected"
