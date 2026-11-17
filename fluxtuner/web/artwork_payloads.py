# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Attach temporary artwork references to authenticated station responses."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

from fluxtuner.web.artwork_tokens import issue_artwork_reference


def with_artwork_references(
    payload: dict[str, Any], session_token: str, signing_key: bytes
) -> dict[str, Any]:
    """Decorate stations without changing persistent or shared discovery data."""
    if not session_token or not isinstance(payload.get("stations"), list):
        return payload

    stations = []
    for station in payload["stations"]:
        if not isinstance(station, dict):
            stations.append(station)
            continue
        copy = dict(station)
        favicon = copy.get("favicon")
        if isinstance(favicon, str) and favicon:
            with suppress(ValueError):
                copy["artwork_ref"] = issue_artwork_reference(favicon, session_token, signing_key)
        stations.append(copy)
    return {**payload, "stations": stations}
