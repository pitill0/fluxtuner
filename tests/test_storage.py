import json

import pytest

from fluxtuner.core.storage import write_json_atomic


def test_write_json_atomic_creates_parent_directory(tmp_path) -> None:
    target = tmp_path / "nested" / "data.json"

    write_json_atomic(target, {"ok": True})

    assert target.exists()
    assert json.loads(target.read_text(encoding="utf-8")) == {"ok": True}


def test_write_json_atomic_replaces_existing_file(tmp_path) -> None:
    target = tmp_path / "data.json"
    target.write_text('{"old": true}', encoding="utf-8")

    write_json_atomic(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"new": True}


def test_write_json_atomic_preserves_existing_file_when_dump_fails(tmp_path) -> None:
    target = tmp_path / "data.json"
    target.write_text('{"old": true}', encoding="utf-8")

    with pytest.raises(TypeError):
        write_json_atomic(target, {"bad": object()})

    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}


def test_write_json_atomic_removes_temp_file_when_replace_fails(tmp_path, monkeypatch) -> None:
    target = tmp_path / "data.json"
    target.write_text('{"old": true}', encoding="utf-8")

    def fake_replace(_source, _destination) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr("os.replace", fake_replace)

    with pytest.raises(OSError):
        write_json_atomic(target, {"new": True})

    assert json.loads(target.read_text(encoding="utf-8")) == {"old": True}
    assert list(tmp_path.glob(".data.json.*.tmp")) == []
