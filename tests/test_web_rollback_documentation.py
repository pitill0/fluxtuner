# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Guard Web SQLite rollback compatibility documentation."""

from pathlib import Path


def test_release_rollback_requires_matching_database_backup() -> None:
    guide = Path("docs/release.md").read_text(encoding="utf-8")

    assert "## Web database compatibility gate" in guide
    assert "1.5.2 supports schema v5" in guide
    assert "schema v9" in guide
    assert "schema v10 and v11" in guide
    assert "pre-upgrade database snapshot" in guide


def test_deployment_rollback_is_not_image_only() -> None:
    guide = Path("docs/secure-web-deployment.md").read_text(encoding="utf-8")

    assert "## Database migrations and rollback safety" in guide
    assert "Do not roll back by changing only the container image" in guide
    assert "PRAGMA integrity_check" in guide
    assert "Stop the affected application" in guide
    assert "pre-upgrade database and persistent data" in guide
    assert "data-loss window" in guide


def test_160_changelog_warns_about_incompatible_rollback() -> None:
    changelog = Path("CHANGELOG.md").read_text(encoding="utf-8")

    heading = "## [1.6.0] - 2026-11-21"
    assert changelog.count(heading) == 1

    section = changelog.split(heading, 1)[1]
    section = section.split("\\n## [", 1)[0]

    assert "### Upgrade and rollback notice" in section
    assert "schema v5" in section
    assert "schema v9" in section
    assert "pre-upgrade database backup" in section
