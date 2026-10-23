# SPDX-License-Identifier: MIT

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from fluxtuner.core import db
from fluxtuner.core.discovery_execution import search_desktop_stations
from fluxtuner.core.search_service import SearchRequest, SearchResult


def test_local_search_reads_existing_profile_without_writing(tmp_path):
    path = tmp_path / "library.db"
    db.init_db(path)

    with db.connect(path) as conn:
        before = conn.total_changes
        count_before = conn.execute("SELECT count(*) FROM profiles").fetchone()[0]

    result = search_desktop_stations(
        SearchRequest(query="missing", source="local"),
        db_path=path,
    )

    with db.connect(path) as conn:
        count_after = conn.execute("SELECT count(*) FROM profiles").fetchone()[0]

    assert result.stations == []
    assert count_after == count_before
    assert before == 0


def test_missing_database_is_not_created(tmp_path):
    path = tmp_path / "missing.db"

    with pytest.raises(sqlite3.OperationalError):
        search_desktop_stations(SearchRequest(source="local"), db_path=path)

    assert not path.exists()


def test_missing_local_profile_is_rejected(tmp_path):
    path = tmp_path / "library.db"
    db.init_db(path)

    with pytest.raises(ValueError, match="profile is unavailable"):
        search_desktop_stations(
            SearchRequest(source="local"),
            profile_name="does-not-exist",
            db_path=path,
        )


def test_invalid_source_is_rejected_before_database_access(tmp_path):
    with pytest.raises(ValueError, match="Unknown station discovery source"):
        search_desktop_stations(
            SearchRequest(source="invalid"),  # type: ignore[arg-type]
            db_path=tmp_path / "missing.db",
        )


def test_local_search_owns_connection_in_worker_thread(tmp_path):
    path = tmp_path / "library.db"
    db.init_db(path)

    with ThreadPoolExecutor(max_workers=1) as pool:
        result = pool.submit(
            search_desktop_stations,
            SearchRequest(source="local"),
            db_path=path,
        ).result()

    assert result.stations == []
    assert result.remote_status == "unknown"


def test_remote_search_does_not_open_sqlite(monkeypatch, tmp_path):
    from fluxtuner.core import discovery_execution

    def forbidden_connection(*args, **kwargs):
        raise AssertionError("Radio Browser must not open SQLite")

    def fake_search(self, request):
        assert request.source == "radio-browser"
        return SearchResult(stations=[])

    monkeypatch.setattr(discovery_execution.sqlite3, "connect", forbidden_connection)
    monkeypatch.setattr(discovery_execution.SearchService, "search", fake_search)

    result = search_desktop_stations(
        SearchRequest(query="jazz"),
        db_path=tmp_path / "does-not-exist.db",
    )
    assert result.stations == []


def test_local_worker_closes_connection_on_search_error(monkeypatch, tmp_path):
    from fluxtuner.core import discovery_execution

    path = tmp_path / "library.db"
    db.init_db(path)

    real_connect = sqlite3.connect
    opened = []

    def tracked_connect(*args, **kwargs):
        conn = real_connect(*args, **kwargs)
        opened.append(conn)
        return conn

    def failing_search(self, request):
        assert request.source == "local"
        raise RuntimeError("simulated search failure")

    monkeypatch.setattr(discovery_execution.sqlite3, "connect", tracked_connect)
    monkeypatch.setattr(discovery_execution.SearchService, "search", failing_search)

    with pytest.raises(RuntimeError, match="simulated search failure"):
        search_desktop_stations(
            SearchRequest(source="local"),
            db_path=path,
        )

    assert len(opened) == 1
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        opened[0].execute("SELECT 1")
