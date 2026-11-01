"""GTK-independent ripping actions and UI-loop monitoring ownership."""

from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fluxtuner.core.ripping import RippingAvailability
from fluxtuner.core.ripping_service import RippingService
from fluxtuner.gui.gtk_ripping import (
    coordinate_ripping_start,
    coordinate_ripping_stop,
    ripping_status,
    start_ripping_availability_probe,
)


class RippingController:
    """Own capability delivery and one UI timer, sharing the authoritative service."""

    def __init__(
        self,
        *,
        service: RippingService,
        check_availability: Callable[[], RippingAvailability],
        profile_context: Callable[[], tuple[int, str]],
        data_directory: Path,
        show_status: Callable[[str], None],
        is_shutting_down: Callable[[], bool],
        schedule: Callable[[int, Callable[[], bool]], int],
        remove_source: Callable[[int], object],
        dispatch: Callable[[Callable[[], bool]], object],
        new_run_id: Callable[[], UUID] = uuid4,
    ) -> None:
        self._service = service
        self._check_availability = check_availability
        self._profile_context = profile_context
        self._data_directory = data_directory
        self._show_status = show_status
        self._is_shutting_down = is_shutting_down
        self._schedule = schedule
        self._remove_source = remove_source
        self._dispatch = dispatch
        self._new_run_id = new_run_id
        self.availability = RippingAvailability(False, "Checking Brynse availability.")
        self.probe_worker: threading.Thread | None = None
        self._timer_id: int | None = None
        self._last_status: tuple[int, str] | None = None

    def start(self, station: dict[str, Any]) -> int | None:
        """Submit one explicit station without changing the current selection."""
        if self._is_shutting_down():
            return None
        if not self.availability.available:
            self._show_status(f"Ripping unavailable: {self.availability.reason}")
            return None

        try:
            profile_id, profile_name = self._profile_context()
            result = coordinate_ripping_start(
                station,
                availability=self.availability,
                service=self._service,
                data_directory=self._data_directory,
                profile_id=profile_id,
                profile_name=profile_name,
                run_id=self._new_run_id(),
            )
        except Exception as exc:  # noqa: BLE001 - user-facing GTK status.
            self._show_status(f"Could not start ripping: {exc}")
            return None

        self._show_status(result.status)
        if result.job_id is not None:
            self.ensure_timer()
        return result.job_id

    def stop(self, station: dict[str, Any]) -> None:
        """Request stopping for an explicit station in the window's profile."""
        if self._is_shutting_down():
            return

        try:
            profile_id, _profile_name = self._profile_context()
            message = coordinate_ripping_stop(
                station,
                service=self._service,
                profile_id=profile_id,
            )
        except Exception as exc:  # noqa: BLE001 - user-facing GTK status.
            self._show_status(f"Could not stop ripping: {exc}")
            return

        if message is not None:
            self._show_status(message)
            self.ensure_timer()

    def ensure_timer(self) -> None:
        """Schedule one GTK state timer after a ripping job is accepted."""
        if self._is_shutting_down() or self._timer_id is not None:
            return
        self._timer_id = self._schedule(200, self.refresh)

    def refresh(self) -> bool:
        """Project current state until all ripping workers have finished."""
        if self._is_shutting_down():
            self._timer_id = None
            return False

        finished = self._service.wait(timeout=0)
        snapshot = self._service.snapshot()
        if snapshot is not None:
            message = ripping_status(snapshot)
            status_key = (snapshot.job_id, message)
            if status_key != self._last_status:
                self._show_status(message)
                self._last_status = status_key

        if finished:
            self._timer_id = None
        return not finished

    def probe_availability(self) -> None:
        """Check optional ripping support outside the GTK thread."""
        if self._is_shutting_down():
            return

        try:
            self.probe_worker = start_ripping_availability_probe(
                check_availability=self._check_availability,
                dispatch=self._dispatch,
                on_result=self.accept_availability,
            )
        except Exception as exc:  # noqa: BLE001 - optional capability failure.
            self.availability = RippingAvailability(
                False,
                f"Could not schedule ripping availability check: {exc}",
            )

    def accept_availability(
        self,
        availability: RippingAvailability,
    ) -> None:
        """Accept a dispatched capability result while the window is open."""
        if self._is_shutting_down():
            return
        self.availability = availability

    def stop_monitoring(self) -> None:
        """Cancel the owned source once; shutdown owns backend finalization."""
        if self._timer_id is not None:
            self._remove_source(self._timer_id)
            self._timer_id = None
