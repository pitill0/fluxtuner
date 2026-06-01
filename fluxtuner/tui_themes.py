from __future__ import annotations


def theme_status(
    theme_name: str,
    *,
    active_theme: str,
    previewed_theme: str | None,
) -> str:
    if theme_name == active_theme:
        return "active"
    if theme_name == previewed_theme:
        return "preview"
    return "available"


def theme_saved_status_message(theme_name: str) -> str:
    return f"Saved default theme: {theme_name}"


def theme_preview_status_message(theme_name: str) -> str:
    return f"Theme preview: {theme_name}. Press Enter to apply or y to save the active theme."


def theme_apply_status_message(theme_name: str, *, saved: bool) -> str:
    suffix = "saved" if saved else "applied"
    return f"Theme {suffix}: {theme_name}"


def theme_missing_status_message(theme_name: str) -> str:
    return f"Theme not found: {theme_name}"


def theme_load_failed_message(error: Exception) -> str:
    return f"Theme load failed: {error}"


def theme_preview_failed_message(error: Exception) -> str:
    return f"Theme preview failed: {error}"


def theme_apply_failed_message(error: Exception) -> str:
    return f"Theme apply failed: {error}"


def theme_remove_disabled_message() -> str:
    return "Theme files are not deleted from FluxTuner. Remove .tcss files manually if needed."


def theme_add_disabled_message() -> str:
    return (
        "Use ↑/↓ to preview temporarily, Enter to apply, or y to save the active theme as default."
    )


def random_favorite_disabled_in_themes_message() -> str:
    return "Random favorite playback is disabled while browsing themes. Press f, h or search first."
