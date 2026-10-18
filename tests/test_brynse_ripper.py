from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from fluxtuner.core.ripping import (
    RippedTrack,
    RippingError,
    RippingRequest,
    RippingStarted,
)
from fluxtuner.recorders.brynse import BrynseRipper


def request(tmp_path: Path) -> RippingRequest:
    return RippingRequest.from_station(
        {"name": "Flux FM", "url": "https://radio.example/stream"},
        output_directory=tmp_path / "tracks",
        profile_name="work",
    )


def api_with_runner(runner: Mock) -> SimpleNamespace:
    return SimpleNamespace(
        RippingRunConfig=Mock(side_effect=lambda **kwargs: SimpleNamespace(**kwargs)),
        RippingRunner=Mock(return_value=runner),
    )


def backend(api: SimpleNamespace) -> BrynseRipper:
    return BrynseRipper(
        module_loader=Mock(return_value=api),
        executable_resolver=Mock(return_value="/tools/ffmpeg"),
    )


def test_request_snapshots_explicit_station_without_mutating_it(tmp_path: Path) -> None:
    station = {
        "name": " Flux FM ",
        "url": "https://radio.example/original",
        "url_resolved": " https://radio.example/resolved ",
    }
    original = dict(station)
    value = RippingRequest.from_station(station, output_directory=tmp_path, profile_name="work")
    assert station == original
    station["name"] = "Other"
    station["url_resolved"] = "https://radio.example/other"
    assert value.station_name == "Flux FM"
    assert value.source_url == "https://radio.example/resolved"
    assert value.profile_name == "work"


@pytest.mark.parametrize("url", ["", "file:///etc/passwd", "ftp://radio.example/a", "https://"])
def test_request_rejects_invalid_streams(tmp_path: Path, url: str) -> None:
    with pytest.raises(RippingError, match="HTTP"):
        RippingRequest("Flux FM", url, tmp_path)


def test_request_rejects_blank_station_name(tmp_path: Path) -> None:
    with pytest.raises(RippingError, match="station name"):
        RippingRequest(" ", "https://radio.example/stream", tmp_path)


def test_absent_optional_dependency_does_not_create_output(tmp_path: Path) -> None:
    loader = Mock(side_effect=ModuleNotFoundError("No module named brynse", name="brynse"))
    ripper = BrynseRipper(module_loader=loader)
    capability = ripper.availability()
    assert not capability.available
    assert "not installed" in capability.reason
    with pytest.raises(RippingError, match="not installed"):
        ripper.run(request(tmp_path))
    assert not (tmp_path / "tracks").exists()


@pytest.mark.parametrize(
    "failure",
    [
        ModuleNotFoundError("No module named numpy", name="numpy"),
        ImportError("incompatible Brynse API"),
        OSError("incompatible native dependency"),
        RuntimeError("backend initialization failed"),
    ],
)
def test_broken_installation_is_distinguished_from_absence(failure: Exception) -> None:
    ripper = BrynseRipper(module_loader=Mock(side_effect=failure))
    capability = ripper.availability()
    assert not capability.available
    assert "could not be loaded" in capability.reason
    assert "not installed" not in capability.reason
    assert str(failure) in capability.reason


def test_incompatible_public_api_is_unavailable() -> None:
    ripper = backend(SimpleNamespace())
    capability = ripper.availability()
    assert not capability.available
    assert "API" in capability.reason


def test_probe_is_lazy_and_does_not_construct_a_runner() -> None:
    api = api_with_runner(Mock())
    loader = Mock(return_value=api)
    ripper = BrynseRipper(
        module_loader=loader, executable_resolver=Mock(return_value="/tools/ffmpeg")
    )
    loader.assert_not_called()
    assert ripper.availability().available
    loader.assert_called_once_with("brynse.integrations.radio")
    api.RippingRunner.assert_not_called()


def test_missing_ffmpeg_is_unavailable(tmp_path: Path) -> None:
    api = api_with_runner(Mock())
    ripper = BrynseRipper(
        module_loader=Mock(return_value=api), executable_resolver=Mock(return_value=None)
    )
    capability = ripper.availability()
    assert not capability.available
    assert "ffmpeg" in capability.reason
    with pytest.raises(RippingError, match="ffmpeg"):
        ripper.run(request(tmp_path))
    api.RippingRunner.assert_not_called()


def test_runner_config_uses_explicit_request_and_safe_defaults(tmp_path: Path) -> None:
    runner = Mock()
    runner.run.return_value = SimpleNamespace(
        codec="mp3", metaint=16000, stopped=False, incomplete_track_title=None
    )
    api = api_with_runner(runner)
    value = request(tmp_path)
    result = backend(api).run(value)
    api.RippingRunConfig.assert_called_once_with(
        url=value.source_url,
        output_directory=value.output_directory,
        ffmpeg_binary="/tools/ffmpeg",
    )
    assert result.request is value
    assert result.tracks == ()
    assert result.codec == "mp3"
    assert result.metaint == 16000
    assert not result.stopped


def test_callbacks_translate_finalized_tracks_and_keep_incomplete_separate(tmp_path: Path) -> None:
    output = tmp_path / "Artist - Track.mp3"
    written = SimpleNamespace(
        path=output,
        transition=SimpleNamespace(outgoing=SimpleNamespace(title="Artist - Track")),
    )
    runner = Mock()

    def run(**callbacks):
        callbacks["on_started"]("mp3", 16000)
        callbacks["on_track_written"](written)
        return SimpleNamespace(
            codec="mp3", metaint=16000, stopped=True, incomplete_track_title="Still playing"
        )

    runner.run.side_effect = run
    started, tracks = Mock(), Mock()
    result = backend(api_with_runner(runner)).run(
        request(tmp_path), on_started=started, on_track_written=tracks
    )
    started.assert_called_once_with(RippingStarted(codec="mp3", metaint=16000))
    tracks.assert_called_once_with(RippedTrack(title="Artist - Track", path=output))
    assert result.tracks == (RippedTrack(title="Artist - Track", path=output),)
    assert result.incomplete_track_title == "Still playing"
    assert result.stopped


@pytest.mark.parametrize("failure", [OSError("disk full"), RuntimeError("read failed")])
def test_run_failure_preserves_already_finalized_tracks(tmp_path: Path, failure: Exception) -> None:
    output = tmp_path / "saved.mp3"
    runner = Mock()

    def run(**callbacks):
        callbacks["on_track_written"](
            SimpleNamespace(
                path=output,
                transition=SimpleNamespace(outgoing=SimpleNamespace(title="Saved")),
            )
        )
        raise failure

    runner.run.side_effect = run
    ripper = backend(api_with_runner(runner))
    value = request(tmp_path)
    with pytest.raises(RippingError, match=str(failure)) as caught:
        ripper.run(value)
    assert caught.value.tracks == (RippedTrack(title="Saved", path=output),)
    assert caught.value.__cause__ is failure
    ripper.stop()
    runner.stop.assert_not_called()


def test_callback_failure_keeps_the_track_that_triggered_it(tmp_path: Path) -> None:
    runner = Mock()
    output = tmp_path / "saved.mp3"

    def run(**callbacks):
        callbacks["on_track_written"](
            SimpleNamespace(
                path=output,
                transition=SimpleNamespace(outgoing=SimpleNamespace(title="Saved")),
            )
        )

    runner.run.side_effect = run
    with pytest.raises(RippingError, match="consumer failed") as caught:
        backend(api_with_runner(runner)).run(
            request(tmp_path), on_track_written=Mock(side_effect=ValueError("consumer failed"))
        )
    assert caught.value.tracks == (RippedTrack(title="Saved", path=output),)


def test_runner_construction_failure_is_contained(tmp_path: Path) -> None:
    api = api_with_runner(Mock())
    api.RippingRunner.side_effect = RuntimeError("construction failed")
    with pytest.raises(RippingError, match="construction failed"):
        backend(api).run(request(tmp_path))


def test_stop_delegates_to_current_runner_and_is_idle_afterwards(tmp_path: Path) -> None:
    runner = Mock()
    ripper = backend(api_with_runner(runner))

    def run(**callbacks):
        callbacks["on_started"]("aac", 8192)
        return SimpleNamespace(codec="aac", metaint=8192, stopped=True, incomplete_track_title=None)

    runner.run.side_effect = run
    ripper.stop()
    ripper.run(request(tmp_path), on_started=lambda _: ripper.stop())
    ripper.stop()
    runner.stop.assert_called_once_with()


def test_stop_failure_is_contained(tmp_path: Path) -> None:
    runner = Mock()
    runner.stop.side_effect = OSError("close failed")
    ripper = backend(api_with_runner(runner))

    def run(**callbacks):
        with pytest.raises(RippingError, match="Could not stop ripping: close failed"):
            ripper.stop()
        return SimpleNamespace(
            codec="mp3", metaint=16000, stopped=False, incomplete_track_title=None
        )

    runner.run.side_effect = run
    ripper.run(request(tmp_path))


def test_overlapping_run_is_rejected_and_each_run_gets_a_new_runner(tmp_path: Path) -> None:
    runner = Mock()
    api = api_with_runner(runner)
    ripper = backend(api)

    def run(**callbacks):
        with pytest.raises(RippingError, match="already active"):
            ripper.run(request(tmp_path))
        return SimpleNamespace(
            codec="mp3", metaint=16000, stopped=False, incomplete_track_title=None
        )

    runner.run.side_effect = run
    ripper.run(request(tmp_path))
    ripper.run(request(tmp_path))
    assert api.RippingRunner.call_count == 2


@pytest.mark.parametrize(
    "url",
    [
        "https://[broken",
        "https://[not-an-ip]/stream",
    ],
)
def test_request_wraps_malformed_stream_url(tmp_path: Path, url: str) -> None:
    with pytest.raises(RippingError, match="HTTP"):
        RippingRequest("Flux FM", url, tmp_path)


def test_request_keeps_output_destination_after_chdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = tmp_path / "initial"
    other = tmp_path / "other"
    initial.mkdir()
    other.mkdir()

    monkeypatch.chdir(initial)
    expected = Path.cwd() / "tracks"
    value = RippingRequest(
        "Flux FM",
        "https://radio.example/stream",
        Path("tracks"),
    )

    monkeypatch.chdir(other)

    assert value.output_directory.absolute() == expected
    assert not expected.exists()
    assert not (other / "tracks").exists()
