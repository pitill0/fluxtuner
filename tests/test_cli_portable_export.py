"""CLI integration tests for portable playlist exports."""

from __future__ import annotations

import sys

import pytest

from fluxtuner import __main__ as cli
from fluxtuner.core import db
from fluxtuner.core.m3u_import import parse_m3u, parse_pls


@pytest.fixture
def library(tmp_path, monkeypatch):
    path = tmp_path / "library.db"
    monkeypatch.setattr(db, "DB_FILE", path)
    db.init_db(path)
    with db.connect(path) as conn:
        user = conn.execute(
            "SELECT id FROM users WHERE username = ?",
            (db.DEFAULT_USER_NAME,),
        ).fetchone()[0]
        profile = db.ensure_default_profile(conn, user_id=int(user))
        db.create_playlist_record(conn, "Morning", profile_id=profile)
        db.add_station_to_playlist_record(
            conn,
            "Morning",
            {"name": "Jazz", "url": "https://radio.example/jazz"},
            profile_id=profile,
        )
        conn.commit()
    return path


@pytest.mark.parametrize(
    ("option", "parser", "extension"),
    [
        ("--export-playlist-m3u", parse_m3u, "m3u"),
        ("--export-playlist-pls", parse_pls, "pls"),
    ],
)
def test_cli_exports_existing_playlist(library, tmp_path, monkeypatch, option, parser, extension):
    destination = tmp_path / f"morning.{extension}"
    monkeypatch.setattr(sys, "argv", ["fluxtuner", option, "Morning", str(destination)])
    cli.main()
    preview = parser(destination.read_bytes())
    assert [(entry.name, entry.url) for entry in preview.entries] == [
        ("Jazz", "https://radio.example/jazz")
    ]
    assert not preview.issues


def test_cli_does_not_overwrite_existing_file(library, tmp_path, monkeypatch):
    destination = tmp_path / "existing.m3u"
    destination.write_bytes(b"keep me")
    monkeypatch.setattr(
        sys, "argv", ["fluxtuner", "--export-playlist-m3u", "Morning", str(destination)]
    )
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert destination.read_bytes() == b"keep me"


def test_cli_rejects_missing_playlist_without_creating_file(library, tmp_path, monkeypatch):
    destination = tmp_path / "missing.pls"
    monkeypatch.setattr(
        sys, "argv", ["fluxtuner", "--export-playlist-pls", "Missing", str(destination)]
    )
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1
    assert not destination.exists()


def test_cli_missing_library_does_not_initialize_database(tmp_path, monkeypatch):
    database = tmp_path / "missing.db"
    destination = tmp_path / "missing.m3u"
    monkeypatch.setattr(db, "DB_FILE", database)
    monkeypatch.setattr(
        sys, "argv", ["fluxtuner", "--export-playlist-m3u", "Morning", str(destination)]
    )
    with pytest.raises(SystemExit):
        cli.main()
    assert not database.exists()
    assert not destination.exists()


def test_cli_failed_publication_leaves_no_partial_file(library, tmp_path, monkeypatch):
    destination = tmp_path / "failed.m3u"

    def fail_link(source, target):
        raise OSError("Simulated publication failure")

    monkeypatch.setattr(cli.os, "link", fail_link)
    monkeypatch.setattr(
        sys, "argv", ["fluxtuner", "--export-playlist-m3u", "Morning", str(destination)]
    )

    with pytest.raises(SystemExit) as exc:
        cli.main()

    assert exc.value.code == 1
    assert not destination.exists()
    assert list(tmp_path.glob(".fluxtuner-export-*")) == []
