"""GTK-independent quit confirmation and asynchronous shutdown orchestration."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import suppress
from time import monotonic
from typing import Protocol

from fluxtuner.core.recording import RecordingManager
from fluxtuner.core.ripping_service import RippingService
from fluxtuner.gui.gtk_recording_shutdown import AsyncRecordingStop
from fluxtuner.gui.gtk_ripping import RippingShutdown, shutdown_has_pending_recordings


class QuitConfirmation(Protocol):
    def __call__(
        self, *, on_confirm: Callable[[], None], on_cancel: Callable[[], None]
    ) -> None: ...


class ShutdownWarning(Protocol):
    def __call__(
        self, *, on_wait: Callable[[], None], on_force: Callable[[], None], has_error: bool
    ) -> None: ...


class ShutdownController:
    """Own quit state, one completion timer and the existing finalization workers."""

    def __init__(
        self,
        *,
        recording_manager: RecordingManager,
        ripping_service: RippingService,
        stop_activity: Callable[[], None],
        stop_playback: Callable[[], None],
        prepare_quit: Callable[[], None],
        show_status: Callable[[str], None],
        show_confirmation: QuitConfirmation,
        show_warning: ShutdownWarning,
        schedule: Callable[[int, Callable[[], bool]], int],
        remove_source: Callable[[int], object],
        clock: Callable[[], float] = monotonic,
    ) -> None:
        self._recording_manager = recording_manager
        self._ripping_service = ripping_service
        self._stop_activity = stop_activity
        self._stop_playback = stop_playback
        self._prepare_quit = prepare_quit
        self._show_status = show_status
        self._show_confirmation = show_confirmation
        self._show_warning = show_warning
        self._schedule = schedule
        self._remove_source = remove_source
        self._clock = clock
        self._ripping_stop = RippingShutdown(service=ripping_service)
        self._recording_stop = AsyncRecordingStop(stop=recording_manager.stop)
        self.confirmation_pending = False
        self.shutting_down = False
        self.close_authorized = False
        self._timer_id: int | None = None
        self._on_complete: Callable[[], None] | None = None
        self._deadline: float | None = None
        self._warning_open = False

    @property
    def pending_completion(self) -> Callable[[], None] | None:
        """Expose the first pending completion for the window's close adapter."""
        return self._on_complete

    def request_quit(self, *, on_complete: Callable[[], None]) -> None:
        """Confirm pending recording work before beginning shutdown."""
        if self.confirmation_pending or self.shutting_down:
            return

        if not shutdown_has_pending_recordings(
            recording_manager=self._recording_manager,
            ripping_service=self._ripping_service,
        ):
            self._prepare_quit()
            if self.shutdown(on_complete=on_complete):
                self.close_authorized = True
                on_complete()
            return

        self.confirmation_pending = True
        settled = False

        def cancel() -> None:
            nonlocal settled
            if settled:
                return
            settled = True
            self.confirmation_pending = False

        def confirm() -> None:
            nonlocal settled
            if settled:
                return
            settled = True
            self.confirmation_pending = False
            self._prepare_quit()
            if self.shutdown(on_complete=on_complete):
                self.close_authorized = True
                on_complete()

        self._show_confirmation(
            on_confirm=confirm,
            on_cancel=cancel,
        )

    def shutdown(self, *, on_complete: Callable[[], None] | None = None) -> bool:
        """Request orderly stops; never block or force a timed-out exit."""
        if not self.shutting_down:
            self.shutting_down = True
            self._deadline = self._clock() + 12.0
            self._ripping_stop.request()
            if self._ripping_stop.error is not None:
                self._show_status(f"Could not stop ripping: {self._ripping_stop.error}")
            self._stop_activity()
            if self._recording_manager.active_session is not None:
                self._recording_stop.request()
            with suppress(Exception):
                self._stop_playback()

        if on_complete is not None and self._on_complete is None:
            self._on_complete = on_complete

        ripping_done = self._ripping_stop.poll()
        ffmpeg_done = not self._recording_stop.requested or self._recording_stop.poll()
        successful = (
            ripping_done
            and ffmpeg_done
            and self._ripping_stop.error is None
            and self._recording_stop.error is None
        )
        if successful:
            if self._timer_id is not None:
                self._remove_source(self._timer_id)
                self._timer_id = None
            self._on_complete = None
            self._deadline = None
            return True

        if self._on_complete is not None and self._timer_id is None:
            self._timer_id = self._schedule(200, self.poll)
        return False

    def poll(self) -> bool:
        """Inspect both workers and a monotonic deadline on GTK's main loop."""
        callback = self._on_complete
        if callback is None:
            self._timer_id = None
            return False

        ripping_done = self._ripping_stop.poll()
        ffmpeg_done = not self._recording_stop.requested or self._recording_stop.poll()
        has_error = self._ripping_stop.error is not None or self._recording_stop.error is not None
        if ripping_done and ffmpeg_done and not has_error and not self._warning_open:
            self._on_complete = None
            self._timer_id = None
            self._deadline = None
            self.close_authorized = True
            callback()
            return False

        deadline = self._deadline
        if not self._warning_open and (deadline is not None and self._clock() >= deadline):
            self._warning_open = True

            def keep_waiting() -> None:
                self._warning_open = False
                self._deadline = self._clock() + 12.0

            def quit_anyway() -> None:
                self._warning_open = False
                self._on_complete = None
                self._timer_id = None
                self._deadline = None
                self.close_authorized = True
                callback()

            self._show_warning(
                on_wait=keep_waiting,
                on_force=quit_anyway,
                has_error=has_error,
            )
        return True
