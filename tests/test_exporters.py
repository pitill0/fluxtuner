"""Round-trip and security tests for portable station exporters."""

from __future__ import annotations

import pytest

from fluxtuner.core import exporters
from fluxtuner.core.m3u_import import M3UEntry, parse_m3u, parse_pls


@pytest.fixture
def entries() -> list[M3UEntry]:
    return [
        M3UEntry("Ràdio València, Jazz", "https://radio.example/jazz"),
        M3UEntry("日本語 Radio", "https://radio.example/jp?station=2&lang=ja"),
        M3UEntry("Rock = Live", "http://rock.example/live.m3u8"),
    ]


@pytest.mark.parametrize(
    ("exporter", "parser"),
    [
        (exporters.export_m3u, parse_m3u),
        (exporters.export_pls, parse_pls),
    ],
)
def test_round_trip_preserves_order_names_urls_and_utf8(entries, exporter, parser):
    content = exporter(entries)
    preview = parser(content)
    assert [(item.name, item.url) for item in preview.entries] == [
        (item.name, item.url) for item in entries
    ]
    assert preview.issues == ()
    assert preview.duplicates == 0
    assert content == exporter(entries)


def test_m3u_header_and_line_termination(entries):
    content = exporters.export_m3u(entries)
    assert content.startswith(b"#EXTM3U\n")
    assert content.endswith(b"\n")


def test_pls_declares_exact_entry_count(entries):
    content = exporters.export_pls(entries)
    assert b"NumberOfEntries=3\n" in content
    assert content.endswith(b"Version=2\n")


@pytest.mark.parametrize("exporter", [exporters.export_m3u, exporters.export_pls])
def test_rejects_empty_collections(exporter):
    with pytest.raises(ValueError, match="empty"):
        exporter([])


@pytest.mark.parametrize("exporter", [exporters.export_m3u, exporters.export_pls])
def test_rejects_duplicate_urls(exporter):
    entries = [
        M3UEntry("One", "https://radio.example/live"),
        M3UEntry("Two", "https://radio.example/live"),
    ]
    with pytest.raises(ValueError, match="Duplicate"):
        exporter(entries)


@pytest.mark.parametrize("exporter", [exporters.export_m3u, exporters.export_pls])
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://user:secret@radio.example/live",
        "https://radio.example/my stream",
    ],
)
def test_rejects_invalid_urls(exporter, url):
    with pytest.raises(ValueError):
        exporter([M3UEntry("Radio", url)])


@pytest.mark.parametrize("exporter", [exporters.export_m3u, exporters.export_pls])
@pytest.mark.parametrize("name", ["Bad\n#EXTINF:-1,Injected", "Bad\tTitle", "x" * 201])
def test_rejects_invalid_names(exporter, name):
    with pytest.raises(ValueError):
        exporter([M3UEntry(name, "https://radio.example/live")])


@pytest.mark.parametrize("exporter", [exporters.export_m3u, exporters.export_pls])
@pytest.mark.parametrize("separator", ["\u2028", "\u2029"])
def test_rejects_unicode_line_separators(exporter, separator):
    entry = M3UEntry(
        name=f"Radio{separator}Jazz",
        url="https://radio.example/live",
    )
    with pytest.raises(ValueError, match="Unicode line separator"):
        exporter([entry])


@pytest.mark.parametrize("exporter", [exporters.export_m3u, exporters.export_pls])
def test_rejects_invalid_entry_types(exporter):
    with pytest.raises(ValueError):
        exporter([{"name": "Radio", "url": "https://radio.example/live"}])


@pytest.mark.parametrize("exporter", [exporters.export_m3u, exporters.export_pls])
def test_rejects_station_count_limit(monkeypatch, exporter):
    monkeypatch.setattr(exporters, "MAX_STATIONS", 1)
    with pytest.raises(ValueError, match="station limit"):
        exporter(
            [
                M3UEntry("One", "https://radio.example/1"),
                M3UEntry("Two", "https://radio.example/2"),
            ]
        )


@pytest.mark.parametrize("exporter", [exporters.export_m3u, exporters.export_pls])
def test_rejects_output_byte_limit(monkeypatch, exporter):
    monkeypatch.setattr(exporters, "MAX_FILE_BYTES", 16)
    with pytest.raises(ValueError, match="byte limit"):
        exporter([M3UEntry("Radio", "https://radio.example/live")])
