from dataclasses import replace

import pytest

from fluxtuner.core.ripping import RippingAvailability, RippingRequest
from fluxtuner.core.ripping_service import RippingSnapshot
from fluxtuner.gui import gtk_ripping


def _menu_context(tmp_path, *, state=None, available=True, workers_finished=True):
    request = RippingRequest(
        station_name="Original station name",
        source_url="https://example.com/clicked",
        output_directory=tmp_path / "tracks",
        profile_id=7,
        profile_name="Focus",
    )
    return {
        "station": {
            "name": "Renamed clicked station",
            "url": "https://example.com/unresolved",
            "url_resolved": request.source_url,
        },
        "availability": RippingAvailability(available, "Unavailable"),
        "snapshot": (
            None if state is None else RippingSnapshot(job_id=1, request=request, state=state)
        ),
        "workers_finished": workers_finished,
        "profile_id": 7,
        "shutting_down": False,
    }


def test_ripping_menu_policy_offers_start_when_ready(tmp_path) -> None:
    context = _menu_context(tmp_path)

    assert gtk_ripping.ripping_menu_action(**context) == "start"


@pytest.mark.parametrize(("available", "workers_finished"), [(False, True), (True, False)])
def test_ripping_menu_policy_rejects_unavailable_or_busy_start(
    tmp_path, available, workers_finished
) -> None:
    context = _menu_context(tmp_path, available=available, workers_finished=workers_finished)

    assert gtk_ripping.ripping_menu_action(**context) is None


@pytest.mark.parametrize("state", ["completed", "stopped", "failed"])
@pytest.mark.parametrize("workers_finished", [False, True])
def test_ripping_menu_policy_terminal_state_requires_finished_workers(
    tmp_path, state, workers_finished
) -> None:
    context = _menu_context(tmp_path, state=state, workers_finished=workers_finished)

    expected = "start" if workers_finished else None
    assert gtk_ripping.ripping_menu_action(**context) == expected


@pytest.mark.parametrize("state", ["starting", "running"])
@pytest.mark.parametrize("available", [False, True])
def test_ripping_menu_policy_offers_matching_stop_independently_of_availability(
    tmp_path, state, available
) -> None:
    context = _menu_context(tmp_path, state=state, available=available, workers_finished=False)

    assert gtk_ripping.ripping_menu_action(**context) == "stop"


def test_ripping_menu_policy_hides_repeated_stop_while_stopping(tmp_path) -> None:
    context = _menu_context(tmp_path, state="stopping", workers_finished=False)

    assert gtk_ripping.ripping_menu_action(**context) is None


@pytest.mark.parametrize("mismatch", ["station", "profile"])
def test_ripping_menu_policy_rejects_other_station_or_profile(tmp_path, mismatch) -> None:
    context = _menu_context(tmp_path, state="running", workers_finished=False)
    if mismatch == "station":
        context["station"]["url_resolved"] = "https://example.com/other"
    else:
        snapshot = context["snapshot"]
        context["snapshot"] = replace(snapshot, request=replace(snapshot.request, profile_id=8))

    assert gtk_ripping.ripping_menu_action(**context) is None


@pytest.mark.parametrize("state", [None, "running"])
def test_ripping_menu_policy_hides_actions_during_shutdown(tmp_path, state) -> None:
    context = _menu_context(tmp_path, state=state, workers_finished=state is None)
    context["shutting_down"] = True

    assert gtk_ripping.ripping_menu_action(**context) is None
