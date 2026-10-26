/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createNavigationController({
  accountPanel,
  subscriptionController,
  stationImportController,
  accountRequestsController,
  adminPanel,
  appState,
  authPanel,
  checkHealth,
  closeMobileMenu,
  customStationController,
  dashboardPanel,
  loadAdminUsersIfNeeded,
  loadDashboard,
  passwordChangeDialog,
  recoveryCodesRegenerateDialog,
  playlistController,
  playlistDialog,
  registerDialog,
  renderAuthRequired,
  resetRadioBrowserView,
  scrollToSection,
  searchPanel,
  showAccountView,
  showAdminView,
  showRadioBrowserView,
}) {
  function closeOpenDialog() {
    if (subscriptionController?.closeIfOpen()) return true;
    if (stationImportController?.closeIfOpen()) return true;
    if (customStationController?.closeIfOpen()) return true;

    if (playlistDialog && !playlistDialog.hidden) {
      playlistController.closePlaylistDialog();
      return true;
    }

    if (registerDialog && !registerDialog.hidden) {
      accountRequestsController.closeRegisterDialog();
      return true;
    }

    if (passwordChangeDialog && !passwordChangeDialog.hidden) {
      accountRequestsController.closePasswordChangeDialog();
      return true;
    }

    if (recoveryCodesRegenerateDialog && !recoveryCodesRegenerateDialog.hidden) {
      accountRequestsController.closeRecoveryCodeRegenerationDialog();
      return true;
    }

    return false;
  }

  async function navigateToPrivateView(loader) {
    closeMobileMenu();
    showRadioBrowserView();

    if (!appState.isAuthenticated()) {
      renderAuthRequired();
      scrollToSection(authPanel);
      return;
    }

    await loader();
    scrollToSection(searchPanel);
  }

  async function navigateToDashboard() {
    closeMobileMenu();

    if (!appState.isAuthenticated()) {
      renderAuthRequired();
      scrollToSection(authPanel);
      return;
    }

    await loadDashboard();
    scrollToSection(dashboardPanel);
  }

  function navigateToSearch() {
    closeMobileMenu();
    resetRadioBrowserView();
    scrollToSection(searchPanel);
  }

  function navigateToAccount() {
    closeMobileMenu();
    if (!appState.isAuthenticated() || !accountPanel) {
      renderAuthRequired();
      scrollToSection(authPanel);
      return;
    }
    showAccountView();
    scrollToSection(accountPanel);
  }

  async function navigateToAdmin() {
    closeMobileMenu();

    const currentUser = appState.getCurrentUser();
    if (!currentUser || !currentUser.is_admin || !adminPanel) return;

    showAdminView();
    await checkHealth();
    await loadAdminUsersIfNeeded();
    scrollToSection(adminPanel);
  }

  return {
    closeOpenDialog,
    navigateToAccount,
    navigateToAdmin,
    navigateToDashboard,
    navigateToPrivateView,
    navigateToSearch,
  };
}
