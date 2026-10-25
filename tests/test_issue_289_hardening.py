"""Security regressions for remote import and bidi station names."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi import HTTPException

from fluxtuner.core.custom_stations import _validate_name
from fluxtuner.core.m3u_import import parse_m3u, parse_pls
from fluxtuner.web.routes import imports


class FakeRequest:
    def __init__(self, url: str) -> None:
        self.headers = {"content-type": "application/json"}
        self.data = json.dumps({"url": url}).encode()

    async def stream(self):
        yield self.data


@pytest.mark.parametrize(
    "failure",
    [
        ValueError("Blocked destination: 127.0.0.1"),
        OSError("Connection refused: 192.168.1.1"),
        TimeoutError("Internal DNS lookup timed out"),
        RuntimeError("Resolver failed for internal.example"),
    ],
)
def test_remote_fetch_failures_share_public_response(
    monkeypatch: pytest.MonkeyPatch,
    failure: Exception,
) -> None:
    monkeypatch.setattr(imports, "_authorize", lambda _request: 7)

    def fail(_url, _resolver):
        raise failure

    monkeypatch.setattr(imports, "fetch_remote_station_collection", fail)

    with pytest.raises(HTTPException) as captured:
        asyncio.run(imports.fetch_remote_import(FakeRequest("https://radio.example/stations.m3u")))

    error = captured.value
    assert error.status_code == 502
    assert error.detail == "Could not retrieve the remote collection."


@pytest.mark.parametrize(
    "name",
    [
        "Radio \u202e MP3",
        "Radio \u202d Jazz",
        "Radio \u2066 Live \u2069",
    ],
)
def test_unsafe_bidi_controls_rejected_by_station_validator(
    name: str,
) -> None:
    with pytest.raises(ValueError, match="invalid characters"):
        _validate_name(name)


@pytest.mark.parametrize(
    "name",
    [
        "Radio \u202e MP3",
        "Radio \u2067 Jazz \u2069",
    ],
)
def test_m3u_rejects_unsafe_bidi_station_names(name: str) -> None:
    source = (f"#EXTM3U\n#EXTINF:-1,{name}\nhttps://radio.example/live\n").encode()

    preview = parse_m3u(source)

    assert preview.entries == ()
    assert len(preview.issues) == 1


@pytest.mark.parametrize(
    "name",
    [
        "Radio \u202e MP3",
        "Radio \u2066 Jazz \u2069",
    ],
)
def test_pls_rejects_unsafe_bidi_station_names(name: str) -> None:
    source = (
        "[playlist]\n"
        "NumberOfEntries=1\n"
        "File1=https://radio.example/live\n"
        f"Title1={name}\n"
        "Version=2\n"
    ).encode()

    preview = parse_pls(source)

    assert preview.entries == ()
    assert len(preview.issues) == 1


@pytest.mark.parametrize(
    "name",
    [
        "Ràdio València",
        "إذاعة القاهرة",
        "רדיו ירושלים",
        "東京ラジオ",
    ],
)
def test_legitimate_international_station_names_preserved(
    name: str,
) -> None:
    assert _validate_name(name) == name

    source = (f"#EXTM3U\n#EXTINF:-1,{name}\nhttps://radio.example/live\n").encode()

    preview = parse_m3u(source)
    assert len(preview.entries) == 1
    assert preview.entries[0].name == name


def test_json_favorite_text_removes_unsafe_bidi() -> None:
    from fluxtuner.core.importers import validate_imported_favorite

    url = "https://radio.example/live?token=123"
    favorite = validate_imported_favorite(
        {
            "name": "Radio \u202e Jazz",
            "custom_name": "Mi \u2066 radio \u2069",
            "country": "Espa\u200fña",
            "codec": "MP\u202d3",
            "tags": "jazz,\u202e live",
            "favorite_tags": [
                "No\u202eche",
                "موسيقى",
            ],
            "url": url,
        }
    )

    assert favorite is not None
    assert favorite["name"] == "Radio  Jazz"
    assert favorite["custom_name"] == "Mi  radio "
    assert favorite["country"] == "España"
    assert favorite["codec"] == "MP3"
    assert favorite["tags"] == "jazz, live"
    assert favorite["favorite_tags"] == ["Noche", "موسيقى"]
    assert favorite["url"] == url
    assert favorite["url_resolved"] == url


def test_json_playlist_name_removes_unsafe_bidi() -> None:
    from fluxtuner.core.importers import validate_imported_playlist

    keys = ["https://radio.example/live?channel=1"]
    playlist = validate_imported_playlist({"name": "Ràdio \u202e València", "station_keys": keys})

    assert playlist is not None
    assert playlist["name"] == "Ràdio  València"
    assert playlist["station_keys"] == keys


def test_json_import_preserves_safe_unicode_formatting() -> None:
    from fluxtuner.core.importers import validate_imported_favorite

    name = "रेडियो\u200dभारत"
    favorite = validate_imported_favorite({"name": name, "url": "https://radio.example/live"})

    assert favorite is not None
    assert favorite["name"] == name


def test_m3u_import_playlist_name_rejects_unsafe_bidi(tmp_path) -> None:
    from fluxtuner.core import db
    from fluxtuner.core.m3u_import import import_m3u

    path = tmp_path / "issue-289.db"
    db.init_db(path)

    with db.connect(path) as conn, pytest.raises(ValueError, match="invalid characters"):
        profile_id = db.ensure_default_profile(conn)
        import_m3u(
            conn,
            profile_id=profile_id,
            playlist_name="Morning \u202e Jazz",
            entries=(),
        )
