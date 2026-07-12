/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createSessionUiController({
  accountRequestsController,
  adminController,
  appState,
  authMessageNode,
  authPanel,
  authUserPanel,
  authUsernameNode,
  dashboardPanel,
  isSetupAvailable,
  loginForm,
  navAdminButton,
  playerDebugController,
  privateActionNodes,
  publicEntrySection,
  publicStatsController,
  publicStatsSection,
  registerDialog,
  resultsNode,
  resultCountNode,
  searchPanel,
  setAppContentVisible,
  setPlayerVisible,
  showRadioBrowserView,
  adminPanel,
}) {
  function updateAuthUi() {
    const currentUser = appState.getCurrentUser();
    const authenticated = appState.isAuthenticated();
    const setupAvailable = isSetupAvailable();

    setPlayerVisible(!setupAvailable && authenticated);

    if (publicEntrySection) {
      publicEntrySection.hidden = setupAvailable || authenticated;
    }

    if (authPanel) {
      authPanel.dataset.authenticated = authenticated ? "true" : "false";
      authPanel.hidden = setupAvailable || authenticated;
    }

    if (publicStatsSection) {
      publicStatsSection.hidden = setupAvailable || authenticated;
    }

    if (!setupAvailable && !authenticated) {
      publicStatsController.loadPublicStats();
    }

    setAppContentVisible(!setupAvailable && authenticated);

    const showAdminPanel =
      authenticated && Boolean(currentUser.is_admin) && !setupAvailable;

    if (authenticated && !showAdminPanel && searchPanel && searchPanel.hidden) {
      showRadioBrowserView();
    }

    if (adminPanel && !showAdminPanel) {
      adminPanel.hidden = true;
    }

    if (dashboardPanel && !authenticated) {
      dashboardPanel.hidden = true;
    }

    if (navAdminButton) {
      navAdminButton.hidden = !showAdminPanel;
    }

    playerDebugController.updateVisibility();

    if (!showAdminPanel) {
      adminController.reset();
    }

    if (loginForm) {
      loginForm.hidden = authenticated;
    }

    if (registerDialog && authenticated) {
      accountRequestsController.closeRegisterDialog();
    }

    if (authUserPanel) {
      authUserPanel.hidden = !authenticated;
    }

    if (authUsernameNode) {
      const displayName = currentUser?.display_name || currentUser?.username || "User";
      authUsernameNode.textContent = authenticated ? displayName : "";
    }

    privateActionNodes.forEach((node) => {
      node.disabled = !authenticated;
    });

    if (authMessageNode) {
      authMessageNode.hidden = !authenticated;
      authMessageNode.textContent = authenticated
        ? "Private library tools are available."
        : "";
    }
  }

  function renderAuthRequired() {
    if (resultsNode && resultCountNode) {
      resultCountNode.textContent = "Login required.";
      resultsNode.innerHTML =
        '<p class="empty">Sign in to use favorites, history and playlists.</p>';
    }

    if (authMessageNode) {
      authMessageNode.hidden = false;
      authMessageNode.textContent = "Session expired or login required.";
    }
  }

  return { renderAuthRequired, updateAuthUi };
}
