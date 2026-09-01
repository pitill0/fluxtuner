from pathlib import Path

import pytest

from fluxtuner.gui.appearance import (
    COMMON_STYLESHEET,
    THEMES_DIR,
    AppearanceMode,
    normalize_appearance,
    palette_path,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, AppearanceMode.SYSTEM),
        ("", AppearanceMode.SYSTEM),
        ("system", AppearanceMode.SYSTEM),
        (" SYSTEM ", AppearanceMode.SYSTEM),
        ("dark", AppearanceMode.DARK),
        ("DARK", AppearanceMode.DARK),
        (" light ", AppearanceMode.LIGHT),
        ("invalid", AppearanceMode.SYSTEM),
        (123, AppearanceMode.SYSTEM),
        (AppearanceMode.DARK, AppearanceMode.DARK),
    ],
)
def test_normalize_appearance(value: object, expected: AppearanceMode) -> None:
    assert normalize_appearance(value) is expected


def test_system_has_no_flux_tuner_palette() -> None:
    assert palette_path(AppearanceMode.SYSTEM) is None


@pytest.mark.parametrize(
    ("mode", "filename"),
    [
        (AppearanceMode.DARK, "dark.css"),
        (AppearanceMode.LIGHT, "light.css"),
        ("dark", "dark.css"),
        ("light", "light.css"),
    ],
)
def test_forced_appearance_resolves_palette_path(
    mode: AppearanceMode | str,
    filename: str,
) -> None:
    assert palette_path(mode) == THEMES_DIR / filename


def test_common_stylesheet_location_is_stable() -> None:
    assert Path(__file__).parents[1] / "fluxtuner" / "gui" / "style.css" == COMMON_STYLESHEET


class FakeProvider:
    loaded_paths: list[str] = []

    def load_from_path(self, path: str) -> None:
        self.loaded_paths.append(path)


class FakeStyleContext:
    added: list[tuple[object, object, int]] = []
    removed: list[tuple[object, object]] = []

    @classmethod
    def add_provider_for_display(cls, display: object, provider: object, priority: int) -> None:
        cls.added.append((display, provider, priority))

    @classmethod
    def remove_provider_for_display(cls, display: object, provider: object) -> None:
        cls.removed.append((display, provider))


class FakeGtk:
    CssProvider = FakeProvider
    StyleContext = FakeStyleContext
    STYLE_PROVIDER_PRIORITY_APPLICATION = 600


def reset_fake_gtk() -> None:
    FakeProvider.loaded_paths = []
    FakeStyleContext.added = []
    FakeStyleContext.removed = []


def test_manager_system_installs_only_common_stylesheet(monkeypatch) -> None:
    from fluxtuner.gui.appearance import GtkAppearanceManager

    reset_fake_gtk()
    display = object()
    manager = GtkAppearanceManager(display)
    monkeypatch.setattr(manager, "_gtk", lambda: FakeGtk)

    assert AppearanceMode.SYSTEM is manager.apply(AppearanceMode.SYSTEM)
    assert [str(COMMON_STYLESHEET)] == FakeProvider.loaded_paths
    assert len(FakeStyleContext.added) == 1
    assert FakeStyleContext.removed == []


def test_manager_switches_forced_palette_at_runtime(monkeypatch) -> None:
    from fluxtuner.gui.appearance import GtkAppearanceManager

    reset_fake_gtk()
    display = object()
    manager = GtkAppearanceManager(display)
    monkeypatch.setattr(manager, "_gtk", lambda: FakeGtk)

    assert AppearanceMode.DARK is manager.apply(AppearanceMode.DARK)
    dark_provider = FakeStyleContext.added[-1][1]

    assert AppearanceMode.LIGHT is manager.apply(AppearanceMode.LIGHT)

    assert [(display, dark_provider)] == FakeStyleContext.removed
    assert [
        str(COMMON_STYLESHEET),
        str(THEMES_DIR / "dark.css"),
        str(THEMES_DIR / "light.css"),
    ] == FakeProvider.loaded_paths


def test_manager_switch_to_system_removes_forced_palette(monkeypatch) -> None:
    from fluxtuner.gui.appearance import GtkAppearanceManager

    reset_fake_gtk()
    display = object()
    manager = GtkAppearanceManager(display)
    monkeypatch.setattr(manager, "_gtk", lambda: FakeGtk)

    manager.apply(AppearanceMode.DARK)
    dark_provider = FakeStyleContext.added[-1][1]

    assert AppearanceMode.SYSTEM is manager.apply(AppearanceMode.SYSTEM)
    assert [(display, dark_provider)] == FakeStyleContext.removed
    assert [
        str(COMMON_STYLESHEET),
        str(THEMES_DIR / "dark.css"),
    ]
