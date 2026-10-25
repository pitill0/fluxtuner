# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC

"""Regression contracts for FluxTuner Web Account navigation."""

from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app


def _static(path: str) -> str:
    response = TestClient(create_app()).get(path)
    assert response.status_code == 200
    return response.text


def test_account_navigation_and_private_panel_exist() -> None:
    page = _static("/")

    assert "data-nav-account data-private-action disabled" in page
    assert "data-account-panel hidden" in page
    assert 'aria-labelledby="account-title"' in page
    assert "data-account-username" in page
    assert "Security" in page


def test_recovery_action_moves_from_header_to_account() -> None:
    page = _static("/")

    header = page.split("</header>", 1)[0]
    account = page.split("data-account-panel hidden", 1)[1]
    account = account.split("data-dashboard-panel", 1)[0]

    assert "data-recovery-codes-regenerate-open" not in header
    assert "data-recovery-codes-regenerate-open" in account
    assert page.count("data-recovery-codes-regenerate-open") == 1
    assert "invalidates" in account.lower()


def test_account_elements_are_registered() -> None:
    module = _static("/static/js/app-elements.js")

    assert 'root.querySelector("[data-nav-account]")' in module
    assert 'root.querySelector("[data-account-panel]")' in module
    assert 'root.querySelector("[data-account-username]")' in module


def test_account_view_is_exclusive() -> None:
    module = _static("/static/js/ui-shell.js")

    assert "function showAccountView()" in module
    assert "accountPanel.hidden = false;" in module
    assert "accountPanel.hidden = true;" in module


def test_account_navigation_requires_authentication() -> None:
    module = _static("/static/js/navigation.js")

    assert "function navigateToAccount()" in module
    assert "appState.isAuthenticated()" in module
    assert "showAccountView();" in module
    assert "scrollToSection(accountPanel);" in module


def test_account_navigation_is_wired_through_app() -> None:
    app = _static("/static/app.js")
    events = _static("/static/js/app-events.js")

    assert "navAccountButton" in app
    assert "accountPanel" in app
    assert "accountUsernameNode" in app
    assert "navigateToAccount" in app
    assert 'navAccountButton.addEventListener("click", navigateToAccount);' in events


def test_account_username_and_logout_state_are_synchronized() -> None:
    module = _static("/static/js/session-ui.js")

    assert "accountUsernameNode.textContent" in module
    assert "accountPanel.hidden = true;" in module


def test_recovery_code_controller_is_reused() -> None:
    events = _static("/static/js/app-events.js")
    controller = _static("/static/js/account-requests.js")

    assert "accountRequestsController.openRecoveryCodeRegenerationDialog" in events
    assert "accountRequestsController.regenerateRecoveryCodes" in events
    assert "function openRecoveryCodeRegenerationDialog()" in controller
    assert "async function regenerateRecoveryCodes(event)" in controller


def test_recovery_dialog_stacks_above_header() -> None:
    css = _static("/static/dialogs.css")

    assert (
        ".recovery-codes-dialog,\n"
        "[data-recovery-codes-regenerate-dialog] {\n"
        "  z-index: 100;\n"
        "}" in css
    )


def test_account_styling_has_responsive_rules() -> None:
    css = _static("/static/shell.css")

    assert ".account-panel" in css
    assert ".account-security" in css
