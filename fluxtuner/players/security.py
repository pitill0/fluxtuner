from __future__ import annotations

import shutil
from urllib.parse import urlparse

from fluxtuner.players.base import PlayerError

SUPPORTED_STREAM_SCHEMES = {"http", "https"}


def resolve_executable(name: str) -> str:
    """Return the absolute executable path for a player binary."""
    executable = shutil.which(name)
    if not executable:
        raise PlayerError(
            f"{name} is required but was not found in PATH. Please install {name} and try again."
        )
    return executable


def is_supported_stream_url(url: str | None) -> bool:
    """Return True when a stream URL is safe to pass to external players."""
    if not url:
        return False

    clean_url = str(url).strip()
    parsed = urlparse(clean_url)

    return parsed.scheme in SUPPORTED_STREAM_SCHEMES and bool(parsed.netloc)


def validate_stream_url(url: str | None) -> str:
    """Return a normalized stream URL or raise PlayerError."""
    clean_url = str(url or "").strip()

    if not is_supported_stream_url(clean_url):
        raise PlayerError("Unsupported or invalid stream URL.")

    return clean_url
