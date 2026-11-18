# SPDX-License-Identifier: MIT
"""Security contracts for versioned recommendation snapshots."""

from __future__ import annotations

import json

import pytest

from fluxtuner.core.m3u_import import M3UEntry
from fluxtuner.core.share_snapshots import (
    MAX_SHARE_STATIONS,
    build_share_snapshot,
    validate_share_title,
)


def _entry(
    name: str = "Radio",
    url: str = "https://radio.example/live",
) -> M3UEntry:
    return M3UEntry(name=name, url=url)


def test_single_station_snapshot_is_minimal_and_versioned():
    result = build_share_snapshot(
        kind="station",
        entries=(_entry(),),
    )

    assert json.loads(result) == {
        "version": 1,
        "stations": [{"name": "Radio", "url": "https://radio.example/live"}],
    }


def test_playlist_snapshot_preserves_order_and_unicode():
    result = build_share_snapshot(
        kind="playlist",
        entries=(
            _entry("Música", "https://radio.example/first"),
            _entry("第二", "https://radio.example/second"),
        ),
    )
    stations = json.loads(result)["stations"]

    assert [item["name"] for item in stations] == ["Música", "第二"]
    assert [item["url"] for item in stations] == [
        "https://radio.example/first",
        "https://radio.example/second",
    ]


def test_snapshot_is_deterministic():
    entries = (_entry(),)
    assert build_share_snapshot(kind="station", entries=entries) == build_share_snapshot(
        kind="station", entries=entries
    )


@pytest.mark.parametrize(
    "kind,entries",
    [
        ("invalid", (_entry(),)),
        ("station", ()),
        ("playlist", ()),
        ("station", (_entry(), _entry())),
        ("playlist", tuple(_entry() for _ in range(MAX_SHARE_STATIONS + 1))),
    ],
)
def test_invalid_kind_or_count_rejected(kind, entries):
    with pytest.raises(ValueError):
        build_share_snapshot(kind=kind, entries=entries)


@pytest.mark.parametrize(
    "url",
    [
        "https://user:password@radio.example/live",
        "https://radio.example/live?token=secret",
        "https://radio.example/live?key=abc",
        "https://radio.example/live#private",
        "http://radio.example/live?quality=high",
        "file:///tmp/radio",
        "javascript:alert(1)",
        "https://radio.example/live\\bad",
        "https://radio.example/live\nHeader: value",
    ],
)
def test_unshareable_urls_rejected(url):
    with pytest.raises(ValueError):
        build_share_snapshot(
            kind="station",
            entries=(_entry(url=url),),
        )


@pytest.mark.parametrize(
    "name",
    [
        "",
        " ",
        "x" * 201,
        "bad\nname",
        "bad\u202ename",
    ],
)
def test_invalid_station_names_rejected(name):
    with pytest.raises(ValueError):
        build_share_snapshot(
            kind="station",
            entries=(_entry(name=name),),
        )


@pytest.mark.parametrize(
    "title",
    ["", " ", "x" * 121, "bad\nname", "bad\u202etitle"],
)
def test_invalid_titles_rejected(title):
    with pytest.raises(ValueError):
        validate_share_title(title)


def test_title_is_normalized():
    assert validate_share_title("  Morning Radio  ") == "Morning Radio"


def test_utf8_size_limit_is_enforced():
    entries = tuple(
        _entry("é" * 200, f"https://radio.example/{i}/" + "a" * 1900)
        for i in range(MAX_SHARE_STATIONS)
    )
    result = build_share_snapshot(kind="playlist", entries=entries)

    assert len(result.encode("utf-8")) <= 1_048_576


def test_snapshot_rejects_non_entry_objects():
    with pytest.raises(ValueError):
        build_share_snapshot(
            kind="station",
            entries=({"name": "Radio", "url": "https://radio.example"},),
        )
