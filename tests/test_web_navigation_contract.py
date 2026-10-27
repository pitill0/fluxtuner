"""Contract checks for the planned FluxTuner Web navigation architecture."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCUMENT = ROOT / "docs/web-navigation-architecture.md"


def architecture() -> str:
    return DOCUMENT.read_text(encoding="utf-8")


def test_primary_destinations_are_defined() -> None:
    content = architecture()
    for destination in (
        "Dashboard",
        "Explore",
        "My Library",
        "Account",
        "Administration",
    ):
        assert f"| {destination} |" in content


def test_library_destinations_are_defined() -> None:
    content = architecture()
    for destination in (
        "Favorites",
        "Playlists",
        "My Stations",
        "Remote Catalogs",
        "History",
    ):
        assert f"| {destination} |" in content


def test_contextual_actions_are_not_destinations() -> None:
    content = architecture()
    section = content.split("### Contextual actions", maxsplit=1)[1].split("## 3.", maxsplit=1)[0]

    for action in (
        "Add station",
        "Import stations",
        "Create playlist",
        "Subscribe to remote catalog",
    ):
        assert f"- {action}" in section

    for action in ("Add station", "Import stations"):
        assert f"| {action} |" not in content


def test_navigation_and_player_are_independent() -> None:
    content = architecture()
    assert "Player runtime state is independent" in content
    assert "Normal navigation does not restart audio playback." in content


def test_mobile_and_desktop_contracts_exist() -> None:
    content = architecture()
    assert "Collapsible sidebar" in content
    assert "maximum of two menu levels" in content
    assert "Focus is restored" in content
    assert "Escape closes the drawer" in content


def test_security_and_history_contracts_exist() -> None:
    content = architecture()
    for requirement in (
        "Back and Forward",
        "Deep links must not bypass authentication",
        "Logout clears access",
        "Stale asynchronous results",
        "Administration is only available",
    ):
        assert requirement in content


def test_acceptance_matrix_covers_critical_regressions() -> None:
    content = architecture()
    for scenario in (
        "Desktop navigation",
        "Mobile drawer",
        "Browser Back",
        "Browser Forward",
        "Playback",
        "Logout",
        "Admin access",
        "Catalog detail",
        "Recovery dialogs",
        "Mobile layout",
    ):
        assert f"| {scenario} |" in content
