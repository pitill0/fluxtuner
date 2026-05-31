import json
import logging
from pathlib import Path

from fluxtuner import config


def patch_config_file(tmp_path: Path, monkeypatch) -> Path:
    config_file = tmp_path / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)
    return config_file


def test_get_playback_state_normalizes_volume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_config_file(tmp_path, monkeypatch)

    config.save_config(
        {
            "playback": {
                "volume": 250,
                "muted": 1,
                "last_station": {"name": "Test Radio"},
            }
        }
    )

    state = config.get_playback_state()

    assert state["volume"] == 100
    assert state["muted"] is True
    assert state["last_station"] == {"name": "Test Radio"}


def test_save_playback_state_clamps_volume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_config_file(tmp_path, monkeypatch)

    config.save_playback_state(volume=-10, muted=False)

    state = config.get_playback_state()

    assert state["volume"] == 0
    assert state["muted"] is False


def test_get_playback_state_ignores_invalid_playback_value(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_config_file(tmp_path, monkeypatch)

    config.save_config({"playback": "invalid"})

    assert config.get_playback_state() == {}


def test_get_playback_state_ignores_invalid_volume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_config_file(tmp_path, monkeypatch)

    config.save_config(
        {
            "playback": {
                "volume": "loud",
                "muted": False,
            }
        }
    )

    state = config.get_playback_state()

    assert state["volume"] is None
    assert state["muted"] is False


def test_load_config_logs_invalid_json(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    config_file = tmp_path / "config.json"
    config_file.write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr(config, "CONFIG_FILE", config_file)

    with caplog.at_level(logging.WARNING):
        assert config.load_config() == config.default_config()

    assert "Invalid config JSON" in caplog.text


def test_load_config_returns_defaults_for_missing_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_config_file(tmp_path, monkeypatch)

    assert config.load_config() == config.default_config()


def test_load_config_returns_defaults_for_invalid_json(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = patch_config_file(tmp_path, monkeypatch)
    config_file.write_text("{not-json", encoding="utf-8")

    assert config.load_config() == config.default_config()


def test_load_config_merges_saved_values_with_defaults(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = patch_config_file(tmp_path, monkeypatch)
    config_file.write_text(json.dumps({"theme": "nord"}), encoding="utf-8")

    loaded = config.load_config()

    assert loaded["theme"] == "nord"
    assert loaded["playback"] == {
        "last_station": None,
        "volume": None,
        "muted": False,
    }


def test_get_and_set_config_value(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_config_file(tmp_path, monkeypatch)

    assert config.get_config_value("theme") == "default"
    assert config.get_config_value("missing", "fallback") == "fallback"

    config.set_config_value("theme", "dracula")

    assert config.get_config_value("theme") == "dracula"


def test_save_playback_state_preserves_omitted_values(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_config_file(tmp_path, monkeypatch)

    config.save_playback_state(
        last_station={"name": "Test Radio", "url": "https://example.com/stream"},
        volume=30,
        muted=True,
    )
    config.save_playback_state(volume=50)

    state = config.get_playback_state()

    assert state == {
        "last_station": {"name": "Test Radio", "url": "https://example.com/stream"},
        "volume": 50,
        "muted": True,
    }


def test_save_config_creates_parent_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "nested" / "config.json"
    monkeypatch.setattr(config, "CONFIG_FILE", config_file)

    config.save_config(config.default_config())

    assert config_file.exists()


def test_save_playback_state_ignores_invalid_volume_without_overwriting_existing_value(
    tmp_path: Path,
    monkeypatch,
) -> None:
    patch_config_file(tmp_path, monkeypatch)

    config.save_playback_state(volume=35, muted=True)
    config.save_playback_state(volume="loud")  # type: ignore[arg-type]

    state = config.get_playback_state()

    assert state["volume"] == 35
    assert state["muted"] is True
