from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from textual.app import App
from textual.widgets import Button, Footer, Header, Input, ListView, Static

from fluxtuner.themes import get_theme_path

_RULE_RE = re.compile(r"(?P<selector>[^{}]+)\{(?P<body>[^{}]*)\}", re.MULTILINE | re.DOTALL)
_DECL_RE = re.compile(r"(?P<name>[a-zA-Z_-]+)\s*:\s*(?P<value>[^;]+);")

SUPPORTED_SELECTORS = {
    "Screen",
    "Header",
    "Footer",
    "Button",
    "#toolbar",
    "#filters",
    "#query",
    "#country-filter",
    "#bitrate-filter",
    ".toolbar-button",
    ".side-button",
    ".filter-label",
    "#stations",
    "#side-panel",
    "#mode-title",
    "#now-playing",
    "#details",
    "#status",
}

COLOR_PROPS = {"background", "color"}


def parse_tcss(path: Path) -> dict[str, dict[str, str]]:
    """Parse a small, practical subset of TCSS used by FluxTuner themes.

    This is intentionally not a full CSS parser. It extracts top-level selector
    blocks and simple `property: value;` declarations so themes can be re-applied
    at runtime without relying on Textual's dev-only CSS watcher.
    """
    css = path.read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)

    rules: dict[str, dict[str, str]] = {}
    for match in _RULE_RE.finditer(css):
        selector = " ".join(match.group("selector").strip().split())
        if selector not in SUPPORTED_SELECTORS:
            continue
        declarations: dict[str, str] = {}
        for decl in _DECL_RE.finditer(match.group("body")):
            value = decl.group("value").strip()
            if value.startswith("$"):
                # Runtime theming needs concrete values. Textual may understand
                # variables at startup, but we cannot reliably resolve them here.
                continue
            declarations[decl.group("name").strip()] = value
        if declarations:
            rules[selector] = declarations
    return rules


def _split_box(value: str) -> tuple[int, int, int, int] | None:
    try:
        parts = [int(part) for part in value.split()]
    except ValueError:
        return None

    if len(parts) == 1:
        top = right = bottom = left = parts[0]
    elif len(parts) == 2:
        top = bottom = parts[0]
        right = left = parts[1]
    elif len(parts) == 4:
        top, right, bottom, left = parts
    else:
        return None
    return (top, right, bottom, left)


def _parse_border(value: str) -> tuple[str, str] | None:
    parts = value.split()
    if len(parts) < 2:
        return None
    return (parts[0], parts[1])


def _set_if_supported(styles: Any, attr: str, value: Any) -> None:
    try:
        setattr(styles, attr, value)
    except Exception:
        # Different Textual versions may support a slightly different style set.
        pass


def _apply_declarations(widget: Any, declarations: dict[str, str]) -> None:
    styles = widget.styles
    for prop, value in declarations.items():
        if prop in COLOR_PROPS:
            _set_if_supported(styles, prop.replace("-", "_"), value)
        elif prop == "border":
            border = _parse_border(value)
            if border:
                _set_if_supported(styles, "border", border)
        elif prop == "padding":
            spacing = _split_box(value)
            if spacing:
                _set_if_supported(styles, "padding", spacing)
        elif prop == "margin":
            spacing = _split_box(value)
            if spacing:
                _set_if_supported(styles, "margin", spacing)
        elif prop == "margin-left":
            try:
                left = int(value)
            except ValueError:
                continue
            current = getattr(styles, "margin", None)
            if current is not None:
                try:
                    _set_if_supported(styles, "margin", (current.top, current.right, current.bottom, left))
                except Exception:
                    _set_if_supported(styles, "margin", (0, 0, 0, left))
        elif prop == "text-style":
            _set_if_supported(styles, "text_style", value)
        elif prop in {"height", "width", "min-width", "max-width"}:
            parsed_value: Any = value
            if value.isdigit():
                parsed_value = int(value)
            _set_if_supported(styles, prop.replace("-", "_"), parsed_value)


def apply_theme_runtime(app: App[Any], theme_name: str) -> Path:
    """Apply a FluxTuner theme to already-mounted widgets.

    Returns the path that was loaded. Raises exceptions for unreadable files so
    the caller can surface a useful status message.
    """
    path = get_theme_path(theme_name)
    rules = parse_tcss(path)

    if "Screen" in rules:
        _apply_declarations(app.screen, rules["Screen"])

    selector_map = {
        "Header": Header,
        "Footer": Footer,
        "Button": Button,
        "#toolbar": "#toolbar",
        "#filters": "#filters",
        "#query": "#query",
        "#country-filter": "#country-filter",
        "#bitrate-filter": "#bitrate-filter",
        ".toolbar-button": ".toolbar-button",
        ".side-button": ".side-button",
        ".filter-label": ".filter-label",
        "#stations": "#stations",
        "#side-panel": "#side-panel",
        "#mode-title": "#mode-title",
        "#now-playing": "#now-playing",
        "#details": "#details",
        "#status": "#status",
    }

    for selector, target in selector_map.items():
        declarations = rules.get(selector)
        if not declarations:
            continue
        try:
            widgets = app.query(target) if isinstance(target, str) else app.query(target)
            for widget in widgets:
                _apply_declarations(widget, declarations)
        except Exception:
            continue

    app.refresh(layout=True)
    return path
