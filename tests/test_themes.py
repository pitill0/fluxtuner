from pathlib import Path

from fluxtuner import themes


def test_list_themes_returns_default_when_theme_dir_is_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(themes, "THEMES_DIR", tmp_path / "missing")

    assert themes.list_themes() == [themes.DEFAULT_THEME]


def test_list_themes_returns_sorted_tcss_stems(
    tmp_path: Path,
    monkeypatch,
) -> None:
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    (themes_dir / "nord.tcss").write_text("", encoding="utf-8")
    (themes_dir / "default.tcss").write_text("", encoding="utf-8")
    (themes_dir / "README.md").write_text("", encoding="utf-8")

    monkeypatch.setattr(themes, "THEMES_DIR", themes_dir)

    assert themes.list_themes() == ["default", "nord"]


def test_get_theme_path_returns_requested_theme(
    tmp_path: Path,
    monkeypatch,
) -> None:
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    requested = themes_dir / "nord.tcss"
    requested.write_text("", encoding="utf-8")
    (themes_dir / "default.tcss").write_text("", encoding="utf-8")

    monkeypatch.setattr(themes, "THEMES_DIR", themes_dir)

    assert themes.get_theme_path("nord") == requested


def test_get_theme_path_falls_back_to_default_theme(
    tmp_path: Path,
    monkeypatch,
) -> None:
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    default_theme = themes_dir / "default.tcss"
    default_theme.write_text("", encoding="utf-8")

    monkeypatch.setattr(themes, "THEMES_DIR", themes_dir)

    assert themes.get_theme_path("missing") == default_theme
    assert themes.get_theme_path(None) == default_theme
    assert themes.get_theme_path("   ") == default_theme


def test_theme_exists_checks_tcss_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    themes_dir = tmp_path / "themes"
    themes_dir.mkdir()
    (themes_dir / "nord.tcss").write_text("", encoding="utf-8")

    monkeypatch.setattr(themes, "THEMES_DIR", themes_dir)

    assert themes.theme_exists("nord") is True
    assert themes.theme_exists("missing") is False
    assert themes.theme_exists(None) is False
