# SPDX-License-Identifier: MIT
"""Contract tests for remote catalog refresh comparison."""

import pytest

from fluxtuner.core.m3u_import import M3UEntry
from fluxtuner.core.remote_subscriptions import compare_catalogs


def entry(name: str, url: str) -> M3UEntry:
    return M3UEntry(name=name, url=url)


def test_initial_subscription_preview() -> None:
    result = compare_catalogs(
        [],
        [entry("Radio A", "https://radio.example/a")],
    )
    assert len(result.added) == 1
    assert not result.removed
    assert not result.changed
    assert result.unchanged == 0


def test_identical_refresh_has_no_changes() -> None:
    current = [entry("Radio A", "https://radio.example/a")]
    result = compare_catalogs(current, current)
    assert not result.added
    assert not result.removed
    assert not result.changed
    assert result.unchanged == 1


def test_added_removed_and_renamed_stations() -> None:
    before = [
        entry("Old Name", "https://radio.example/a"),
        entry("Removed", "https://radio.example/b"),
    ]
    after = [
        entry("New Name", "https://radio.example/a"),
        entry("Added", "https://radio.example/c"),
    ]
    result = compare_catalogs(before, after)
    assert [item.name for item in result.added] == ["Added"]
    assert [item.name for item in result.removed] == ["Removed"]
    assert len(result.changed) == 1
    assert result.changed[0].before.name == "Old Name"
    assert result.changed[0].after.name == "New Name"


def test_changed_stream_url_is_not_assumed_same_station() -> None:
    result = compare_catalogs(
        [entry("Radio A", "https://radio.example/old")],
        [entry("Radio A", "https://radio.example/new")],
    )
    assert len(result.added) == 1
    assert len(result.removed) == 1
    assert not result.changed


def test_empty_incoming_catalog_is_rejected() -> None:
    with pytest.raises(ValueError):
        compare_catalogs(
            [entry("Radio A", "https://radio.example/a")],
            [],
        )


def test_duplicate_identity_is_rejected() -> None:
    with pytest.raises(ValueError):
        compare_catalogs(
            [],
            [
                entry("Radio A", "https://radio.example/a"),
                entry("Radio B", "https://radio.example/a"),
            ],
        )


def test_invalid_station_is_rejected() -> None:
    with pytest.raises(ValueError):
        compare_catalogs(
            [],
            [entry("Bad", "file:///etc/passwd")],
        )


def test_refresh_comparison_has_no_input_side_effects() -> None:
    before = [entry("A", "https://radio.example/a")]
    after = [entry("B", "https://radio.example/a")]
    before_copy = list(before)
    after_copy = list(after)

    compare_catalogs(before, after)

    assert before == before_copy
    assert after == after_copy
