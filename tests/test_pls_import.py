from __future__ import annotations

import pytest

from fluxtuner.core.m3u_import import parse_m3u, parse_pls, parse_station_collection


def test_pls_order_titles_and_gaps() -> None:
    preview = parse_pls(
        b"[playlist]\nNumberOfEntries=2\nFile3=https://example.org/three\n"
        b"Title3=Third\nFile1=https://example.org/one\nTitle1=First\nVersion=2\n"
    )
    assert [(entry.name, entry.url) for entry in preview.entries] == [
        ("First", "https://example.org/one"),
        ("Third", "https://example.org/three"),
    ]
    assert preview.issues == ()


def test_pls_missing_name_duplicate_url_and_bad_count() -> None:
    preview = parse_station_collection(
        b"[playlist]\nNumberOfEntries=5\nFile1=https://example.org/a\n"
        b"File2=https://example.org/a\nFile3=https://example.org/b\n"
    )
    assert [entry.name for entry in preview.entries] == ["example.org", "example.org"]
    assert preview.duplicates == 1
    assert any("NumberOfEntries" in issue.reason for issue in preview.issues)


def test_pls_duplicate_key_is_reported_first_value_wins() -> None:
    preview = parse_pls(
        b"[playlist]\nFile1=https://example.org/a\n"
        b"File1=https://example.org/other\nTitle1=Original\n"
    )
    assert len(preview.entries) == 1
    assert preview.entries[0].url == "https://example.org/a"
    assert any("Duplicate PLS key" in issue.reason for issue in preview.issues)


def test_pls_invalid_url_does_not_discard_valid_entries() -> None:
    preview = parse_pls(b"[playlist]\nFile1=file:///tmp/a.mp3\nFile2=https://example.org/valid\n")
    assert [entry.url for entry in preview.entries] == ["https://example.org/valid"]
    assert len(preview.issues) == 1


@pytest.mark.parametrize(
    "payload", [b"[playlist]\nFile1=https://x\nFile1=https://y", b"[playlist]\nNumberOfEntries=abc"]
)
def test_pls_bad_fields_are_deterministic(payload: bytes) -> None:
    assert parse_pls(payload) == parse_pls(payload)


def test_m3u_dispatch_stays_unchanged() -> None:
    data = b"#EXTM3U\n#EXTINF:-1,Classic\nhttps://example.org/radio\n"
    assert parse_station_collection(data) == parse_m3u(data)


def test_pls_loader_and_invalid_header(tmp_path) -> None:
    from fluxtuner.core.m3u_import import load_station_collection

    path = tmp_path / "test.PLS"
    path.write_bytes(b"[playlist]\nFile1=https://example.org/one\n")
    assert len(load_station_collection(path).entries) == 1
    path.write_bytes(b"File1=https://example.org/one\n")
    with pytest.raises(ValueError, match="begin with"):
        load_station_collection(path)
