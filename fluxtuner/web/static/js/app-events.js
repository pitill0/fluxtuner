/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function bindApplicationEvents({
  accountRequestsController,
  adminCreateUserForm,
  adminLoadUsersButton,
  adminPasswordChangeRequestsNode,
  adminPasswordForm,
  adminUsersNode,
  appHeader,
  checkHealth,
  closeMobileMenu,
  closeOpenDialog,
  createAdminUser,
  createFirstAdmin,
  dashboardActionButtons,
  dashboardRefreshButton,
  documentNode,
  healthButton,
  loadAdminUsers,
  loadDashboard,
  loadFavorites,
  loadFavoritesButton,
  loadHistory,
  loadHistoryButton,
  loadPlaylists,
  loadPlaylistsButton,
  login,
  loginForm,
  logout,
  logoutButton,
  mutateAdminUser,
  mutatePasswordChangeRequest,
  navigateToAdmin,
  navigateToDashboard,
  navigateToPrivateView,
  navigateToSearch,
  navAdminButton,
  navDashboardButton,
  navFavoritesButton,
  navHistoryButton,
  navPlaylistsButton,
  navSearchButton,
  navToggleButton,
  nodeConstructor,
  passwordChangeCancelButtons,
  passwordChangeForm,
  passwordChangeOpenButton,
  playerDebugClearButton,
  playerDebugController,
  playerDebugCopyButton,
  playerDebugDownloadButton,
  playerDebugEnableInput,
  playerDebugToggleButton,
  playlistCancelButtons,
  playlistController,
  playlistForm,
  registerCancelButtons,
  registerForm,
  registerOpenButton,
  searchController,
  searchForm,
  setAdminUserPassword,
  setMobileMenuOpen,
  setupForm,
  themeToggleButton,
  toggleTheme,
  logPlayerEvent,
}) {
  if (adminLoadUsersButton) adminLoadUsersButton.addEventListener("click", loadAdminUsers);
  if (adminCreateUserForm) adminCreateUserForm.addEventListener("submit", createAdminUser);
  if (adminPasswordForm) adminPasswordForm.addEventListener("submit", setAdminUserPassword);

  if (adminUsersNode) {
    adminUsersNode.addEventListener("click", (event) => {
      const button = event.target.closest("[data-admin-user-action]");
      if (!button) return;
      mutateAdminUser(
        button.dataset.adminUsername || "",
        button.dataset.adminUserAction || "",
        button,
      );
    });
  }

  if (adminPasswordChangeRequestsNode) {
    adminPasswordChangeRequestsNode.addEventListener("click", (event) => {
      const button = event.target.closest("[data-admin-password-change-action]");
      if (!button) return;
      mutatePasswordChangeRequest(
        button.dataset.requestId || "",
        button.dataset.adminPasswordChangeAction || "",
      );
    });
  }

  if (playlistForm) playlistForm.addEventListener("submit", playlistController.submitPlaylistDialog);
  playlistCancelButtons.forEach((button) => {
    button.addEventListener("click", playlistController.closePlaylistDialog);
  });

  if (setupForm) setupForm.addEventListener("submit", createFirstAdmin);
  if (loginForm) loginForm.addEventListener("submit", login);

  if (registerOpenButton) {
    registerOpenButton.addEventListener("click", accountRequestsController.openRegisterDialog);
  }
  if (passwordChangeOpenButton) {
    passwordChangeOpenButton.addEventListener(
      "click",
      accountRequestsController.openPasswordChangeDialog,
    );
  }
  passwordChangeCancelButtons.forEach((button) => {
    button.addEventListener("click", accountRequestsController.closePasswordChangeDialog);
  });
  if (passwordChangeForm) {
    passwordChangeForm.addEventListener(
      "submit",
      accountRequestsController.requestPasswordChange,
    );
  }
  registerCancelButtons.forEach((button) => {
    button.addEventListener("click", accountRequestsController.closeRegisterDialog);
  });
  if (registerForm) {
    registerForm.addEventListener("submit", accountRequestsController.registerAccount);
  }

  if (logoutButton) logoutButton.addEventListener("click", logout);
  if (healthButton) healthButton.addEventListener("click", checkHealth);
  if (playerDebugToggleButton) {
    playerDebugToggleButton.addEventListener("click", playerDebugController.toggleDetails);
  }
  if (playerDebugCopyButton) {
    playerDebugCopyButton.addEventListener("click", playerDebugController.copyLog);
  }
  if (playerDebugClearButton) {
    playerDebugClearButton.addEventListener("click", playerDebugController.clearLog);
  }
  if (playerDebugDownloadButton) {
    playerDebugDownloadButton.addEventListener("click", playerDebugController.downloadLog);
  }

  if (navToggleButton) {
    navToggleButton.addEventListener("click", () => {
      const isOpen = appHeader?.dataset.mobileMenuOpen === "true";
      setMobileMenuOpen(!isOpen);
    });
  }

  documentNode.addEventListener("click", (event) => {
    if (!appHeader || appHeader.dataset.mobileMenuOpen !== "true") return;
    if (event.target instanceof nodeConstructor && appHeader.contains(event.target)) return;
    closeMobileMenu();
  });

  documentNode.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      if (closeOpenDialog()) return;
      closeMobileMenu();
    }
  });

  if (themeToggleButton) themeToggleButton.addEventListener("click", toggleTheme);
  if (navDashboardButton) navDashboardButton.addEventListener("click", navigateToDashboard);
  if (dashboardRefreshButton) dashboardRefreshButton.addEventListener("click", loadDashboard);

  dashboardActionButtons.forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.getAttribute("data-dashboard-action");
      if (action === "search") navigateToSearch();
      else if (action === "favorites") await navigateToPrivateView(loadFavorites);
      else if (action === "playlists") await navigateToPrivateView(loadPlaylists);
      else if (action === "history") await navigateToPrivateView(loadHistory);
      else if (action === "admin" && navAdminButton) navAdminButton.click();
    });
  });

  if (navSearchButton) navSearchButton.addEventListener("click", navigateToSearch);
  if (navFavoritesButton) {
    navFavoritesButton.addEventListener("click", () => navigateToPrivateView(loadFavorites));
  }
  if (navPlaylistsButton) {
    navPlaylistsButton.addEventListener("click", () => navigateToPrivateView(loadPlaylists));
  }
  if (navHistoryButton) {
    navHistoryButton.addEventListener("click", () => navigateToPrivateView(loadHistory));
  }
  if (navAdminButton) navAdminButton.addEventListener("click", navigateToAdmin);
  if (searchForm) searchForm.addEventListener("submit", searchController.searchStations);
  if (loadHistoryButton) loadHistoryButton.addEventListener("click", loadHistory);
  if (loadFavoritesButton) loadFavoritesButton.addEventListener("click", loadFavorites);
  if (loadPlaylistsButton) loadPlaylistsButton.addEventListener("click", loadPlaylists);

  if (playerDebugEnableInput) {
    playerDebugEnableInput.addEventListener("change", () => {
      playerDebugController.applyState(playerDebugEnableInput.checked);
      logPlayerEvent("player-debug-toggle", { enabled: playerDebugController.enabled });
    });
  }
}
