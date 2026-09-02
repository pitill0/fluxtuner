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
