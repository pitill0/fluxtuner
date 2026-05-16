from pathlib import Path

from fluxtuner import paths


def test_config_file_creates_config_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_dir = tmp_path / "config" / paths.APP_NAME
    monkeypatch.setattr(paths, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data" / paths.APP_NAME)
    monkeypatch.setattr(paths, "CACHE_DIR", tmp_path / "cache" / paths.APP_NAME)

    result = paths.config_file("config.json")

    assert result == config_dir / "config.json"
    assert config_dir.exists()


def test_data_file_creates_data_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_dir = tmp_path / "data" / paths.APP_NAME
    monkeypatch.setattr(paths, "CONFIG_DIR", tmp_path / "config" / paths.APP_NAME)
    monkeypatch.setattr(paths, "DATA_DIR", data_dir)
    monkeypatch.setattr(paths, "CACHE_DIR", tmp_path / "cache" / paths.APP_NAME)

    result = paths.data_file("favorites.json")

    assert result == data_dir / "favorites.json"
    assert data_dir.exists()


def test_cache_file_creates_cache_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cache_dir = tmp_path / "cache" / paths.APP_NAME
    monkeypatch.setattr(paths, "CONFIG_DIR", tmp_path / "config" / paths.APP_NAME)
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data" / paths.APP_NAME)
    monkeypatch.setattr(paths, "CACHE_DIR", cache_dir)

    result = paths.cache_file("search_cache.json")

    assert result == cache_dir / "search_cache.json"
    assert cache_dir.exists()


def test_migrate_legacy_file_copies_missing_new_file(tmp_path: Path) -> None:
    legacy_file = tmp_path / "legacy.json"
    new_file = tmp_path / "new" / "current.json"

    legacy_file.write_text('{"ok": true}', encoding="utf-8")

    paths.migrate_legacy_file(legacy_file, new_file)

    assert new_file.read_text(encoding="utf-8") == '{"ok": true}'
    assert legacy_file.exists()


def test_migrate_legacy_file_keeps_existing_new_file(tmp_path: Path) -> None:
    legacy_file = tmp_path / "legacy.json"
    new_file = tmp_path / "new" / "current.json"

    legacy_file.write_text("legacy", encoding="utf-8")
    new_file.parent.mkdir(parents=True)
    new_file.write_text("current", encoding="utf-8")

    paths.migrate_legacy_file(legacy_file, new_file)

    assert new_file.read_text(encoding="utf-8") == "current"


def test_migrate_legacy_file_ignores_missing_legacy_file(tmp_path: Path) -> None:
    legacy_file = tmp_path / "missing.json"
    new_file = tmp_path / "new" / "current.json"

    paths.migrate_legacy_file(legacy_file, new_file)

    assert not new_file.exists()
