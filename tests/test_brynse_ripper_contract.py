from __future__ import annotations

import importlib
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from fluxtuner.core.ripping import RippingRequest, RippingStarted
from fluxtuner.recorders.brynse import BrynseRipper


def test_adapter_delegates_stop_to_real_brynse_runner(tmp_path: Path) -> None:
    try:
        radio = importlib.import_module("brynse.integrations.radio")
    except ModuleNotFoundError as exc:
        if exc.name == "brynse":
            pytest.skip("Optional Brynse dependency is not installed")
        raise

    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is required by the adapter")

    class SyntheticSource:
        metadata = {
            "Content-Type": "audio/mpeg",
            "icy-metaint": "16000",
        }

        def __init__(self) -> None:
            self.read_calls = 0
            self.close_calls = 0

        def read(self, max_bytes: int) -> bytes:
            self.read_calls += 1
            raise AssertionError("Unexpected read after stop in on_started")

        def close(self) -> None:
            self.close_calls += 1

    source = SyntheticSource()
    api = SimpleNamespace(
        RippingRunConfig=radio.RippingRunConfig,
        RippingRunner=lambda config: radio.RippingRunner(
            config,
            stream_opener=lambda url: source,
        ),
    )
    ripper = BrynseRipper(module_loader=lambda name: api)
    request = RippingRequest(
        station_name="Synthetic station",
        source_url="https://example.invalid/synthetic",
        output_directory=tmp_path / "tracks",
        profile_name="contract-test",
    )
    started = []
    written = []

    def on_started(event: RippingStarted) -> None:
        started.append(event)
        ripper.stop()

    capability = ripper.availability()
    assert capability.available, capability.reason

    result = ripper.run(
        request,
        on_started=on_started,
        on_track_written=written.append,
    )

    assert started == [RippingStarted(codec="mp3", metaint=16000)]
    assert result.request is request
    assert result.stopped is True
    assert result.codec == "mp3"
    assert result.metaint == 16000
    assert result.incomplete_track_title is None
    assert result.tracks == ()
    assert written == []
    assert source.read_calls == 0
    assert source.close_calls >= 1

    closes_after_completion = source.close_calls
    ripper.stop()
    assert source.close_calls == closes_after_completion


@pytest.mark.parametrize("read_raises", [False, True])
def test_adapter_stops_real_runner_during_read(tmp_path: Path, read_raises: bool) -> None:
    from threading import Event, Thread

    try:
        radio = importlib.import_module("brynse.integrations.radio")
    except ModuleNotFoundError as exc:
        if exc.name == "brynse":
            pytest.skip("Optional Brynse dependency is not installed")
        raise

    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is required by the adapter")

    class BlockingSource:
        metadata = {
            "Content-Type": "audio/mpeg",
            "icy-metaint": "16000",
        }

        def __init__(self) -> None:
            self.reading = Event()
            self.release = Event()
            self.closed = Event()

        def read(self, max_bytes: int) -> bytes:
            self.reading.set()
            if not self.release.wait(timeout=5):
                raise AssertionError("Source read was not released")
            if read_raises:
                raise OSError("Read interrupted by source closure")
            return b""

        def close(self) -> None:
            self.closed.set()
            self.release.set()

    source = BlockingSource()
    api = SimpleNamespace(
        RippingRunConfig=radio.RippingRunConfig,
        RippingRunner=lambda config: radio.RippingRunner(
            config,
            stream_opener=lambda url: source,
        ),
    )
    ripper = BrynseRipper(module_loader=lambda name: api)
    request = RippingRequest(
        "Synthetic station",
        "https://example.invalid/synthetic",
        tmp_path / "tracks",
    )
    results = []
    errors = []

    def run() -> None:
        try:
            results.append(ripper.run(request))
        except Exception as exc:
            errors.append(exc)

    worker = Thread(target=run, daemon=True)
    worker.start()
    try:
        assert source.reading.wait(timeout=5), errors

        ripper.stop()
        worker.join(timeout=5)

        assert not worker.is_alive(), "Runner did not terminate after stop"
        assert source.closed.is_set()
        assert errors == []
        assert len(results) == 1
        assert results[0].request is request
        assert results[0].stopped is True
        assert results[0].tracks == ()
        assert results[0].incomplete_track_title is None
    finally:
        source.release.set()
        worker.join(timeout=5)
