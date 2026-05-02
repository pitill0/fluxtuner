from __future__ import annotations

from pathlib import Path

THEMES_DIR = Path(__file__).parent / "themes"
DEFAULT_THEME = "default"


def list_themes() -> list[str]:
    """Return available theme names from the bundled themes directory."""
    if not THEMES_DIR.exists():
        return [DEFAULT_THEME]
    return sorted(path.stem for path in THEMES_DIR.glob("*.tcss"))


def get_theme_path(theme_name: str | None) -> Path:
    """Return the requested theme path, falling back to the default theme."""
    requested = (theme_name or DEFAULT_THEME).strip() or DEFAULT_THEME
    theme_path = THEMES_DIR / f"{requested}.tcss"
    if theme_path.exists():
        return theme_path
    return THEMES_DIR / f"{DEFAULT_THEME}.tcss"


def theme_exists(theme_name: str | None) -> bool:
    """Return True when the requested theme exists."""
    if not theme_name:
        return False
    return (THEMES_DIR / f"{theme_name}.tcss").exists()
