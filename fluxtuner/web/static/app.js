/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { createAccountRequestsController } from "/static/js/account-requests.js";
import { createAdminController } from "/static/js/admin.js";
import { createApiFetch } from "/static/js/api.js";
import { createAppElements } from "/static/js/app-elements.js";
import { createAppState } from "/static/js/app-state.js";
import { createAuthController } from "/static/js/auth.js";
import { createDashboardController } from "/static/js/dashboard.js";
import { createFavoriteController } from "/static/js/favorites.js";
import { createHealthController } from "/static/js/health.js";
import { createLibraryViewsController } from "/static/js/library-views.js";
import { createMediaSessionController } from "/static/js/media-session.js";
import { createPlayerDebugController } from "/static/js/player-debug.js";
import { createPlayerController } from "/static/js/player.js";
import { createPlaylistController } from "/static/js/playlists.js";
import { createPlaylistRenderer } from "/static/js/playlist-renderer.js";
import { createPublicStatsController } from "/static/js/public-stats.js";
import { createSearchController } from "/static/js/search.js";
import { createSessionUiController } from "/static/js/session-ui.js";
import { createSetupController } from "/static/js/setup.js";
import { createThemeController } from "/static/js/theme.js";
import { createUiShellController } from "/static/js/ui-shell.js";
import { createStationRenderer } from "/static/js/station-renderer.js";
import { stationUrl } from "/static/js/stations.js";

const {
  adminCreateUserForm,
  adminLoadUsersButton,
  adminMessageNode,
  adminPanel,
  adminPasswordChangeRequestsNode,
  adminPasswordForm,
  adminUsersNode,
  appContent,
  appContentNodes,
  appHeader,
  audioNode,
  authMessageNode,
  authPanel,
  authUserPanel,
  authUsernameNode,
  dashboardActionButtons,
  dashboardAdminActionButton,
  dashboardAdminMetricsNode,
  dashboardAdminPanel,
  dashboardFavoriteHighlightsNode,
  dashboardMessageNode,
  dashboardPanel,
  dashboardRecentHistoryNode,
  dashboardRefreshButton,
  dashboardUserMetricsNode,
  healthButton,
  healthStateNode,
  healthSummaryNode,
  loadFavoritesButton,
  loadHistoryButton,
  loadPlaylistsButton,
  loginForm,
  logoutButton,
  navAdminButton,
  navDashboardButton,
  navFavoritesButton,
  navHistoryButton,
  navPlaylistsButton,
  navSearchButton,
  navToggleButton,
  passwordChangeCancelButtons,
  passwordChangeDialog,
  passwordChangeForm,
  passwordChangeMessageNode,
  passwordChangeOpenButton,
  playerBar,
  playerDebugClearButton,
  playerDebugCopyButton,
  playerDebugDetailsNode,
  playerDebugDownloadButton,
  playerDebugEnableInput,
  playerDebugExportNode,
  playerDebugLogNode,
  playerDebugPanel,
  playerDebugSnapshotNode,
  playerDebugSummaryNode,
  playerDebugToggleButton,
  playerOpenLink,
  playerStatusNode,
  playerStopButton,
  playerTitleNode,
  playerToggleButton,
  playlistCancelButtons,
  playlistDialog,
  playlistForm,
  playlistMessageNode,
  playlistSelect,
  playlistStationNameNode,
  privateActionNodes,
  publicEntrySection,
  publicStatsContentNode,
  publicStatsMessageNode,
  publicStatsSection,
  registerCancelButtons,
  registerDialog,
  registerForm,
  registerMessageNode,
  registerOpenButton,
  resultCountNode,
  resultsKickerNode,
  resultsNode,
  resultsTitleNode,
  searchForm,
  searchPanel,
  setupForm,
  setupMessageNode,
  setupPanel,
  setupTokenField,
  statusNode,
  themeLabelNode,
  themeToggleButton,
} = createAppElements();

const appState = createAppState();

let playerController = null;
let playStation = () => {};
let setPlayerState = () => {};
let stopPlayback = () => {};

const uiShellController = createUiShellController({
  adminPanel,
  appContentNodes,
  appHeader,
  dashboardPanel,
  navToggleButton,
  playerBar,
  resultCountNode,
  resultsKickerNode,
  resultsNode,
  resultsTitleNode,
  searchPanel,
  setCurrentPlaylistName: appState.setCurrentPlaylistName,
  setCurrentView: appState.setCurrentView,
});

const {
  closeMobileMenu,
  resetRadioBrowserView,
  scrollToSection,
  setAppContentVisible,
  setMobileMenuOpen,
  setPlayerVisible,
  setResultsHeader,
  showAdminView,
  showDashboardView,
  showRadioBrowserView,
} = uiShellController;

const themeController = createThemeController({
  toggleButton: themeToggleButton,
  labelNode: themeLabelNode,
});

const toggleTheme = themeController.toggleTheme;

themeController.initializeTheme();
const healthController = createHealthController({
  fetch: window.fetch.bind(window),
  statusNode,
  healthStateNode,
  healthSummaryNode,
});
const { checkHealth } = healthController;


const publicStatsController = createPublicStatsController({
  contentNode: publicStatsContentNode,
  messageNode: publicStatsMessageNode,
  fetchImpl: window.fetch.bind(window),
});

const playerDebugController = createPlayerDebugController({
  panel: playerDebugPanel,
  summaryNode: playerDebugSummaryNode,
  enableInput: playerDebugEnableInput,
  toggleButton: playerDebugToggleButton,
  copyButton: playerDebugCopyButton,
  clearButton: playerDebugClearButton,
  downloadButton: playerDebugDownloadButton,
  detailsNode: playerDebugDetailsNode,
  snapshotNode: playerDebugSnapshotNode,
  logNode: playerDebugLogNode,
  exportNode: playerDebugExportNode,
  getSnapshot: (details) => playerController?.debugSnapshot(details) || { details },
  isVisible: () =>
    Boolean(appState.getCurrentUser()?.is_admin) && !isSetupAvailable(),
});

const logPlayerEvent = playerDebugController.logEvent;

playerDebugController.initialize();

function closeOpenDialog() {
  if (playlistDialog && !playlistDialog.hidden) {
    closePlaylistDialog();
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

function isSetupAvailable() {
  return setupController.isSetupAvailable();
}

const setupController = createSetupController({
  appContent,
  authPanel,
  getCurrentUser: appState.getCurrentUser,
  loadAuthState: () => loadAuthState(),
  resetRadioBrowserView,
  scrollToSection,
  searchPanel,
  setAppContentVisible,
  setCsrfToken: appState.setCsrfToken,
  setCurrentUser: appState.setCurrentUser,
  setPlayerVisible,
  setupForm,
  setupMessageNode,
  setupPanel,
  setupTokenField,
  updateAuthUi: () => updateAuthUi(),
});

const { createFirstAdmin, loadSetupState, updateSetupUi } = setupController;

const apiFetch = createApiFetch({
  getCsrfToken: appState.getCsrfToken,
  onUnauthorized: () => {
    appState.setCsrfToken("");
    appState.setCurrentUser(null);
    updateAuthUi();
    renderAuthRequired();
  },
});

const dashboardController = createDashboardController({
  apiFetch,
  panelNode: dashboardPanel,
  messageNode: dashboardMessageNode,
  userMetricsNode: dashboardUserMetricsNode,
  recentHistoryNode: dashboardRecentHistoryNode,
  favoriteHighlightsNode: dashboardFavoriteHighlightsNode,
  adminPanelNode: dashboardAdminPanel,
  adminMetricsNode: dashboardAdminMetricsNode,
  adminActionButton: dashboardAdminActionButton,
  renderStation: (station) => renderStation(station),
  bindResultActions: () => bindResultActions(),
  showDashboardView,
  isAuthenticated: appState.isAuthenticated,
  setCurrentView: appState.setCurrentView,
  setCurrentPlaylistName: appState.setCurrentPlaylistName,
});
const { loadDashboard } = dashboardController;


const accountRequestsController = createAccountRequestsController({
  authMessageNode,
  passwordChangeDialog,
  passwordChangeForm,
  passwordChangeMessageNode,
  registerDialog,
  registerForm,
  registerMessageNode,
});

const adminController = createAdminController({
  apiFetch,
  usersNode: adminUsersNode,
  messageNode: adminMessageNode,
  createUserForm: adminCreateUserForm,
  passwordForm: adminPasswordForm,
  passwordChangeRequestsNode: adminPasswordChangeRequestsNode,
  getCurrentUser: appState.getCurrentUser,
  loadDashboard,
});
const {
  createUser: createAdminUser,
  loadUsers: loadAdminUsers,
  loadUsersIfNeeded: loadAdminUsersIfNeeded,
  mutatePasswordChangeRequest,
  mutateUser: mutateAdminUser,
  setUserPassword: setAdminUserPassword,
} = adminController;

const sessionUiController = createSessionUiController({
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
});
const { renderAuthRequired, updateAuthUi } = sessionUiController;

const authController = createAuthController({
  apiFetch,
  authMessageNode,
  loginForm,
  loadDashboard,
  publicStatsController,
  renderAuthRequired,
  resetRadioBrowserView,
  setCsrfToken: appState.setCsrfToken,
  setCurrentUser: appState.setCurrentUser,
  stopPlayback: () => stopPlayback(),
  updateAuthUi,
});
const { loadAuthState, login, logout } = authController;

const mediaSessionController = createMediaSessionController({
  getCurrentStation: () => playerController?.getCurrentStation() || null,
  logPlayerEvent,
  pauseCurrentStationPlayback: (message) =>
    playerController?.pauseCurrentStationPlayback(message),
  startCurrentStationPlayback: (message) =>
    playerController?.startCurrentStationPlayback(message),
  stopPlayback: () => playerController?.stopPlayback(),
});

const { setupMediaSessionHandlers } = mediaSessionController;

playerController = createPlayerController({
  audioNode,
  playerBar,
  titleNode: playerTitleNode,
  statusNode: playerStatusNode,
  toggleButton: playerToggleButton,
  stopButton: playerStopButton,
  openLink: playerOpenLink,
  stationUrl,
  logPlayerEvent,
  mediaSessionController,
  recordHistory: (station) => recordHistory(station),
  resetRecordedHistory: () => favoriteController.resetRecordedHistory(),
});

({ playStation, setPlayerState, stopPlayback } = playerController);

const stationRenderer = createStationRenderer({
  renderState: () => ({
    currentUser: appState.getCurrentUser(),
    currentView: appState.getCurrentView(),
  }),
  onPlayStation: (station) => playStation(station),
  onAddFavorite: (station) => addFavorite(station),
  onRemoveFavorite: (station) => removeFavorite(station),
  onAddToPlaylist: (station) => playlistController.addToPlaylist(station),
  onRemoveFromPlaylist: (station) => playlistController.removeFromPlaylist(station),
  onStationActionError: (error) => {
    setPlayerState("error", `Could not read station data. ${error}`);
  },
});

const { bindResultActions, renderStation } = stationRenderer;

const searchController = createSearchController({
  searchForm,
  resultsNode,
  resultCountNode,
  setResultsHeader,
  renderStation,
  bindResultActions,
  setSearchView: () => {
    showRadioBrowserView();
    appState.setCurrentView("search");
    appState.setCurrentPlaylistName("");
  },
});

const { renderResults, renderSearchError } = searchController;

const playlistRenderer = createPlaylistRenderer({
  resultsNode,
  resultCountNode,
  onCreatePlaylist: (name) => playlistController.createPlaylist(name),
  onOpenPlaylist: (name) => loadPlaylistStations(name),
  onDeletePlaylist: (name) => playlistController.deletePlaylist(name),
});

const { bindPlaylistActions, renderPlaylists } = playlistRenderer;

const libraryViewsController = createLibraryViewsController({
  apiFetch,
  resultsNode,
  resultCountNode,
  setResultsHeader,
  renderResults,
  renderPlaylists,
  renderSearchError,
  setLibraryView: (view, playlistName = "") => {
    appState.setCurrentView(view);
    appState.setCurrentPlaylistName(playlistName);
  },
});

const { loadFavorites, loadHistory, loadPlaylists, loadPlaylistStations } = libraryViewsController;


const favoriteController = createFavoriteController({
  apiFetch,
  stationUrl,
  setPlayerState,
  isAuthenticated: appState.isAuthenticated,
  getCurrentView: appState.getCurrentView,
  loadFavorites,
});

const { addFavorite, recordHistory, removeFavorite } = favoriteController;

const playlistController = createPlaylistController({
  apiFetch,
  dialog: playlistDialog,
  form: playlistForm,
  selectNode: playlistSelect,
  messageNode: playlistMessageNode,
  stationNameNode: playlistStationNameNode,
  setPlayerState,
  getCurrentView: appState.getCurrentView,
  getCurrentPlaylistName: appState.getCurrentPlaylistName,
  loadPlaylists,
  loadPlaylistStations,
});

if (adminLoadUsersButton) {
  adminLoadUsersButton.addEventListener("click", loadAdminUsers);
}

if (adminCreateUserForm) {
  adminCreateUserForm.addEventListener("submit", createAdminUser);
}

if (adminPasswordForm) {
  adminPasswordForm.addEventListener("submit", setAdminUserPassword);
}

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

if (playlistForm) {
  playlistForm.addEventListener("submit", playlistController.submitPlaylistDialog);
}

playlistCancelButtons.forEach((button) => {
  button.addEventListener("click", playlistController.closePlaylistDialog);
});

if (setupForm) {
  setupForm.addEventListener("submit", createFirstAdmin);
}

if (loginForm) {
  loginForm.addEventListener("submit", login);
}

if (registerOpenButton) {
  registerOpenButton.addEventListener("click", accountRequestsController.openRegisterDialog);
}

if (passwordChangeOpenButton) {
  passwordChangeOpenButton.addEventListener("click", accountRequestsController.openPasswordChangeDialog);
}

passwordChangeCancelButtons.forEach((button) => {
  button.addEventListener("click", accountRequestsController.closePasswordChangeDialog);
});

if (passwordChangeForm) {
  passwordChangeForm.addEventListener("submit", accountRequestsController.requestPasswordChange);
}

registerCancelButtons.forEach((button) => {
  button.addEventListener("click", accountRequestsController.closeRegisterDialog);
});

if (registerForm) {
  registerForm.addEventListener("submit", accountRequestsController.registerAccount);
}

if (logoutButton) {
  logoutButton.addEventListener("click", logout);
}

if (healthButton) {
  healthButton.addEventListener("click", checkHealth);
}

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

document.addEventListener("click", (event) => {
  if (!appHeader || appHeader.dataset.mobileMenuOpen !== "true") return;
  if (event.target instanceof Node && appHeader.contains(event.target)) return;

  closeMobileMenu();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    if (closeOpenDialog()) {
      return;
    }

    closeMobileMenu();
  }
});

if (themeToggleButton) {
  themeToggleButton.addEventListener("click", toggleTheme);
}

if (navDashboardButton) {
  navDashboardButton.addEventListener("click", async () => {
    closeMobileMenu();
    if (!appState.isAuthenticated()) {
      renderAuthRequired();
      scrollToSection(authPanel);
      return;
    }

    await loadDashboard();
    scrollToSection(dashboardPanel);
  });
}

if (dashboardRefreshButton) {
  dashboardRefreshButton.addEventListener("click", loadDashboard);
}

dashboardActionButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const action = button.getAttribute("data-dashboard-action");
    if (action === "search") {
      resetRadioBrowserView();
      scrollToSection(searchPanel);
    } else if (action === "favorites") {
      await navigateToPrivateView(loadFavorites);
    } else if (action === "playlists") {
      await navigateToPrivateView(loadPlaylists);
    } else if (action === "history") {
      await navigateToPrivateView(loadHistory);
    } else if (action === "admin" && navAdminButton) {
      navAdminButton.click();
    }
  });
});

if (navSearchButton) {
  navSearchButton.addEventListener("click", () => {
    closeMobileMenu();
    resetRadioBrowserView();
    scrollToSection(searchPanel);
  });
}

if (navFavoritesButton) {
  navFavoritesButton.addEventListener("click", () => navigateToPrivateView(loadFavorites));
}

if (navPlaylistsButton) {
  navPlaylistsButton.addEventListener("click", () => navigateToPrivateView(loadPlaylists));
}

if (navHistoryButton) {
  navHistoryButton.addEventListener("click", () => navigateToPrivateView(loadHistory));
}

if (navAdminButton) {
  navAdminButton.addEventListener("click", async () => {
    closeMobileMenu();

    const currentUser = appState.getCurrentUser();
    if (!currentUser || !currentUser.is_admin || !adminPanel) return;

    showAdminView();

    await checkHealth();

    await loadAdminUsersIfNeeded();

    scrollToSection(adminPanel);
  });
}

if (searchForm) {
  searchForm.addEventListener("submit", searchController.searchStations);
}

if (loadHistoryButton) {
  loadHistoryButton.addEventListener("click", loadHistory);
}

if (loadFavoritesButton) {
  loadFavoritesButton.addEventListener("click", loadFavorites);
}

if (loadPlaylistsButton) {
  loadPlaylistsButton.addEventListener("click", loadPlaylists);
}

setupMediaSessionHandlers();
playerController.initialize();

if (playerDebugEnableInput) {
  playerDebugEnableInput.addEventListener("change", () => {
    playerDebugController.applyState(playerDebugEnableInput.checked);
    logPlayerEvent("player-debug-toggle", { enabled: playerDebugController.enabled });
  });
}


async function initializeAuthFlow() {
  updateSetupUi();
  updateAuthUi();

  await loadSetupState();

  if (setupController.isSetupAvailable()) {
    updateSetupUi();
    updateAuthUi();
  }
}

initializeAuthFlow();
