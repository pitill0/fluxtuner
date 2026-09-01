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


class GtkAppearanceManager:
    """Apply shared and forced GTK appearance stylesheets to one display."""

    def __init__(self, display: object) -> None:
        self._display = display
        self._common_provider: object | None = None
        self._palette_provider: object | None = None
        self._configured_mode = AppearanceMode.SYSTEM
        self._settings: object | Any = None
        self._settings_handler_id: int | None = None

    def _gtk(self):
        import gi

        gi.require_version("Gtk", "4.0")
        from gi.repository import Gtk

        return Gtk

    def _load_provider(self, path: Path):
        Gtk = self._gtk()
        provider = Gtk.CssProvider()
        provider.load_from_path(str(path))
        return provider

    def install_common_stylesheet(self) -> None:
        """Install the shared application stylesheet once."""

        if self._common_provider is not None or not COMMON_STYLESHEET.exists():
            return

        Gtk = self._gtk()
        provider = self._load_provider(COMMON_STYLESHEET)
        Gtk.StyleContext.add_provider_for_display(
            self._display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self._common_provider = provider

    def _system_palette_mode(self) -> AppearanceMode | None:
        Gtk = self._gtk()
        settings = Gtk.Settings.get_default()
        if settings is None:
            return None

        properties = {prop.name for prop in settings.list_properties()}
        if "gtk-interface-color-scheme" not in properties:
            return None

        scheme = settings.get_property("gtk-interface-color-scheme")
        if scheme == Gtk.InterfaceColorScheme.DARK:
            return AppearanceMode.DARK
        if scheme == Gtk.InterfaceColorScheme.LIGHT:
            return AppearanceMode.LIGHT
        return None

    def _ensure_system_listener(self) -> None:
        Gtk = self._gtk()
        settings = Gtk.Settings.get_default()
        if settings is None:
            return

        properties = {prop.name for prop in settings.list_properties()}
        if "gtk-interface-color-scheme" not in properties:
            return

        if self._settings is settings and self._settings_handler_id is not None:
            return

        self._disconnect_system_listener()
        self._settings = settings
        self._settings_handler_id = settings.connect(
            "notify::gtk-interface-color-scheme",
            self._on_system_color_scheme_changed,
        )

    def _disconnect_system_listener(self) -> None:
        if self._settings is not None and self._settings_handler_id is not None:
            settings: Any = self._settings
            settings.disconnect(self._settings_handler_id)

        self._settings = None
        self._settings_handler_id = None

    def _on_system_color_scheme_changed(
        self,
        _settings: object,
        _pspec: object,
    ) -> None:
        if self._configured_mode is AppearanceMode.SYSTEM:
            self._apply_effective_mode(self._system_palette_mode())

    def _apply_effective_mode(self, mode: AppearanceMode | None) -> None:
        Gtk = self._gtk()

        if self._palette_provider is not None:
            Gtk.StyleContext.remove_provider_for_display(
                self._display,
                self._palette_provider,
            )
            self._palette_provider = None

        if mode is None:
            return

        path = palette_path(mode)
        if path is None or not path.exists():
            return

        provider = self._load_provider(path)
        Gtk.StyleContext.add_provider_for_display(
            self._display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )
        self._palette_provider = provider

    def apply(self, mode: AppearanceMode | str | None) -> AppearanceMode:
        """Apply one appearance mode and return the normalized mode."""

        normalized = normalize_appearance(mode)
        self._configured_mode = normalized
        self.install_common_stylesheet()

        if normalized is AppearanceMode.SYSTEM:
            self._ensure_system_listener()
            self._apply_effective_mode(self._system_palette_mode())
            return normalized

        self._disconnect_system_listener()
        self._apply_effective_mode(normalized)
        return normalized
