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


def test_service_stops_real_brynse_runner_after_pending_open(tmp_path: Path) -> None:
    from threading import Event, get_ident

    from fluxtuner.core.ripping_service import RippingService

    try:
        radio = importlib.import_module("brynse.integrations.radio")
    except ModuleNotFoundError as exc:
        if exc.name == "brynse":
            pytest.skip("Optional Brynse dependency is not installed")
        raise

    if shutil.which("ffmpeg") is None:
        pytest.skip("FFmpeg is required by the adapter")

    entered_open = Event()
    release_open = Event()
    caller_thread = get_ident()
    close_threads: list[int] = []

    class Source:
        metadata = {
            "Content-Type": "audio/mpeg",
            "icy-metaint": "16000",
        }

        def __init__(self) -> None:
            self.closed = Event()

        def read(self, max_bytes: int) -> bytes:
            assert self.closed.wait(timeout=5), "Source was not closed by Brynse."
            raise OSError("Read interrupted by source closure")

        def close(self) -> None:
            close_threads.append(get_ident())
            self.closed.set()

    source = Source()

    def open_stream(url):
        entered_open.set()
        assert release_open.wait(timeout=5), "Stream opening was not released."
        return source

    api = SimpleNamespace(
        RippingRunConfig=radio.RippingRunConfig,
        RippingRunner=lambda config: radio.RippingRunner(
            config,
            stream_opener=open_stream,
        ),
    )
    ripper = BrynseRipper(module_loader=lambda name: api)
    service = RippingService(backend_factory=lambda: ripper)
    request = RippingRequest(
        "Synthetic station",
        "https://example.invalid/synthetic",
        tmp_path / "tracks",
    )

    try:
        job_id = service.start(request)
        assert entered_open.wait(timeout=5)
        starting = service.snapshot()
        assert starting is not None
        assert starting.job_id == job_id
        assert starting.state == "starting"

        service.stop()
        pending = service.snapshot()
        assert pending is not None
        assert pending.state == "stopping"
        assert not source.closed.is_set()

        release_open.set()
        assert service.wait(timeout=5), "Brynse did not finish after pending stop."

        stopped = service.snapshot()
        assert stopped is not None
        assert stopped.job_id == job_id
        assert stopped.request is request
        assert stopped.state == "stopped"
        assert stopped.error is None
        assert stopped.result is not None
        assert stopped.result.request is request
        assert stopped.result.codec == "mp3"
        assert stopped.result.metaint == 16000
        assert stopped.result.stopped is True
        assert stopped.result.tracks == ()
        assert stopped.result.incomplete_track_title is None
        assert source.closed.is_set()
        assert close_threads
        assert all(thread != caller_thread for thread in close_threads)
    finally:
        service.stop()
        release_open.set()
        source.closed.set()
        assert service.wait(timeout=5)


def test_service_preserves_real_finalized_track_files(tmp_path: Path) -> None:
    import subprocess
    from io import BytesIO

    from fluxtuner.core.ripping_service import RippingService

    try:
        radio = importlib.import_module("brynse.integrations.radio")
    except ModuleNotFoundError as exc:
        if exc.name == "brynse":
            pytest.skip("Optional Brynse dependency is not installed")
        raise

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("FFmpeg is required by the adapter")

    volume = (
        r"volume=if(between(t\,19.5\,20.5)"
        r"+between(t\,39.5\,40.5)\,0\,1):eval=frame"
    )
    generated = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=44100:duration=60",
            "-af",
            volume,
            "-ac",
            "2",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "128k",
            "-write_xing",
            "0",
            "-id3v2_version",
            "0",
            "-f",
            "mp3",
            "pipe:1",
        ],
        capture_output=True,
        timeout=30,
    )
    assert generated.returncode == 0, generated.stderr.decode(errors="replace")
    audio = generated.stdout
    assert audio

    metaint = 16000
    wire = bytearray()
    for offset in range(0, len(audio), metaint):
        block = audio[offset : offset + metaint]
        wire.extend(block)
        if len(block) != metaint:
            break
        end_offset = offset + metaint
        title = (
            "Synthetic A"
            if end_offset < 320000
            else "Synthetic B"
            if end_offset < 640000
            else "Synthetic C"
        )
        payload = f"StreamTitle='{title}';".encode()
        units = (len(payload) + 15) // 16
        wire.append(units)
        wire.extend(payload.ljust(units * 16, b"\0"))

    class Source:
        metadata = {
            "Content-Type": "audio/mpeg",
            "icy-metaint": str(metaint),
        }

        def __init__(self):
            self.stream = BytesIO(wire)
            self.close_calls = 0

        def read(self, max_bytes):
            return self.stream.read(max_bytes)

        def close(self):
            self.close_calls += 1
            self.stream.close()

    source = Source()
    api = SimpleNamespace(
        RippingRunConfig=radio.RippingRunConfig,
        RippingRunner=lambda config: radio.RippingRunner(
            config,
            stream_opener=lambda url: source,
        ),
    )
    service = RippingService(
        backend_factory=lambda: BrynseRipper(module_loader=lambda name: api),
    )
    request = RippingRequest(
        station_name="Synthetic output contract",
        source_url="https://example.invalid/synthetic",
        output_directory=tmp_path / "tracks",
        profile_name="output-contract",
    )

    try:
        job_id = service.start(request)
        assert service.wait(timeout=45)
        snapshot = service.snapshot()
        assert snapshot is not None
        assert snapshot.job_id == job_id
        assert snapshot.state == "completed"
        assert snapshot.error is None, repr(snapshot.error)
        result = snapshot.result
        assert result is not None
        assert result.request is request
        assert result.codec == "mp3"
        assert result.metaint == metaint
        assert not result.stopped
        assert result.tracks
        assert result.tracks[0].title == "Synthetic A"

        for track in result.tracks:
            assert track.path.parent == request.output_directory
            assert track.path.is_file()
            assert track.path.stat().st_size > 0
            decoded = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-nostdin",
                    "-i",
                    str(track.path),
                    "-f",
                    "null",
                    "-",
                ],
                capture_output=True,
                timeout=15,
            )
            assert decoded.returncode == 0, decoded.stderr.decode(errors="replace")

        assert result.incomplete_track_title is not None
        assert result.incomplete_track_title not in {track.title for track in result.tracks}
        assert source.close_calls >= 1
    finally:
        service.stop()
        assert service.wait(timeout=10)
