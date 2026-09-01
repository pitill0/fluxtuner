"""GTK appearance preference helpers.

This module intentionally contains no PyGObject imports so appearance preference
normalization can be tested without an available GTK display or even GTK itself.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any


class AppearanceMode(StrEnum):
    """Configured GTK appearance mode."""

    SYSTEM = "system"
    DARK = "dark"
    LIGHT = "light"


GUI_DIR = Path(__file__).parent
THEMES_DIR = GUI_DIR / "themes"
COMMON_STYLESHEET = GUI_DIR / "style.css"


def normalize_appearance(value: Any) -> AppearanceMode:
    """Return a supported appearance mode, falling back safely to System."""

    if isinstance(value, AppearanceMode):
        return value

    if not isinstance(value, str):
        return AppearanceMode.SYSTEM

    normalized = value.strip().lower()
    try:
        return AppearanceMode(normalized)
    except ValueError:
        return AppearanceMode.SYSTEM


def palette_path(mode: AppearanceMode | str | None) -> Path | None:
    """Return the palette stylesheet for forced modes.

    System deliberately has no FluxTuner palette: GTK remains responsible for
    following the native platform/desktop appearance.
    """

    normalized = normalize_appearance(mode)
    if normalized is AppearanceMode.SYSTEM:
        return None
    return THEMES_DIR / f"{normalized.value}.css"
