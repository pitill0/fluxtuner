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
