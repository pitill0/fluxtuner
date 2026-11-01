# SPDX-License-Identifier: MIT

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from gtk_library_helpers import bind_library_harness

from fluxtuner.core import db
from fluxtuner.core.custom_stations import add_custom_station
from fluxtuner.core.profiles import get_or_create_profile
from fluxtuner.gui import gtk_m3u_import


@pytest.fixture
def library(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    db.init_db()
    with db.connect() as conn:
        profile_id = db.ensure_default_profile(conn)
        other_id = get_or_create_profile(conn, "Other")
        db.create_playlist_record(conn, "Morning", profile_id=profile_id)
        db.create_playlist_record(conn, "Other only", profile_id=other_id)
        add_custom_station(
            conn,
            profile_id=profile_id,
            name="Existing personal name",
            url="https://one.example/live",
        )
        conn.commit()
    path = tmp_path / "Jazz.m3u"
    path.write_text(
        "#EXTM3U\n#EXTINF:-1,Imported name\nhttps://one.example/live\n"
        "#EXTINF:-1,New radio\nhttps://two.example/live\n",
        encoding="utf-8",
    )
    return SimpleNamespace(path=path, profile_id=profile_id, other_id=other_id)


def prepare(library, *, profile_is_current=lambda: True):
    return gtk_m3u_import.prepare_m3u_import(
        library.path,
        profile_id=library.profile_id,
        profile_is_current=profile_is_current,
    )


def counts():
    with db.connect() as conn:
        return tuple(
            conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("stations", "favorites", "playlists", "playlist_stations")
        )


def test_preview_does_not_write_and_only_offers_current_profile_playlists(library):
    before = counts()
    session = prepare(library)
    assert counts() == before
    assert session.playlist_names == ("Morning",)
    assert session.source_name == "Jazz.m3u"
    assert len(session.preview.entries) == 2
    assert session.existing_urls == frozenset({"https://one.example/live"})


def test_cancel_does_not_write_and_prevents_later_submission(library):
    before = counts()
    session = prepare(library)
    session.cancel()
    assert counts() == before
    with pytest.raises(ValueError, match="closed"):
        session.commit("Jazz", existing=False)
    assert counts() == before


def test_new_playlist_import_commits_and_finishes_session(library):
    session = prepare(library)
    result = session.commit("Jazz", existing=False)
    assert result.added_favorites == 1
    assert result.existing_favorites == 1
    assert result.added_to_playlist == 2
    with db.connect() as conn:
        playlist = db.get_playlist_record(conn, "Jazz", profile_id=library.profile_id)
        assert playlist["station_keys"] == [
            "https://one.example/live",
            "https://two.example/live",
        ]
        assert db.get_playlist_record(conn, "Jazz", profile_id=library.other_id) is None
    with pytest.raises(ValueError, match="closed"):
        session.commit("Jazz", existing=False)


def test_existing_playlist_import_uses_selected_destination(library):
    session = prepare(library)
    result = session.commit("Morning", existing=True)
    assert result.added_to_playlist == 2
    with db.connect() as conn:
        assert (
            len(
                db.get_playlist_record(conn, "Morning", profile_id=library.profile_id)[
                    "station_keys"
                ]
            )
            == 2
        )


def test_deleted_destination_is_not_recreated(library):
    session = prepare(library)
    with db.connect() as conn:
        db.delete_playlist_record(conn, "Morning", profile_id=library.profile_id)
        conn.commit()
    before = counts()
    with pytest.raises(ValueError, match="no longer exists"):
        session.commit("Morning", existing=True)
    assert counts() == before


def test_unoffered_destination_is_rejected(library):
    session = prepare(library)
    before = counts()
    with pytest.raises(ValueError, match="offered"):
        session.commit("Other only", existing=True)
    assert counts() == before


def test_new_destination_cannot_silently_merge_into_existing_playlist(library):
    session = prepare(library)
    before = counts()
    with pytest.raises(ValueError, match="already exists"):
        session.commit("morning", existing=False)
    assert counts() == before


def test_profile_change_rejects_save_without_writing(library):
    state = {"current": True}
    session = prepare(library, profile_is_current=lambda: state["current"])
    state["current"] = False
    before = counts()
    with pytest.raises(ValueError, match="profile changed"):
        session.commit("Jazz", existing=False)
    assert counts() == before


def test_storage_failure_rolls_back_and_leaves_session_retryable(library, monkeypatch):
    session = prepare(library)
    before = counts()
    original = gtk_m3u_import.import_m3u_with_new_source

    def fail(conn, **kwargs):
        db.create_playlist_record(conn, "Should roll back", profile_id=library.profile_id)
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(gtk_m3u_import, "import_m3u_with_new_source", fail)
    with pytest.raises(RuntimeError, match="simulated"):
        session.commit("Jazz", existing=False)
    assert counts() == before

    monkeypatch.setattr(gtk_m3u_import, "import_m3u_with_new_source", original)
    assert session.commit("Jazz", existing=False).added_to_playlist == 2


def test_empty_collection_cannot_open_import_session(library):
    library.path.write_text("#EXTM3U\n", encoding="utf-8")
    before = counts()
    with pytest.raises(ValueError, match="valid stations"):
        prepare(library)
    assert counts() == before


def test_window_menu_action_captures_profile_and_closes_popover(monkeypatch):
    import test_gtk_orchestration

    from fluxtuner.gui import gtk_library_panel as library_panel

    assert test_gtk_orchestration.window.MainWindow is not None

    opener = Mock()
    monkeypatch.setattr(library_panel, "open_m3u_import", opener, raising=False)
    harness = SimpleNamespace(
        application_menu_popover=Mock(),
        _playlist_profile_id=Mock(return_value=7),
        _on_m3u_import_saved=Mock(),
        status_label=Mock(),
    )

    library_panel.LibraryPanel.on_import_stations_clicked(bind_library_harness(harness), Mock())

    harness.application_menu_popover.popdown.assert_called_once_with()
    assert opener.call_count == 1
    assert opener.call_args.args == (harness,)
    options = opener.call_args.kwargs
    assert options["profile_id"] == 7
    assert options["profile_is_current"]() is True
    harness._playlist_profile_id.return_value = 8
    assert options["profile_is_current"]() is False


def test_window_refreshes_destination_only_after_successful_import():
    import test_gtk_orchestration

    from fluxtuner.gui import gtk_library_panel as library_panel

    assert test_gtk_orchestration.window.MainWindow is not None

    harness = SimpleNamespace(
        _refresh_saved_playlists=Mock(),
        _show_saved_playlist=Mock(),
        status_label=Mock(),
    )
    result = SimpleNamespace(
        added_favorites=1,
        existing_favorites=1,
        added_to_playlist=2,
        already_in_playlist=0,
    )

    library_panel.LibraryPanel._on_m3u_import_saved(bind_library_harness(harness), "Jazz", result)

    harness._refresh_saved_playlists.assert_called_once_with()
    harness._show_saved_playlist.assert_called_once_with("Jazz")
    assert "2" in harness.status_label.set_text.call_args.args[0]


def test_remote_preview_reuses_session_and_does_not_write(library, monkeypatch):
    before = counts()
    local = prepare(library)
    calls = []

    def fake_download(url, resolver):
        calls.append(url)
        return b"ignored", local.preview

    monkeypatch.setattr(gtk_m3u_import, "preview_remote_station_collection", fake_download)
    session = gtk_m3u_import.prepare_remote_m3u_import(
        "https://catalog.example/lists/Jazz.m3u",
        profile_id=library.profile_id,
        profile_is_current=lambda: True,
    )
    assert counts() == before
    assert session.preview is local.preview
    assert session.source_name == "Jazz.m3u"
    assert session.playlist_names == ("Morning",)
    assert calls == ["https://catalog.example/lists/Jazz.m3u"]

    monkeypatch.setattr(
        gtk_m3u_import,
        "preview_remote_station_collection",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("refetched")),
    )
    assert session.commit("Remote Jazz", existing=False).added_to_playlist == 2
    assert counts() != before


def test_remote_profile_change_prevents_download(library, monkeypatch):
    called = []
    monkeypatch.setattr(
        gtk_m3u_import,
        "preview_remote_station_collection",
        lambda *_args, **_kwargs: called.append(True),
    )
    with pytest.raises(ValueError, match="profile changed"):
        gtk_m3u_import.prepare_remote_m3u_import(
            "https://catalog.example/jazz.m3u",
            profile_id=library.profile_id,
            profile_is_current=lambda: False,
        )
    assert called == []


def test_remote_preview_rejects_changed_profile_after_download(library, monkeypatch):
    preview = prepare(library).preview
    state = {"current": True}

    def fake_download(url, resolver):
        state["current"] = False
        return b"ignored", preview

    monkeypatch.setattr(gtk_m3u_import, "preview_remote_station_collection", fake_download)
    with pytest.raises(ValueError, match="profile changed"):
        gtk_m3u_import.prepare_remote_m3u_import(
            "https://catalog.example/jazz.m3u",
            profile_id=library.profile_id,
            profile_is_current=lambda: state["current"],
        )


def test_window_remote_menu_captures_profile(monkeypatch):
    import test_gtk_orchestration

    from fluxtuner.gui import gtk_library_panel as library_panel

    assert test_gtk_orchestration.window.MainWindow is not None

    opener = Mock()
    monkeypatch.setattr(library_panel, "open_remote_m3u_import", opener, raising=False)
    harness = SimpleNamespace(
        application_menu_popover=Mock(),
        _playlist_profile_id=Mock(return_value=7),
        _on_m3u_import_saved=Mock(),
        status_label=Mock(),
    )
    library_panel.LibraryPanel.on_import_stations_url_clicked(bind_library_harness(harness), Mock())
    harness.application_menu_popover.popdown.assert_called_once_with()
    assert opener.call_count == 1
    assert opener.call_args.kwargs["profile_id"] == 7
    harness._playlist_profile_id.return_value = 8
    assert opener.call_args.kwargs["profile_is_current"]() is False


def test_local_commit_persists_profile_scoped_provenance(library):
    session = prepare(library)
    assert session.local_source is True

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM station_sources").fetchone()[0] == 0

    result = session.commit("Jazz", existing=False)
    assert result.added_to_playlist == 2

    with db.connect() as conn:
        sources = conn.execute(
            "SELECT id, profile_id, kind, display_name FROM station_sources"
        ).fetchall()
        assert len(sources) == 1
        assert sources[0]["profile_id"] == library.profile_id
        assert sources[0]["kind"] == "local_collection"
        assert sources[0]["display_name"] is None
        assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 2


def test_remote_commit_records_remote_provenance(library, monkeypatch):
    preview = prepare(library).preview
    monkeypatch.setattr(
        gtk_m3u_import,
        "preview_remote_station_collection",
        lambda *_args, **_kwargs: (b"snapshot", preview),
    )
    session = gtk_m3u_import.prepare_remote_m3u_import(
        "https://catalog.example/jazz.m3u",
        profile_id=library.profile_id,
        profile_is_current=lambda: True,
    )
    assert session.local_source is False
    assert session.remote_source is True

    session.commit("Remote Jazz", existing=False)

    with db.connect() as conn:
        sources = conn.execute(
            "SELECT profile_id, kind, display_name FROM station_sources"
        ).fetchall()
        assert len(sources) == 1
        assert sources[0]["profile_id"] == library.profile_id
        assert sources[0]["kind"] == "remote_collection"
        assert sources[0]["display_name"] is None
        assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 2


def test_local_cancel_creates_no_provenance(library):
    session = prepare(library)
    session.cancel()

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM station_sources").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM station_source_memberships").fetchone()[0] == 0
