# SPDX-License-Identifier: MIT

from pathlib import Path

import pytest

from fluxtuner.core import db
from fluxtuner.core.recording import RecordingError, RecordingSession
from fluxtuner.core.recordings import (
    SqliteRecordingStore,
    add_recording,
    delete_recording,
    ensure_recordings_dir,
    get_recording,
    list_recordings,
)


def _add_sample_recording(
    conn,
    tmp_path: Path,
    *,
    station_name: str = "Flux FM",
    started_at: str = "2026-09-02T12:00:00+00:00",
    file_name: str = "recording.mka",
) -> int:
    return add_recording(
        conn,
        station_name=station_name,
        source_url="https://radio.example/stream",
        file_path=tmp_path / file_name,
        started_at=started_at,
        stopped_at="2026-09-02T12:00:20+00:00",
        duration_seconds=20.0,
        file_size=640_000,
    )


def test_ensure_recordings_dir_creates_directory(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from fluxtuner.core import recordings

    target = tmp_path / "recordings"
    monkeypatch.setattr(recordings, "RECORDINGS_DIR", target)

    assert ensure_recordings_dir() == target
    assert target.is_dir()


def test_add_and_get_recording(tmp_path: Path) -> None:
    db_file = tmp_path / "fluxtuner.db"
    db.init_db(db_file)

    with db.connect(db_file) as conn:
        recording_id = _add_sample_recording(conn, tmp_path)
        conn.commit()

        recording = get_recording(conn, recording_id)

    assert recording is not None
    assert recording["station_name"] == "Flux FM"
    assert recording["source_url"] == "https://radio.example/stream"
    assert recording["file_path"] == str(tmp_path / "recording.mka")
    assert recording["duration_seconds"] == 20.0
    assert recording["file_size"] == 640_000
    assert recording["status"] == "completed"


def test_list_recordings_returns_newest_first(tmp_path: Path) -> None:
    db_file = tmp_path / "fluxtuner.db"
    db.init_db(db_file)

    with db.connect(db_file) as conn:
        _add_sample_recording(
            conn,
            tmp_path,
            station_name="Older",
            started_at="2026-09-02T11:00:00+00:00",
            file_name="older.mka",
        )
        _add_sample_recording(
            conn,
            tmp_path,
            station_name="Newer",
            started_at="2026-09-02T12:00:00+00:00",
            file_name="newer.mka",
        )
        conn.commit()

        recordings = list_recordings(conn)

    assert [item["station_name"] for item in recordings] == ["Newer", "Older"]


def test_recordings_are_profile_scoped(tmp_path: Path) -> None:
    db_file = tmp_path / "fluxtuner.db"
    db.init_db(db_file)

    with db.connect(db_file) as conn:
        default_user_id = db.ensure_default_user(conn)
        other_profile_id = db.get_or_create_profile(
            conn,
            "other",
            user_id=default_user_id,
        )

        default_id = _add_sample_recording(conn, tmp_path, station_name="Default")
        other_id = add_recording(
            conn,
            station_name="Other",
            source_url="https://radio.example/other",
            file_path=tmp_path / "other.mka",
            started_at="2026-09-02T13:00:00+00:00",
            stopped_at="2026-09-02T13:00:20+00:00",
            duration_seconds=20.0,
            file_size=123,
            profile_id=other_profile_id,
        )
        conn.commit()

        assert get_recording(conn, other_id) is None
        assert get_recording(conn, default_id, profile_id=other_profile_id) is None
        assert [item["id"] for item in list_recordings(conn)] == [default_id]
        assert [item["id"] for item in list_recordings(conn, profile_id=other_profile_id)] == [
            other_id
        ]


def test_delete_recording_removes_metadata_only(tmp_path: Path) -> None:
    db_file = tmp_path / "fluxtuner.db"
    db.init_db(db_file)
    media_file = tmp_path / "recording.mka"
    media_file.write_bytes(b"media")

    with db.connect(db_file) as conn:
        recording_id = add_recording(
            conn,
            station_name="Flux FM",
            source_url="https://radio.example/stream",
            file_path=media_file,
            started_at="2026-09-02T12:00:00+00:00",
            stopped_at="2026-09-02T12:00:20+00:00",
            duration_seconds=20.0,
            file_size=media_file.stat().st_size,
        )
        conn.commit()

        assert delete_recording(conn, recording_id) is True
        conn.commit()
        assert get_recording(conn, recording_id) is None

    assert media_file.exists()


@pytest.mark.parametrize(
    ("duration_seconds", "file_size", "message"),
    [
        (-1.0, 1, "duration"),
        (1.0, -1, "file size"),
    ],
)
def test_add_recording_rejects_negative_values(
    tmp_path: Path,
    duration_seconds: float,
    file_size: int,
    message: str,
) -> None:
    db_file = tmp_path / "fluxtuner.db"
    db.init_db(db_file)

    with db.connect(db_file) as conn, pytest.raises(ValueError, match=message):
        add_recording(
            conn,
            station_name="Flux FM",
            source_url="https://radio.example/stream",
            file_path=tmp_path / "recording.mka",
            started_at="2026-09-02T12:00:00+00:00",
            stopped_at="2026-09-02T12:00:20+00:00",
            duration_seconds=duration_seconds,
            file_size=file_size,
        )


def test_sqlite_recording_store_persists_completed_session(tmp_path: Path) -> None:
    db_file = tmp_path / "fluxtuner.db"
    media_file = tmp_path / "recording.mka"
    media_file.write_bytes(b"recorded-media")

    store = SqliteRecordingStore(db_path=db_file)
    session = RecordingSession(
        station_name="Flux FM",
        source_url="https://radio.example/stream",
        output_path=media_file,
        started_at="2026-09-02T12:00:00+00:00",
        stopped_at="2026-09-02T12:00:20.500000+00:00",
    )

    recording_id = store.save(session)

    with db.connect(db_file) as conn:
        recording = get_recording(conn, recording_id)

    assert recording is not None
    assert recording["station_name"] == "Flux FM"
    assert recording["duration_seconds"] == 20.5
    assert recording["file_size"] == len(b"recorded-media")
    assert recording["file_path"] == str(media_file)


def test_sqlite_recording_store_rejects_active_session(tmp_path: Path) -> None:
    store = SqliteRecordingStore(db_path=tmp_path / "fluxtuner.db")
    session = RecordingSession(
        station_name="Flux FM",
        source_url="https://radio.example/stream",
        output_path=tmp_path / "recording.mka",
        started_at="2026-09-02T12:00:00+00:00",
    )

    with pytest.raises(RecordingError, match="active recording"):
        store.save(session)


def test_sqlite_recording_store_rejects_missing_output_file(tmp_path: Path) -> None:
    store = SqliteRecordingStore(db_path=tmp_path / "fluxtuner.db")
    session = RecordingSession(
        station_name="Flux FM",
        source_url="https://radio.example/stream",
        output_path=tmp_path / "missing.mka",
        started_at="2026-09-02T12:00:00+00:00",
        stopped_at="2026-09-02T12:00:20+00:00",
    )

    with pytest.raises(RecordingError, match="does not exist"):
        store.save(session)
