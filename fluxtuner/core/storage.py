from __future__ import annotations

import json
import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import Any


def write_json_atomic(
    path: Path,
    data: Any,
    *,
    indent: int = 2,
    sort_keys: bool = False,
    ensure_ascii: bool = False,
) -> None:
    """Write JSON data atomically.

    The file is first written to a temporary file in the same directory and then
    atomically moved into place. This avoids leaving partially written JSON files
    if the process is interrupted during a write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    json_text = json.dumps(
        data,
        indent=indent,
        sort_keys=sort_keys,
        ensure_ascii=ensure_ascii,
    )

    temp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(json_text)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, path)
    except Exception:
        if temp_path is not None:
            with suppress(OSError):
                temp_path.unlink(missing_ok=True)
        raise
