"""Validate user-selected storage directories without retaining files."""

from __future__ import annotations

import tempfile
from pathlib import Path


def validate_storage_destination(directory: Path) -> None:
    """Require an existing, writable local directory.

    A temporary file tests actual write access and is closed immediately.
    No persistent file or directory is created by this validation.
    """
    if not directory.is_absolute():
        raise ValueError("Storage directory must be absolute")

    if not directory.exists():
        raise ValueError("Storage destination does not exist")

    if not directory.is_dir():
        raise ValueError("Storage destination is not a directory")

    try:
        with tempfile.TemporaryFile(dir=directory):
            pass
    except OSError as exc:
        raise OSError(f"Storage destination is not writable: {directory}: {exc}") from exc
