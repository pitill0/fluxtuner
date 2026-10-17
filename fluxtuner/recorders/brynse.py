"""Optional adapter to Brynse's public radio runner, without GTK imports."""

from __future__ import annotations

import importlib
import shutil
from collections.abc import Callable
from threading import Lock
from typing import Any

from fluxtuner.core.ripping import (
    RippedTrack,
    RippingAvailability,
    RippingError,
    RippingRequest,
    RippingResult,
    RippingStarted,
)


class BrynseRipper:
    """Run one blocking job at a time with a fresh Brynse runner per job.

    stop() delegates to the active runner; it does not wait for completion or
    guarantee cancellation during stream opening. Worker lifecycle belongs to
    the future coordinator, not to GTK or this adapter.
    """

    def __init__(
        self,
        *,
        module_loader: Callable[[str], Any] = importlib.import_module,
        executable_resolver: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self._module_loader = module_loader
        self._executable_resolver = executable_resolver
        self._run_lock = Lock()
        self._runner: Any = None

    def _load_runtime(self) -> tuple[Any, str]:
        try:
            radio = self._module_loader("brynse.integrations.radio")
        except ModuleNotFoundError as exc:
            if exc.name == "brynse":
                raise RippingError("Brynse is not installed.") from exc
            raise RippingError(f"Brynse could not be loaded: {exc}") from exc
        except Exception as exc:  # noqa: BLE001 - a broken optional import is unavailable.
            raise RippingError(f"Brynse could not be loaded: {exc}") from exc

        if not all(
            callable(getattr(radio, name, None)) for name in ("RippingRunConfig", "RippingRunner")
        ):
            raise RippingError("Brynse radio API is incompatible.")

        ffmpeg = self._executable_resolver("ffmpeg")
        if ffmpeg is None:
            raise RippingError("Ripping unavailable: ffmpeg was not found in PATH.")
        return radio, ffmpeg

    def availability(self) -> RippingAvailability:
        try:
            self._load_runtime()
        except RippingError as exc:
            return RippingAvailability(available=False, reason=str(exc))
        return RippingAvailability(available=True)

    def run(
        self,
        request: RippingRequest,
        *,
        on_started: Callable[[RippingStarted], None] | None = None,
        on_track_written: Callable[[RippedTrack], None] | None = None,
    ) -> RippingResult:
        if not self._run_lock.acquire(blocking=False):
            raise RippingError("A ripping run is already active.")

        tracks: list[RippedTrack] = []

        def started(codec: str, metaint: int) -> None:
            if on_started is not None:
                on_started(RippingStarted(codec=codec, metaint=metaint))

        def track_written(written: Any) -> None:
            track = RippedTrack(title=written.transition.outgoing.title, path=written.path)
            tracks.append(track)
            if on_track_written is not None:
                on_track_written(track)

        try:
            radio, ffmpeg = self._load_runtime()
            config = radio.RippingRunConfig(
                url=request.source_url,
                output_directory=request.output_directory,
                ffmpeg_binary=ffmpeg,
            )
            runner = radio.RippingRunner(config)
            self._runner = runner
            result = runner.run(on_started=started, on_track_written=track_written)
            return RippingResult(
                request=request,
                codec=result.codec,
                metaint=result.metaint,
                stopped=result.stopped,
                tracks=tuple(tracks),
                incomplete_track_title=result.incomplete_track_title,
            )
        except Exception as exc:  # noqa: BLE001 - contain optional backend failures.
            raise RippingError(str(exc), tracks=tuple(tracks)) from exc
        finally:
            self._runner = None
            self._run_lock.release()

    def stop(self) -> None:
        runner = self._runner
        if runner is not None:
            try:
                runner.stop()
            except Exception as exc:  # noqa: BLE001 - contain optional backend failures.
                raise RippingError(f"Could not stop ripping: {exc}") from exc
