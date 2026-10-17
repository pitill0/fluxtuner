"""Calculate ripping destinations without filesystem side effects."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

from fluxtuner.core.ripping import RippingError


def ripping_output_directory(
    *,
    data_directory: Path,
    profile_id: int,
    run_id: UUID,
) -> Path:
    """Return a destination for an explicit persistent profile and run."""
    if isinstance(profile_id, bool) or not isinstance(profile_id, int) or profile_id <= 0:
        raise RippingError("Ripping profile ID must be a positive integer.")
    root = data_directory.expanduser().absolute()
    return root / "rips" / f"profile-{profile_id}" / run_id.hex
