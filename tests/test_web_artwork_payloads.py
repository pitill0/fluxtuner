"""Signed artwork references are response-only, not persisted station metadata."""

from __future__ import annotations

from fluxtuner.web.artwork_payloads import with_artwork_references
from fluxtuner.web.artwork_tokens import verify_artwork_reference

KEY = b"private-server-key-for-artwork-signatures-32"
FAVICON = "https://radio.example/station.png"


def test_decorates_without_mutating_station_payloads() -> None:
    payload = {
        "count": 2,
        "stations": [{"name": "Valid", "favicon": FAVICON}, {"name": "No logo", "favicon": ""}],
    }
    decorated = with_artwork_references(payload, "session-a", KEY)
    assert "artwork_ref" not in payload["stations"][0]
    assert decorated["count"] == 2
    assert "artwork_ref" not in decorated["stations"][1]
    assert (
        verify_artwork_reference(decorated["stations"][0]["artwork_ref"], "session-a", KEY)
        == FAVICON
    )


def test_refs_change_per_session_but_source_is_shared() -> None:
    payload = {"stations": [{"favicon": FAVICON}]}
    first = with_artwork_references(payload, "session-a", KEY)["stations"][0]["artwork_ref"]
    second = with_artwork_references(payload, "session-b", KEY)["stations"][0]["artwork_ref"]
    assert first != second
    assert verify_artwork_reference(first, "session-a", KEY) == FAVICON
    assert verify_artwork_reference(second, "session-b", KEY) == FAVICON


def test_skips_unusable_favicons_and_missing_sessions() -> None:
    payload = {
        "stations": [
            {"favicon": "file:///etc/passwd"},
            {"favicon": "https://user:pass@radio.example/icon.png"},
            {"favicon": None},
        ]
    }
    decorated = with_artwork_references(payload, "session-a", KEY)
    assert all("artwork_ref" not in item for item in decorated["stations"])
    assert with_artwork_references(payload, "", KEY) is payload


def test_does_not_change_nonstation_responses() -> None:
    payload = {"status": "ok", "count": 0}
    assert with_artwork_references(payload, "session-a", KEY) is payload
