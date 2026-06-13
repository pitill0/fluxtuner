from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from fluxtuner.core.stations import station_codec, station_name, station_url
from fluxtuner.players.capabilities import PlayerCapabilities

_CODEC_ALIASES = {
    "mpeg": "mp3",
    "mpeg audio": "mp3",
    "mpeg layer 3": "mp3",
    "mpeg-1 layer 3": "mp3",
    "mp3": "mp3",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/x-mpeg": "mp3",
    "aac": "aac",
    "aac+": "aac",
    "heaac": "aac",
    "he-aac": "aac",
    "audio/aac": "aac",
    "ogg": "ogg",
    "application/ogg": "ogg",
    "audio/ogg": "ogg",
    "vorbis": "vorbis",
    "audio/vorbis": "vorbis",
    "opus": "opus",
    "audio/opus": "opus",
    "flac": "flac",
    "audio/flac": "flac",
    "m3u8": "hls",
    "hls": "hls",
    "application/vnd.apple.mpegurl": "hls",
    "application/x-mpegurl": "hls",
}


def normalize_codec(value: Any) -> str | None:
    """Normalize station codec or MIME metadata to a compact codec key."""
    if value is None:
        return None

    clean_value = str(value).strip().lower()
    if not clean_value or clean_value == "?":
        return None

    clean_value = clean_value.split(";", 1)[0].strip()
    clean_value = clean_value.replace("_", "-")

    if clean_value in _CODEC_ALIASES:
        return _CODEC_ALIASES[clean_value]

    compact = clean_value.replace("-", "").replace(" ", "")
    if compact in _CODEC_ALIASES:
        return _CODEC_ALIASES[compact]

    if "mp3" in compact or compact == "mpeg":
        return "mp3"
    if "aac" in compact:
        return "aac"
    if "vorbis" in compact:
        return "vorbis"
    if "opus" in compact:
        return "opus"
    if "ogg" in compact:
        return "ogg"
    if "flac" in compact:
        return "flac"
    if "m3u8" in compact or "mpegurl" in compact:
        return "hls"

    return clean_value


def station_codec_candidates(station: dict[str, Any] | None) -> set[str]:
    """Return normalized codec candidates from station metadata and URL hints."""
    if not station:
        return set()

    candidates: set[str] = set()
    metadata_keys = ("codec", "content_type", "content-type", "mime_type", "mimetype")

    for key in metadata_keys:
        normalized = normalize_codec(station.get(key))
        if normalized:
            candidates.add(normalized)

    normalized_display_codec = normalize_codec(station_codec(station))
    if normalized_display_codec:
        candidates.add(normalized_display_codec)

    url = station_url(station)
    if url:
        path = urlparse(url).path.lower()
        if path.endswith(".mp3"):
            candidates.add("mp3")
        elif path.endswith(".ogg") or path.endswith(".oga"):
            candidates.add("ogg")
        elif path.endswith(".opus"):
            candidates.add("opus")
        elif path.endswith(".flac"):
            candidates.add("flac")
        elif path.endswith(".m3u8"):
            candidates.add("hls")

    return candidates


def station_is_supported(station: dict[str, Any] | None, capabilities: PlayerCapabilities) -> bool:
    """Return True when a station is compatible with the active backend."""
    if capabilities.general_purpose:
        return True

    candidates = station_codec_candidates(station)
    if not candidates:
        return False

    return bool(candidates & capabilities.supported_codecs)


def filter_supported_stations(
    stations: list[dict[str, Any]],
    capabilities: PlayerCapabilities,
) -> list[dict[str, Any]]:
    """Return only stations compatible with the active backend."""
    if capabilities.general_purpose:
        return stations
    return [station for station in stations if station_is_supported(station, capabilities)]


def unsupported_station_message(station: dict[str, Any] | None, backend_name: str) -> str:
    name = station_name(station)
    return (
        f"{name} is not supported by the active backend: {backend_name}. "
        "Try mpv or ffplay for broader stream compatibility."
    )
