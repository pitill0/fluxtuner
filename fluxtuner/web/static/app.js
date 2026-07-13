/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { createAccountRequestsController } from "/static/js/account-requests.js";
import { createAdminController } from "/static/js/admin.js";
import { createApiFetch } from "/static/js/api.js";
import { createAppElements } from "/static/js/app-elements.js";
import { bindApplicationEvents } from "/static/js/app-events.js";
import { bootstrapApplication } from "/static/js/app-bootstrap.js";
import { createAppState } from "/static/js/app-state.js";
import { createAuthController } from "/static/js/auth.js";
import { createDashboardController } from "/static/js/dashboard.js";
import { createFavoriteController } from "/static/js/favorites.js";
import { createHealthController } from "/static/js/health.js";
import { createLibraryViewsController } from "/static/js/library-views.js";
import { createMediaSessionController } from "/static/js/media-session.js";
import { createMetadataController } from "/static/js/metadata.js";
import { createNavigationController } from "/static/js/navigation.js";
import { createPlayerDebugController } from "/static/js/player-debug.js";
import { createPlayerController } from "/static/js/player.js";
import { createPlayerRuntime } from "/static/js/player-runtime.js";
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
  playerStationNode,
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
const playerRuntime = createPlayerRuntime();

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
  getSnapshot: playerRuntime.debugSnapshot,
  isVisible: () =>
    Boolean(appState.getCurrentUser()?.is_admin) && !isSetupAvailable(),
});

const logPlayerEvent = playerDebugController.logEvent;

playerDebugController.initialize();

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
  stopPlayback: playerRuntime.stopPlayback,
  updateAuthUi,
});
const { loadAuthState, login, logout } = authController;

const mediaSessionController = createMediaSessionController({
  getCurrentStation: playerRuntime.getCurrentStation,
  logPlayerEvent,
  pauseCurrentStationPlayback: playerRuntime.pauseCurrentStationPlayback,
  startCurrentStationPlayback: playerRuntime.startCurrentStationPlayback,
  stopPlayback: playerRuntime.stopPlayback,
});

const { setupMediaSessionHandlers } = mediaSessionController;

const metadataController = createMetadataController({
  apiFetch,
  titleNode: playerTitleNode,
  stationNode: playerStationNode,
  logPlayerEvent,
});

const playerController = createPlayerController({
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
  metadataController,
  recordHistory: (station) => recordHistory(station),
  resetRecordedHistory: () => favoriteController.resetRecordedHistory(),
});

playerRuntime.attach(playerController);

const stationRenderer = createStationRenderer({
  renderState: () => ({
    currentUser: appState.getCurrentUser(),
    currentView: appState.getCurrentView(),
  }),
  onPlayStation: playerRuntime.playStation,
  onAddFavorite: (station) => addFavorite(station),
  onRemoveFavorite: (station) => removeFavorite(station),
  onAddToPlaylist: (station) => playlistController.addToPlaylist(station),
  onRemoveFromPlaylist: (station) => playlistController.removeFromPlaylist(station),
  onStationActionError: (error) => {
    playerRuntime.setPlayerState("error", `Could not read station data. ${error}`);
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
  setPlayerState: playerRuntime.setPlayerState,
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
  setPlayerState: playerRuntime.setPlayerState,
  getCurrentView: appState.getCurrentView,
  getCurrentPlaylistName: appState.getCurrentPlaylistName,
  loadPlaylists,
  loadPlaylistStations,
});

const navigationController = createNavigationController({
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
});
const {
  closeOpenDialog,
  navigateToAdmin,
  navigateToDashboard,
  navigateToPrivateView,
  navigateToSearch,
} = navigationController;

bindApplicationEvents({
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
  documentNode: document,
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
  nodeConstructor: Node,
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
});

bootstrapApplication({
  loadSetupState,
  playerController,
  setupController,
  setupMediaSessionHandlers,
  updateAuthUi,
  updateSetupUi,
});
