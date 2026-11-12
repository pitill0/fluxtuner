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
    rips_directory: Path | None = None,
) -> Path:
    """Return an isolated per-profile/run destination without creating files."""
    if isinstance(profile_id, bool) or not isinstance(profile_id, int) or profile_id <= 0:
        raise RippingError("Ripping profile ID must be a positive integer.")

    if rips_directory is None:
        root = data_directory.expanduser().absolute() / "rips"
    else:
        root = rips_directory.expanduser()
        if not root.is_absolute():
            raise RippingError("Custom ripping directory must be absolute.")

    return root / f"profile-{profile_id}" / run_id.hex
