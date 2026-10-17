from __future__ import annotations

import threading
from collections.abc import Callable
from queue import Queue
from unittest.mock import Mock

import pytest

from fluxtuner.core.ripping import RippingAvailability


@pytest.mark.parametrize(
    "availability",
    [
        RippingAvailability(True),
        RippingAvailability(False, "Brynse is not installed."),
    ],
)
def test_gtk_ripping_probe_runs_in_worker_and_dispatches_result(
    availability: RippingAvailability,
) -> None:
    from fluxtuner.gui.gtk_ripping import start_ripping_availability_probe

    main_thread = threading.get_ident()
    entered = threading.Event()
    release = threading.Event()
    checked_from: list[int] = []
    pending: Queue[tuple[int, Callable[[], bool]]] = Queue()
    delivered: list[tuple[int, RippingAvailability]] = []

    def check() -> RippingAvailability:
        checked_from.append(threading.get_ident())
        entered.set()
        assert release.wait(5)
        return availability

    def dispatch(callback: Callable[[], bool]) -> None:
        pending.put((threading.get_ident(), callback))

    def accept(value: RippingAvailability) -> None:
        delivered.append((threading.get_ident(), value))

    worker = start_ripping_availability_probe(
        check_availability=check,
        dispatch=dispatch,
        on_result=accept,
    )
    try:
        assert entered.wait(5)
        assert worker.is_alive()
        assert delivered == []

        release.set()
        dispatched_from, callback = pending.get(timeout=5)
        worker.join(timeout=5)

        assert not worker.is_alive()
        assert checked_from[0] != main_thread
        assert dispatched_from == checked_from[0]
        assert delivered == []

        assert callback() is False
        assert delivered == [(main_thread, availability)]
    finally:
        release.set()
        worker.join(timeout=5)


def test_gtk_ripping_probe_dispatches_contained_failure() -> None:
    from fluxtuner.gui.gtk_ripping import start_ripping_availability_probe

    pending: Queue[Callable[[], bool]] = Queue()
    accept = Mock()

    def check() -> RippingAvailability:
        raise RuntimeError("broken dependency")

    worker = start_ripping_availability_probe(
        check_availability=check,
        dispatch=pending.put,
        on_result=accept,
    )
    try:
        callback = pending.get(timeout=5)
        worker.join(timeout=5)

        assert not worker.is_alive()
        accept.assert_not_called()
        assert callback() is False
        accept.assert_called_once_with(
            RippingAvailability(
                False,
                "Could not check ripping availability: broken dependency",
            )
        )
    finally:
        worker.join(timeout=5)
