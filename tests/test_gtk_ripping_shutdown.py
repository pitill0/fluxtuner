from __future__ import annotations

from unittest.mock import Mock

import pytest

from fluxtuner.core.ripping import RippingError
from fluxtuner.core.ripping_service import RippingService


def test_gtk_ripping_shutdown_does_nothing_before_request() -> None:
    from fluxtuner.gui.gtk_ripping import RippingShutdown

    service = Mock(spec=RippingService)
    shutdown = RippingShutdown(service=service)

    assert shutdown.poll() is False
    assert shutdown.error is None
    service.stop.assert_not_called()
    service.wait.assert_not_called()


def test_gtk_ripping_shutdown_requests_stop_once_without_waiting() -> None:
    from fluxtuner.gui.gtk_ripping import RippingShutdown

    service = Mock(spec=RippingService)
    shutdown = RippingShutdown(service=service)

    shutdown.request()
    shutdown.request()

    service.stop.assert_called_once_with()
    service.wait.assert_not_called()
    assert shutdown.error is None


@pytest.mark.parametrize("state", ["completed", "stopped", "failed"])
def test_gtk_ripping_shutdown_waits_for_workers_despite_terminal_snapshot(state) -> None:
    from fluxtuner.gui.gtk_ripping import RippingShutdown

    service = Mock(spec=RippingService)
    service.snapshot.return_value = Mock(state=state)
    service.wait.side_effect = [False, True]
    shutdown = RippingShutdown(service=service)
    shutdown.request()

    assert shutdown.poll() is False
    assert shutdown.poll() is True

    assert service.wait.call_count == 2
    for invocation in service.wait.call_args_list:
        assert invocation.args == ()
        assert invocation.kwargs == {"timeout": 0}
    service.snapshot.assert_not_called()
    service.stop.assert_called_once_with()


def test_gtk_ripping_shutdown_contains_stop_error_and_still_tracks_workers() -> None:
    from fluxtuner.gui.gtk_ripping import RippingShutdown

    service = Mock(spec=RippingService)
    error = RippingError("Stop worker unavailable.")
    service.stop.side_effect = error
    service.wait.side_effect = [False, True]
    shutdown = RippingShutdown(service=service)

    shutdown.request()
    shutdown.request()

    assert shutdown.error is error
    assert shutdown.poll() is False
    assert shutdown.poll() is True
    assert shutdown.error is error
    service.stop.assert_called_once_with()
    for invocation in service.wait.call_args_list:
        assert invocation.kwargs == {"timeout": 0}


def test_gtk_ripping_shutdown_without_active_workers_is_ready() -> None:
    from fluxtuner.gui.gtk_ripping import RippingShutdown

    service = Mock(spec=RippingService)
    service.wait.return_value = True
    shutdown = RippingShutdown(service=service)

    shutdown.request()

    assert shutdown.poll() is True
    service.stop.assert_called_once_with()
    service.wait.assert_called_once_with(timeout=0)
