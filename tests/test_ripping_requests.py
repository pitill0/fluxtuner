from pathlib import Path
from uuid import UUID

import pytest


def test_builder_snapshots_station_profile_and_output_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fluxtuner.core.ripping_requests import build_ripping_request

    monkeypatch.chdir(tmp_path)
    station = {
        "name": "Clicked station",
        "url": "https://example.invalid/original",
        "url_resolved": "https://example.invalid/resolved",
    }
    original_station = station.copy()
    run_id = UUID("11111111-1111-4111-8111-111111111111")

    request = build_ripping_request(
        station,
        data_directory=Path("app-data"),
        profile_id=7,
        profile_name="Focus",
        run_id=run_id,
    )

    assert station == original_station
    station["name"] = "Another station"
    station["url_resolved"] = "https://example.invalid/another"
    monkeypatch.chdir(tmp_path.parent)

    assert request.station_name == "Clicked station"
    assert request.source_url == "https://example.invalid/resolved"
    assert request.profile_id == 7
    assert request.profile_name == "Focus"
    assert request.output_directory == (tmp_path / "app-data" / "rips" / "profile-7" / run_id.hex)
    assert not (tmp_path / "app-data").exists()
