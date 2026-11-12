from datetime import UTC, datetime

from fluxtuner.core import recordings


def test_recording_output_path_is_safe_and_deterministic(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recordings, "RECORDINGS_DIR", tmp_path)

    path = recordings.recording_output_path(
        "Rádio Música / 80's",
        timestamp=datetime(2026, 9, 2, 15, 55, 1, tzinfo=UTC),
        suffix="deadbeef",
    )

    assert path.parent == tmp_path
    assert path.name == "20260902-155501-radio-musica-80-s-deadbeef.mka"
    assert tmp_path.is_dir()


def test_recording_output_path_falls_back_for_non_ascii_name(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(recordings, "RECORDINGS_DIR", tmp_path)

    path = recordings.recording_output_path(
        "東京",
        timestamp=datetime(2026, 9, 2, 15, 55, 1, tzinfo=UTC),
        suffix="cafebabe",
    )

    assert path.name == "20260902-155501-station-cafebabe.mka"


def test_recording_output_path_uses_configured_directory(tmp_path, monkeypatch) -> None:
    from fluxtuner import config

    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")
    monkeypatch.setattr(recordings, "RECORDINGS_DIR", tmp_path / "default-recordings")

    custom = tmp_path / "custom-recordings"
    config.set_storage_directory("recordings_directory", custom)

    first = recordings.recording_output_path(
        "Radio",
        timestamp=datetime(2026, 9, 2, 15, 55, 1, tzinfo=UTC),
        suffix="11111111",
    )

    assert first.parent == custom
    assert custom.is_dir()
    assert not (tmp_path / "default-recordings").exists()

    config.set_storage_directory("recordings_directory", None)

    second = recordings.recording_output_path(
        "Radio",
        timestamp=datetime(2026, 9, 2, 15, 55, 2, tzinfo=UTC),
        suffix="22222222",
    )

    assert second.parent == tmp_path / "default-recordings"
    assert first.parent == custom
    assert second.parent.is_dir()


def test_recording_output_path_accepts_explicit_directory(tmp_path, monkeypatch) -> None:
    from fluxtuner import config

    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")

    configured = tmp_path / "configured"
    explicit = tmp_path / "explicit"

    config.set_storage_directory("recordings_directory", configured)

    output = recordings.recording_output_path(
        "Radio",
        timestamp=datetime(2026, 9, 2, 15, 55, 1, tzinfo=UTC),
        suffix="33333333",
        directory=explicit,
    )

    assert output.parent == explicit
    assert explicit.is_dir()
    assert not configured.exists()


def test_recording_directory_rejects_relative_explicit_path(tmp_path, monkeypatch) -> None:
    import pytest

    from fluxtuner import config

    monkeypatch.setattr(config, "CONFIG_FILE", tmp_path / "config.json")

    with pytest.raises(ValueError, match="absolute"):
        recordings.ensure_recordings_dir(
            directory=__import__("pathlib").Path("relative-recordings")
        )
