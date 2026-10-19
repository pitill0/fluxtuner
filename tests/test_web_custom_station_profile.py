# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

from fluxtuner import config
from fluxtuner.core import db, favorites
from fluxtuner.web import context, library


def test_custom_station_is_visible_when_desktop_has_an_active_profile(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_FILE", tmp_path / "fluxtuner.db")
    monkeypatch.setattr(favorites, "FAVORITES_FILE", tmp_path / "favorites.json")
    monkeypatch.setattr(favorites, "LEGACY_FAVORITES_FILE", tmp_path / "missing-legacy.json")
    monkeypatch.setattr(config, "get_config_value", lambda *_args, **_kwargs: "Desktop")
    db.init_db()

    with db.connect() as conn:
        user_id = db.get_or_create_user(conn, "web-listener")
        db.ensure_default_profile(conn, user_id=user_id)
        conn.commit()

    created = library.create_custom_station_payload(
        user_id=user_id,
        profile_name=None,
        name="Personal radio",
        url="https://radio.example/live",
    )
    assert created["added"] is True

    visible = library.favorites_payload(
        user_id=user_id,
        profile_name=context.effective_profile_name(None),
    )
    assert visible["count"] == 1
    assert visible["stations"][0]["name"] == "Personal radio"


def test_web_preserves_explicit_profile_without_using_desktop_selection(
    monkeypatch,
):
    monkeypatch.setattr(config, "get_config_value", lambda *_args, **_kwargs: "Desktop")

    assert context.effective_profile_name(None) is None
    assert context.effective_profile_name(" Work ") == "Work"
    assert context.effective_profile_name("") == ""
