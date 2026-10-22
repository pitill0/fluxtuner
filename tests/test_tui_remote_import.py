# SPDX-License-Identifier: MIT
"""Offline contracts for remote collection imports in the TUI."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from fluxtuner import tui_m3u_import as importer
from fluxtuner.core.m3u_import import M3UImportResult, parse_station_collection

COLLECTION = b"#EXTM3U\n#EXTINF:-1,Remote Example\nhttps://radio.example/live\n"


def _fake_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE profiles (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO profiles (id) VALUES (1)")
    conn.commit()
    return conn


def _mock_library(monkeypatch) -> None:
    monkeypatch.setattr(importer.db, "connect", _fake_connection)
    monkeypatch.setattr(importer.db, "list_playlists", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(importer, "list_favorites", lambda *_args, **_kwargs: [])


def test_remote_url_is_fetched_once_and_previewed(monkeypatch):
    _mock_library(monkeypatch)
    calls = []
    expected = parse_station_collection(COLLECTION)

    def fake_fetch(url, resolver):
        calls.append((url, resolver))
        return COLLECTION, expected

    monkeypatch.setattr(importer, "preview_remote_station_collection", fake_fetch)

    preview, playlists, existing_urls = importer._load_preview(
        "https://radio.example/collection.m3u", 1
    )

    assert preview is expected
    assert playlists == ()
    assert existing_urls == frozenset()
    assert len(calls) == 1
    assert calls[0][0] == "https://radio.example/collection.m3u"


def test_local_file_preserves_existing_loader(monkeypatch):
    _mock_library(monkeypatch)
    calls = []
    expected = parse_station_collection(COLLECTION)

    def fake_local_loader(path):
        calls.append(path)
        return expected

    def unexpected_remote(*_args, **_kwargs):
        raise AssertionError("Local import must not fetch remote content")

    monkeypatch.setattr(importer, "load_m3u_file", fake_local_loader)
    monkeypatch.setattr(importer, "preview_remote_station_collection", unexpected_remote)

    preview, _, _ = importer._load_preview(Path("/tmp/stations.m3u"), 1)

    assert preview is expected
    assert calls == [Path("/tmp/stations.m3u")]


def test_confirmation_uses_captured_preview_without_refetch(monkeypatch):
    _mock_library(monkeypatch)
    preview = parse_station_collection(COLLECTION)
    captured = []

    monkeypatch.setattr(
        importer.db,
        "get_playlist_record",
        lambda *_args, **_kwargs: None,
    )

    def fake_import(conn, *, profile_id, playlist_name, entries):
        captured.append((profile_id, playlist_name, entries))
        return M3UImportResult(1, 0, 1, 0)

    monkeypatch.setattr(importer, "import_m3u", fake_import)

    def unexpected_remote(*_args, **_kwargs):
        raise AssertionError("Confirmation must not download again")

    monkeypatch.setattr(importer, "preview_remote_station_collection", unexpected_remote)

    outcome = importer._save_import(1, preview, "Remote stations", False, lambda: True)

    assert outcome.name == "Remote stations"
    assert captured == [(1, "Remote stations", preview.entries)]
