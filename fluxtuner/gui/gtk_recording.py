# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fluxtuner.core.recording import RecordingManager, RecordingRequest


class RecordingController:
    """Coordinate recording actions without owning widgets or session state."""

    def __init__(
        self,
        *,
        manager: RecordingManager,
        show_status: Callable[[str], None],
        refresh_controls: Callable[[], None],
    ) -> None:
        self._manager = manager
        self._show_status = show_status
        self._refresh_controls = refresh_controls

    def start(
        self,
        station: dict[str, Any],
        *,
        available: bool,
        station_url: Callable[[dict[str, Any]], str | None],
        station_name: Callable[[dict[str, Any]], str],
        output_path: Callable[[str], Path],
    ) -> None:
        if not available:
            self._show_status("Recording unavailable: ffmpeg was not found in PATH.")
            self._refresh_controls()
            return

        source_url = station_url(station)
        if not source_url:
            self._show_status("Selected station has no stream URL.")
            self._refresh_controls()
            return

        display_name = station_name(station)
        destination = output_path(display_name)
        try:
            self._manager.start(
                RecordingRequest(
                    station_name=display_name,
                    source_url=source_url,
                    output_path=destination,
                )
            )
        except Exception as exc:  # noqa: BLE001 - preserve the GTK action error boundary.
            self._show_status(f"Could not start recording: {exc}")
            self._refresh_controls()
            return

        self._refresh_controls()
        self._show_status(f"Recording: {display_name} → {destination.name}")

    def stop(self) -> None:
        if self._manager.active_session is None:
            self._show_status("No recording is active.")
            self._refresh_controls()
            return

        try:
            completed = self._manager.stop()
        except Exception as exc:  # noqa: BLE001 - preserve the GTK action error boundary.
            self._show_status(f"Could not finalize recording: {exc}")
            self._refresh_controls()
            return

        self._refresh_controls()
        if completed is None:
            self._show_status("Recording stopped.")
            return

        self._show_status(
            f"Saved recording #{completed.recording_id}: "
            f"{completed.station_name} → {completed.output_path.name}"
        )
