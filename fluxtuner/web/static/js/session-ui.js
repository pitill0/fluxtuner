/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createSessionUiController({
  presentation,
  recommendationController,
  subscriptionController,
  stationImportController,
  customStationController,
  accountRequestsController,
  adminController,
  appState,
  authMessageNode,
  authPanel,
  authUserPanel,
  authUsernameNode,
  accountPanel,
  accountUsernameNode,
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
  function presentMessage(node, message, key, params = {}) {
    if (!node) return;
    if (key && presentation) presentation.present(node, key, message, "textContent", params);
    else {
      presentation?.clear(node);
      node.textContent = message || "";
    }
  }

  function updateAuthUi() {
    recommendationController?.syncSession();
    stationImportController?.syncSession();
    subscriptionController?.syncSession();
    customStationController?.syncSession();
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

    if (
      authenticated && !showAdminPanel && searchPanel && searchPanel.hidden &&
      !(accountPanel && !accountPanel.hidden)
    ) {
      showRadioBrowserView();
    }

    if (adminPanel && !showAdminPanel) {
      adminPanel.hidden = true;
    }

    if (accountPanel && (!authenticated || setupAvailable)) {
      accountPanel.hidden = true;
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

    if (accountUsernameNode) {
      accountUsernameNode.textContent = authenticated
        ? currentUser?.username || ""
        : "";
    }

    privateActionNodes.forEach((node) => {
      node.disabled = !authenticated;
    });

    if (authMessageNode) {
      authMessageNode.hidden = !authenticated;
      if (authenticated) presentMessage(authMessageNode, "Private library tools are available.", "session.private_tools");
      else presentMessage(authMessageNode, "");
    }
  }

  function renderAuthRequired() {
    if (resultsNode && resultCountNode) {
      presentMessage(resultCountNode, "Login required.", "session.login_required");
      resultsNode.innerHTML =
        '<p class="empty">Sign in to use favorites, history and playlists.</p>';
    }

    if (authMessageNode) {
      authMessageNode.hidden = false;
      presentMessage(authMessageNode, "Session expired or login required.", "session.expired");
    }
  }

  return { renderAuthRequired, updateAuthUi };
}
