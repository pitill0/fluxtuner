from pathlib import Path
from uuid import UUID

import pytest


def test_output_directory_separates_profiles_and_runs_without_creating_dirs(
    tmp_path: Path,
) -> None:
    from fluxtuner.core.ripping_paths import ripping_output_directory

    data_directory = tmp_path / "app-data"
    first_run = UUID("11111111-1111-4111-8111-111111111111")
    second_run = UUID("22222222-2222-4222-8222-222222222222")

    first = ripping_output_directory(
        data_directory=data_directory,
        profile_id=7,
        run_id=first_run,
    )
    other_profile = ripping_output_directory(
        data_directory=data_directory,
        profile_id=8,
        run_id=first_run,
    )
    other_run = ripping_output_directory(
        data_directory=data_directory,
        profile_id=7,
        run_id=second_run,
    )

    assert first == data_directory / "rips" / "profile-7" / first_run.hex
    assert other_profile == data_directory / "rips" / "profile-8" / first_run.hex
    assert other_run == data_directory / "rips" / "profile-7" / second_run.hex
    assert len({first, other_profile, other_run}) == 3
    assert first.is_absolute()
    assert not data_directory.exists()


@pytest.mark.parametrize("profile_id", [0, -1, True])
def test_output_directory_rejects_invalid_profile_id(tmp_path: Path, profile_id: int) -> None:
    from fluxtuner.core.ripping import RippingError
    from fluxtuner.core.ripping_paths import ripping_output_directory

    data_directory = tmp_path / "app-data"
    with pytest.raises(RippingError, match="positive integer"):
        ripping_output_directory(
            data_directory=data_directory,
            profile_id=profile_id,
            run_id=UUID("11111111-1111-4111-8111-111111111111"),
        )
    assert not data_directory.exists()
