from fluxtuner import tui_themes


def test_theme_status_marks_active_theme() -> None:
    assert (
        tui_themes.theme_status(
            "default",
            active_theme="default",
            previewed_theme=None,
        )
        == "active"
    )


def test_theme_status_marks_previewed_theme() -> None:
    assert (
        tui_themes.theme_status(
            "solarized",
            active_theme="default",
            previewed_theme="solarized",
        )
        == "preview"
    )


def test_theme_status_marks_available_theme() -> None:
    assert (
        tui_themes.theme_status(
            "arcane",
            active_theme="default",
            previewed_theme="solarized",
        )
        == "available"
    )


def test_theme_saved_status_message() -> None:
    assert tui_themes.theme_saved_status_message("default") == "Saved default theme: default"


def test_theme_preview_status_message() -> None:
    assert tui_themes.theme_preview_status_message("default") == (
        "Theme preview: default. Press Enter to apply or y to save the active theme."
    )


def test_theme_apply_status_message_for_applied_theme() -> None:
    assert tui_themes.theme_apply_status_message("default", saved=False) == "Theme applied: default"


def test_theme_apply_status_message_for_saved_theme() -> None:
    assert tui_themes.theme_apply_status_message("default", saved=True) == "Theme saved: default"


def test_theme_missing_status_message() -> None:
    assert tui_themes.theme_missing_status_message("missing") == "Theme not found: missing"


def test_theme_failure_messages() -> None:
    error = RuntimeError("boom")

    assert tui_themes.theme_load_failed_message(error) == "Theme load failed: boom"
    assert tui_themes.theme_preview_failed_message(error) == "Theme preview failed: boom"
    assert tui_themes.theme_apply_failed_message(error) == "Theme apply failed: boom"


def test_theme_disabled_action_messages() -> None:
    assert "not deleted" in tui_themes.theme_remove_disabled_message()
    assert "preview temporarily" in tui_themes.theme_add_disabled_message()
    assert "Random favorite playback is disabled" in (
        tui_themes.random_favorite_disabled_in_themes_message()
    )
