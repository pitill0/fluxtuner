"""Storage destination acceptance checks."""

from pathlib import Path

import pytest

from fluxtuner.core import storage_validation
from fluxtuner.core.storage_validation import validate_storage_destination


def test_valid_directory_is_writable_without_leaving_files(tmp_path: Path) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    validate_storage_destination(destination)

    assert list(destination.iterdir()) == []


def test_missing_directory_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="does not exist"):
        validate_storage_destination(tmp_path / "missing")

    assert not (tmp_path / "missing").exists()


def test_regular_file_is_rejected(tmp_path: Path) -> None:
    destination = tmp_path / "file"
    destination.write_text("original")

    with pytest.raises(ValueError, match="not a directory"):
        validate_storage_destination(destination)

    assert destination.read_text() == "original"


def test_relative_directory_is_rejected() -> None:
    with pytest.raises(ValueError, match="absolute"):
        validate_storage_destination(Path("relative-directory"))


def test_write_failure_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    destination = tmp_path / "destination"
    destination.mkdir()

    def deny_write(*_args: object, **_kwargs: object) -> None:
        raise PermissionError("Permission denied")

    monkeypatch.setattr(storage_validation.tempfile, "TemporaryFile", deny_write)

    with pytest.raises(OSError, match="not writable"):
        validate_storage_destination(destination)

    assert list(destination.iterdir()) == []
