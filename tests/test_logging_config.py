import logging

from fluxtuner.logging_config import configure_logging, get_logger


def test_configure_logging_defaults_to_warning(monkeypatch) -> None:
    monkeypatch.delenv("FLUXTUNER_DEBUG", raising=False)

    configure_logging()

    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_uses_debug_when_verbose(monkeypatch) -> None:
    monkeypatch.delenv("FLUXTUNER_DEBUG", raising=False)

    configure_logging(verbose=True)

    assert logging.getLogger().level == logging.DEBUG


def test_configure_logging_uses_debug_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("FLUXTUNER_DEBUG", "1")

    configure_logging()

    assert logging.getLogger().level == logging.DEBUG


def test_get_logger_returns_named_logger() -> None:
    logger = get_logger("fluxtuner.test")

    assert logger.name == "fluxtuner.test"
