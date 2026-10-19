# SPDX-License-Identifier: MIT

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

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
    original = gtk_m3u_import.import_m3u

    def fail(conn, **kwargs):
        db.create_playlist_record(conn, "Should roll back", profile_id=library.profile_id)
        raise RuntimeError("simulated storage failure")

    monkeypatch.setattr(gtk_m3u_import, "import_m3u", fail)
    with pytest.raises(RuntimeError, match="simulated"):
        session.commit("Jazz", existing=False)
    assert counts() == before

    monkeypatch.setattr(gtk_m3u_import, "import_m3u", original)
    assert session.commit("Jazz", existing=False).added_to_playlist == 2


def test_empty_collection_cannot_open_import_session(library):
    library.path.write_text("#EXTM3U\n", encoding="utf-8")
    before = counts()
    with pytest.raises(ValueError, match="valid stations"):
        prepare(library)
    assert counts() == before


def test_window_menu_action_captures_profile_and_closes_popover(monkeypatch):
    from test_gtk_orchestration import window

    opener = Mock()
    monkeypatch.setattr(window, "open_m3u_import", opener, raising=False)
    harness = SimpleNamespace(
        application_menu_popover=Mock(),
        _playlist_profile_id=Mock(return_value=7),
        _on_m3u_import_saved=Mock(),
        status_label=Mock(),
    )

    window.MainWindow.on_import_stations_clicked(harness, Mock())

    harness.application_menu_popover.popdown.assert_called_once_with()
    assert opener.call_count == 1
    assert opener.call_args.args == (harness,)
    options = opener.call_args.kwargs
    assert options["profile_id"] == 7
    assert options["profile_is_current"]() is True
    harness._playlist_profile_id.return_value = 8
    assert options["profile_is_current"]() is False


def test_window_refreshes_destination_only_after_successful_import():
    from test_gtk_orchestration import window

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

    window.MainWindow._on_m3u_import_saved(harness, "Jazz", result)

    harness._refresh_saved_playlists.assert_called_once_with()
    harness._show_saved_playlist.assert_called_once_with("Jazz")
    assert "2" in harness.status_label.set_text.call_args.args[0]
