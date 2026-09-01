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
