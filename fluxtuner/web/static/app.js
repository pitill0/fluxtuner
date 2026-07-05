/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { createAccountRequestsController } from "/static/js/account-requests.js";
import { createAdminController } from "/static/js/admin.js";
import { createApiFetch } from "/static/js/api.js";
import { createAuthController } from "/static/js/auth.js";
import { createDashboardController } from "/static/js/dashboard.js";
import { createFavoriteController } from "/static/js/favorites.js";
import { createHealthController } from "/static/js/health.js";
import { createLibraryViewsController } from "/static/js/library-views.js";
import { createMediaSessionController } from "/static/js/media-session.js";
import { createPlayerDebugController } from "/static/js/player-debug.js";
import { createPlayerController } from "/static/js/player.js";
import { createPlaylistController } from "/static/js/playlists.js";
import { createPublicStatsController } from "/static/js/public-stats.js";
import { createSearchController } from "/static/js/search.js";
import { createSetupController } from "/static/js/setup.js";
import { createThemeController } from "/static/js/theme.js";
import { createUiShellController } from "/static/js/ui-shell.js";
import { createStationRenderer } from "/static/js/station-renderer.js";
import { escapeHtml, stationUrl } from "/static/js/stations.js";

const statusNode = document.querySelector("[data-status]");
const healthStateNode = document.querySelector("[data-health-state]");
const healthSummaryNode = document.querySelector("[data-health-summary]");
const healthButton = document.querySelector("[data-health-check]");
const searchForm = document.querySelector("[data-search-form]");
const resultsNode = document.querySelector("[data-results]");
const resultCountNode = document.querySelector("[data-result-count]");
const resultsKickerNode = document.querySelector("[data-results-kicker]");
const resultsTitleNode = document.querySelector("[data-results-title]");
const appContent = document.querySelector("[data-app-content]");
const searchPanel = document.querySelector("[data-search-panel]");
const appContentNodes = document.querySelectorAll("[data-app-content]");
const appHeader = document.querySelector("[data-app-header]");
const navToggleButton = document.querySelector("[data-nav-toggle]");
const themeToggleButton = document.querySelector("[data-theme-toggle]");
const themeLabelNode = document.querySelector("[data-theme-label]");
const navDashboardButton = document.querySelector("[data-nav-dashboard]");
const navSearchButton = document.querySelector("[data-nav-search]");
const navFavoritesButton = document.querySelector("[data-nav-favorites]");
const navPlaylistsButton = document.querySelector("[data-nav-playlists]");
const navHistoryButton = document.querySelector("[data-nav-history]");
const navAdminButton = document.querySelector("[data-nav-admin]");
const loadHistoryButton = document.querySelector("[data-load-history]");
const loadFavoritesButton = document.querySelector("[data-load-favorites]");
const loadPlaylistsButton = document.querySelector("[data-load-playlists]");
const publicEntrySection = document.querySelector("[data-public-entry]");
const authPanel = document.querySelector("[data-auth-panel]");
const loginForm = document.querySelector("[data-login-form]");
const registerOpenButton = document.querySelector("[data-register-open]");
const registerDialog = document.querySelector("[data-register-dialog]");
const registerCancelButtons = document.querySelectorAll("[data-register-cancel]");
const registerForm = document.querySelector("[data-register-form]");
const registerMessageNode = document.querySelector("[data-register-message]");
const passwordChangeOpenButton = document.querySelector("[data-password-change-open]");
const passwordChangeDialog = document.querySelector("[data-password-change-dialog]");
const passwordChangeCancelButtons = document.querySelectorAll("[data-password-change-cancel]");
const passwordChangeForm = document.querySelector("[data-password-change-form]");
const passwordChangeMessageNode = document.querySelector("[data-password-change-message]");
const authMessageNode = document.querySelector("[data-auth-message]");
const publicStatsSection = document.querySelector("[data-public-stats]");
const publicStatsContentNode = document.querySelector("[data-public-stats-content]");
const publicStatsMessageNode = document.querySelector("[data-public-stats-message]");
const authUserPanel = document.querySelector("[data-auth-user]");
const authUsernameNode = document.querySelector("[data-auth-username]");
const logoutButton = document.querySelector("[data-logout]");
const privateActionNodes = document.querySelectorAll("[data-private-action]");
const setupPanel = document.querySelector("[data-setup-panel]");
const setupForm = document.querySelector("[data-setup-form]");
const setupTokenField = document.querySelector("[data-setup-token-field]");
const setupMessageNode = document.querySelector("[data-setup-message]");
const dashboardPanel = document.querySelector("[data-dashboard-panel]");
const dashboardRefreshButton = document.querySelector("[data-dashboard-refresh]");
const dashboardUserMetricsNode = document.querySelector("[data-dashboard-user-metrics]");
const dashboardRecentHistoryNode = document.querySelector("[data-dashboard-recent-history]");
const dashboardFavoriteHighlightsNode = document.querySelector("[data-dashboard-favorite-highlights]");
const dashboardAdminPanel = document.querySelector("[data-dashboard-admin]");
const dashboardAdminMetricsNode = document.querySelector("[data-dashboard-admin-metrics]");
const dashboardAdminActionButton = document.querySelector("[data-dashboard-admin-action]");
const dashboardMessageNode = document.querySelector("[data-dashboard-message]");
const adminPanel = document.querySelector("[data-admin-panel]");
const adminLoadUsersButton = document.querySelector("[data-admin-load-users]");
const adminCreateUserForm = document.querySelector("[data-admin-create-user-form]");
const adminPasswordForm = document.querySelector("[data-admin-password-form]");
const adminMessageNode = document.querySelector("[data-admin-message]");
const adminUsersNode = document.querySelector("[data-admin-users]");
const adminPasswordChangeRequestsNode = document.querySelector(
  "[data-admin-password-change-requests]",
);
const playlistDialog = document.querySelector("[data-playlist-dialog]");
const playlistForm = document.querySelector("[data-playlist-form]");
const playlistSelect = document.querySelector("[data-playlist-select]");
const playlistMessageNode = document.querySelector("[data-playlist-message]");
const playlistStationNameNode = document.querySelector("[data-playlist-station-name]");
const playlistCancelButtons = document.querySelectorAll("[data-playlist-cancel]");

const playerBar = document.querySelector("[data-player-bar]");
const audioNode = document.querySelector("[data-audio]");
const playerTitleNode = document.querySelector("[data-player-title]");
const playerStatusNode = document.querySelector("[data-player-status]");
const playerToggleButton = document.querySelector("[data-player-toggle]");
const playerStopButton = document.querySelector("[data-player-stop]");
const playerOpenLink = document.querySelector("[data-player-open]");
const playerDebugPanel = document.querySelector("[data-player-debug-panel]");
const playerDebugSummaryNode = document.querySelector("[data-player-debug-summary]");
const playerDebugEnableInput = document.querySelector("[data-player-debug-enable]");
const playerDebugToggleButton = document.querySelector("[data-player-debug-toggle]");
const playerDebugCopyButton = document.querySelector("[data-player-debug-copy]");
const playerDebugClearButton = document.querySelector("[data-player-debug-clear]");
const playerDebugDownloadButton = document.querySelector("[data-player-debug-download]");
const playerDebugDetailsNode = document.querySelector("[data-player-debug-details]");
const playerDebugSnapshotNode = document.querySelector("[data-player-debug-snapshot]");
const playerDebugLogNode = document.querySelector("[data-player-debug-log]");
const playerDebugExportNode = document.querySelector("[data-player-debug-export]");

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
  renderStation,
  bindResultActions,
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

function renderPlaylists(payload) {
  if (!resultsNode || !resultCountNode) return;

  const playlists = payload.playlists || [];
  resultCountNode.textContent = `${payload.count ?? playlists.length} playlist${
    playlists.length === 1 ? "" : "s"
  }`;

  if (!playlists.length) {
    resultsNode.innerHTML = `
      <p class="empty">No playlists yet.</p>
      <div class="station-actions">
        <button type="button" data-create-playlist>Create playlist</button>
      </div>
    `;
    bindPlaylistActions();
    return;
  }

  resultsNode.innerHTML = `
    <div class="station-actions">
      <button type="button" data-create-playlist>Create playlist</button>
    </div>
    ${playlists
      .map(
        (playlist) => `
          <article class="station-card">
            <header>
              <div>
                <h3>${escapeHtml(playlist.name)}</h3>
              </div>
              <div class="station-meta">
                <span>${Number(playlist.count || 0)} station${
                  Number(playlist.count || 0) === 1 ? "" : "s"
                }</span>
              </div>
            </header>

            <div class="station-actions">
              <button type="button" data-open-playlist="${escapeHtml(
                playlist.name,
              )}">Open playlist</button>
              <button type="button" data-delete-playlist="${escapeHtml(
                playlist.name,
              )}">Delete playlist</button>
            </div>
          </article>
        `,
      )
      .join("")}
  `;

  bindPlaylistActions();
}

function bindPlaylistActions() {
  document.querySelectorAll("[data-create-playlist]").forEach((button) => {
    button.addEventListener("click", playlistController.createPlaylistFromPrompt);
  });

  document.querySelectorAll("[data-open-playlist]").forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.getAttribute("data-open-playlist");
      if (name) {
        loadPlaylistStations(name);
      }
    });
  });

  document.querySelectorAll("[data-delete-playlist]").forEach((button) => {
    button.addEventListener("click", () => {
      const name = button.getAttribute("data-delete-playlist");
      if (name) {
        playlistController.deletePlaylist(name);
      }
    });
  });
}

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

document.querySelectorAll("[data-dashboard-action]").forEach((button) => {
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
    return;
  }

  await loadAuthState();
}

initializeAuthFlow();
