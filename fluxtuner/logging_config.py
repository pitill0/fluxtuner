from __future__ import annotations

import logging
import os

DEFAULT_LOG_FORMAT = "%(levelname)s:%(name)s:%(message)s"

_DEBUG_VALUES = {"1", "true", "yes", "on"}


def _env_debug_enabled() -> bool:
    return os.getenv("FLUXTUNER_DEBUG", "").strip().lower() in _DEBUG_VALUES


def configure_logging(*, verbose: bool = False) -> None:
    """Configure application logging.

    By default FluxTuner only emits warnings and errors. Debug logging can be
    enabled with the CLI --verbose flag or with FLUXTUNER_DEBUG=1.
    """
    level = logging.DEBUG if verbose or _env_debug_enabled() else logging.WARNING

    logging.basicConfig(
        level=level,
        format=DEFAULT_LOG_FORMAT,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger."""
    return logging.getLogger(name)
