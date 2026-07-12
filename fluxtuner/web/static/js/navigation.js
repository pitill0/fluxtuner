/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createNavigationController({
  accountRequestsController,
  adminPanel,
  appState,
  authPanel,
  checkHealth,
  closeMobileMenu,
  dashboardPanel,
  loadAdminUsersIfNeeded,
  loadDashboard,
  passwordChangeDialog,
  playlistController,
  playlistDialog,
  registerDialog,
  renderAuthRequired,
  resetRadioBrowserView,
  scrollToSection,
  searchPanel,
  showAdminView,
  showRadioBrowserView,
}) {
  function closeOpenDialog() {
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
    navigateToAdmin,
    navigateToDashboard,
    navigateToPrivateView,
    navigateToSearch,
  };
}
