from __future__ import annotations

import importlib
from pathlib import Path


def test_data_dir_uses_fluxtuner_data_dir(
    monkeypatch,
    tmp_path: Path,
) -> None:
    custom_data_dir = tmp_path / "custom-data"

    monkeypatch.setenv("FLUXTUNER_DATA_DIR", str(custom_data_dir))
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)

    import fluxtuner.paths as paths

    reloaded_paths = importlib.reload(paths)

    assert custom_data_dir == reloaded_paths.DATA_DIR
    assert reloaded_paths.data_file("history.json") == custom_data_dir / "history.json"
    assert custom_data_dir.exists()


def test_data_dir_falls_back_to_xdg_data_home(
    monkeypatch,
    tmp_path: Path,
) -> None:
    xdg_data_home = tmp_path / "xdg-data"

    monkeypatch.delenv("FLUXTUNER_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(xdg_data_home))

    import fluxtuner.paths as paths

    reloaded_paths = importlib.reload(paths)

    assert xdg_data_home / "fluxtuner" == reloaded_paths.DATA_DIR
    assert reloaded_paths.data_file("favorites.json") == (
        xdg_data_home / "fluxtuner" / "favorites.json"
    )


def test_config_and_cache_keep_xdg_locations_when_data_dir_is_custom(
    monkeypatch,
    tmp_path: Path,
) -> None:
    custom_data_dir = tmp_path / "data"
    custom_config_home = tmp_path / "config"
    custom_cache_home = tmp_path / "cache"

    monkeypatch.setenv("FLUXTUNER_DATA_DIR", str(custom_data_dir))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(custom_config_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(custom_cache_home))

    import fluxtuner.paths as paths

    reloaded_paths = importlib.reload(paths)

    assert custom_data_dir == reloaded_paths.DATA_DIR
    assert custom_config_home / "fluxtuner" == reloaded_paths.CONFIG_DIR
    assert custom_cache_home / "fluxtuner" == reloaded_paths.CACHE_DIR
