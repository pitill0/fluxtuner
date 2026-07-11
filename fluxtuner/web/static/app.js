/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { createAccountRequestsController } from "/static/js/account-requests.js";
import { createAdminController } from "/static/js/admin.js";
import { createApiFetch } from "/static/js/api.js";
import { createAppElements } from "/static/js/app-elements.js";
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

let playerController = null;
let playStation = () => {};
let setPlayerState = () => {};
let stopPlayback = () => {};
let currentView = "search";
let currentPlaylistName = "";
let currentUser = null;
let csrfToken = "";
let dashboardLoaded = false;

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
  setCurrentPlaylistName: (value) => {
    currentPlaylistName = value;
  },
  setCurrentView: (value) => {
    currentView = value;
  },
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
  isVisible: () => Boolean(currentUser?.is_admin) && !isSetupAvailable(),
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
  if (!currentUser) {
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
  getCurrentUser: () => currentUser,
  loadAuthState: () => loadAuthState(),
  resetRadioBrowserView,
  scrollToSection,
  searchPanel,
  setAppContentVisible,
  setCsrfToken: (token) => {
    csrfToken = token;
  },
  setCurrentUser: (user) => {
    currentUser = user;
  },
  setPlayerVisible,
  setupForm,
  setupMessageNode,
  setupPanel,
  setupTokenField,
  updateAuthUi: () => updateAuthUi(),
});

const { createFirstAdmin, loadSetupState, updateSetupUi } = setupController;

function updateAuthUi() {
  const authenticated = Boolean(currentUser);

  setPlayerVisible(!setupController.isSetupAvailable() && authenticated);

  if (publicEntrySection) {
    publicEntrySection.hidden = isSetupAvailable() || authenticated;
  }

  if (authPanel) {
    authPanel.dataset.authenticated = authenticated ? "true" : "false";
    authPanel.hidden = setupController.isSetupAvailable() || authenticated;
  }

  if (publicStatsSection) {
    publicStatsSection.hidden = isSetupAvailable() || authenticated;
  }

  if (!isSetupAvailable() && !authenticated) {
    publicStatsController.loadPublicStats();
  }

  setAppContentVisible(!setupController.isSetupAvailable() && authenticated);

  const showAdminPanel = authenticated && Boolean(currentUser.is_admin) && !isSetupAvailable();

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
    authMessageNode.textContent = authenticated ? "Private library tools are available." : "";
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

const apiFetch = createApiFetch({
  getCsrfToken: () => csrfToken,
  onUnauthorized: () => {
    csrfToken = "";
    currentUser = null;
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
  isAuthenticated: () => Boolean(currentUser),
  setDashboardLoaded: (value) => {
    dashboardLoaded = value;
  },
  setCurrentView: (value) => {
    currentView = value;
  },
  setCurrentPlaylistName: (value) => {
    currentPlaylistName = value;
  },
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
  getCurrentUser: () => currentUser,
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

const authController = createAuthController({
  apiFetch,
  authMessageNode,
  loginForm,
  loadDashboard,
  publicStatsController,
  renderAuthRequired,
  resetRadioBrowserView,
  setCsrfToken: (token) => {
    csrfToken = token;
  },
  setCurrentUser: (user) => {
    currentUser = user;
  },
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
    currentUser,
    currentView,
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
    currentView = "search";
    currentPlaylistName = "";
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
    currentView = view;
    currentPlaylistName = playlistName;
  },
});

const { loadFavorites, loadHistory, loadPlaylists, loadPlaylistStations } = libraryViewsController;


const favoriteController = createFavoriteController({
  apiFetch,
  stationUrl,
  setPlayerState,
  isAuthenticated: () => Boolean(currentUser),
  getCurrentView: () => currentView,
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
  getCurrentView: () => currentView,
  getCurrentPlaylistName: () => currentPlaylistName,
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
    if (!currentUser) {
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
