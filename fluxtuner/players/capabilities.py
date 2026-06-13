from __future__ import annotations

from dataclasses import dataclass, field


def _normalize_values(
    values: frozenset[str] | set[str] | tuple[str, ...] | list[str],
) -> frozenset[str]:
    return frozenset(str(value).strip().lower() for value in values if str(value).strip())


@dataclass(frozen=True)
class PlayerCapabilities:
    """Static playback capabilities declared by a player backend.

    General-purpose backends such as mpv and ffplay are treated as broadly
    compatible with station results. Specialized backends such as mpg123 and
    ogg123 declare the codecs they can reasonably handle so FluxTuner can avoid
    showing or randomly selecting streams that are unlikely to play.
    """

    general_purpose: bool = False
    supports_pause: bool = False
    supports_volume: bool = False
    supports_mute: bool = False
    supported_codecs: frozenset[str] = field(default_factory=frozenset)
    supported_mime_types: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        object.__setattr__(self, "supported_codecs", _normalize_values(self.supported_codecs))
        object.__setattr__(
            self,
            "supported_mime_types",
            _normalize_values(self.supported_mime_types),
        )

    def supports_codec(self, codec: str | None) -> bool:
        """Return True when this backend supports the normalized codec."""
        if self.general_purpose:
            return True
        if not codec:
            return False
        return codec.strip().lower() in self.supported_codecs
