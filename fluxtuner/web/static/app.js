import { createBrowserNavigationController } from "/static/js/browser-navigation.js";
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
import { createNavigationAccordion } from "/static/js/navigation-accordion.js";
import { createSidebarToggle } from "/static/js/sidebar-toggle.js";
import { createMobileDrawer } from "/static/js/mobile-drawer.js";
import { createAuthController } from "/static/js/auth.js";
import { createCustomStationController } from "/static/js/custom-stations.js";
import { createStationImportController } from "/static/js/station-imports.js";
import { createRemoteSubscriptionController } from "/static/js/remote-subscriptions.js";
import { createDashboardController } from "/static/js/dashboard.js";
import { createFavoriteController } from "/static/js/favorites.js";
import { createHealthController } from "/static/js/health.js";
import { createLibraryViewsController } from "/static/js/library-views.js";
import { createUnifiedLibraryController } from "/static/js/unified-library.js";
import { createMediaSessionController } from "/static/js/media-session.js";
import { createMetadataController } from "/static/js/metadata.js";
import { createNavigationController } from "/static/js/navigation.js";
import { createNavigationPresentation } from "/static/js/navigation-presentation.js";
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
  stationImportElements,
  subscriptionElements,
  customStationMenuButton,
  customStationDialog,
  customStationForm,
  customStationMessageNode,
  customStationOpenButton,
  customStationCancelButtons,
  customStationTools,
  adminCreateUserForm,
  adminLoadUsersButton,
  adminMessageNode,
  accountPanel,
  accountUsernameNode,
  adminPanel,
  adminPasswordForm,
  adminUsersNode,
  appContent,
  appContentNodes,
  appHeader,
  appShell,
  sidebarToggleButton,
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
  navAccountButton,
  navAdminButton,
  navDashboardButton,
  navFavoritesButton,
  navHistoryButton,
  navPlaylistsButton,
  navStationsButton,
  navCatalogsButton,
  navSearchButton,
  navToggleButton,
  passwordChangeCancelButtons,
  passwordChangeDialog,
  passwordChangeForm,
  passwordChangeMessageNode,
  passwordChangeOpenButton,
  recoveryCodesCloseButtons,
  recoveryCodesDialog,
  recoveryCodesListNode,
  recoveryCodesRegenerateCancelButtons,
  recoveryCodesRegenerateDialog,
  recoveryCodesRegenerateForm,
  recoveryCodesRegenerateMessageNode,
  recoveryCodesRegenerateOpenButton,
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
  playerCopyButton,
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
let browserNavigation = null;

createMobileDrawer({
  root: appShell,
  header: appHeader,
  toggleButton: navToggleButton,
  windowNode: window,
}).bind();

createNavigationAccordion({
  root: appShell,
}).bind();

createSidebarToggle({
  shell: appShell,
  button: sidebarToggleButton,
  windowNode: window,
}).bind();

const navigationPresentation = createNavigationPresentation({
  appState,
  root: document,
  accountPanel,
  adminPanel,
  dashboardPanel,
  searchPanel,
});
navigationPresentation.bind();
const playerRuntime = createPlayerRuntime();

const uiShellController = createUiShellController({
  accountPanel,
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
  setCurrentSection: appState.setCurrentSection,
});

const {
  closeMobileMenu,
  resetRadioBrowserView,
  scrollToSection,
  setAppContentVisible,
  setMobileMenuOpen,
  setPlayerVisible,
  setResultsHeader,
  showAccountView,
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

const apiFetch = createApiFetch({
  getCsrfToken: appState.getCsrfToken,
  onUnauthorized: () => {
    if (playerRuntime.getCurrentStation()) {
      playerRuntime.stopPlayback();
    }
    appState.setCsrfToken("");
    appState.setCurrentUser(null);
    updateAuthUi();
    renderAuthRequired();
  },
});

const dashboardController = createDashboardController({
  apiFetch,
  getCurrentUser: appState.getCurrentUser,
  isDashboardVisible: () => dashboardPanel?.hidden === false,
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
  apiFetch,
  authMessageNode,
  passwordChangeDialog,
  passwordChangeForm,
  passwordChangeMessageNode,
  recoveryCodesRegenerateDialog,
  recoveryCodesRegenerateForm,
  recoveryCodesRegenerateMessageNode,
  recoveryCodesDialog,
  recoveryCodesListNode,
  registerDialog,
  registerForm,
  registerMessageNode,
});

const { showRecoveryCodes } = accountRequestsController;

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
  showRecoveryCodes,
  setPlayerVisible,
  setupForm,
  setupMessageNode,
  setupPanel,
  setupTokenField,
  updateAuthUi: () => updateAuthUi(),
});

const { createFirstAdmin, loadSetupState, updateSetupUi } = setupController;

const adminController = createAdminController({
  apiFetch,
  usersNode: adminUsersNode,
  messageNode: adminMessageNode,
  createUserForm: adminCreateUserForm,
  passwordForm: adminPasswordForm,
  getCurrentUser: appState.getCurrentUser,
  loadDashboard,
});
const {
  createUser: createAdminUser,
  loadUsers: loadAdminUsers,
  loadUsersIfNeeded: loadAdminUsersIfNeeded,
  mutateUser: mutateAdminUser,
  setUserPassword: setAdminUserPassword,
} = adminController;

const customStationController = createCustomStationController({
  apiFetch,
  dialog: customStationDialog,
  form: customStationForm,
  messageNode: customStationMessageNode,
  openButton: customStationOpenButton,
  cancelButtons: customStationCancelButtons,
  toolsNode: customStationTools,
  getCurrentUser: appState.getCurrentUser,
  getSessionKey: appState.getCsrfToken,
  beforeOpen: () => closeOpenDialog(),
  onSaved: async (added) => {
    showRadioBrowserView();
    await loadFavorites();
    if (authMessageNode && appState.isAuthenticated()) {
      authMessageNode.hidden = false;
      authMessageNode.textContent = added
        ? "Station added to favorites."
        : "Station is already in favorites.";
    }
  },
});

const stationImportController = createStationImportController({
  apiFetch,
  elements: stationImportElements,
  getCurrentUser: appState.getCurrentUser,
  getSessionKey: appState.getCsrfToken,
  beforeOpen: () => {
    closeMobileMenu();
    closeOpenDialog();
  },
  onSaved: async (payload) => {
    showRadioBrowserView();
    await loadPlaylistStations(payload.name);
    if (authMessageNode && appState.isAuthenticated()) {
      authMessageNode.hidden = false;
      authMessageNode.textContent =
        `Imported ${payload.added_to_playlist} stations into ${payload.name}. ` +
        `${payload.existing_favorites} already in favorites.`;
    }
  },
});

const subscriptionController = createRemoteSubscriptionController({
  apiFetch,
  onChanged: ({ type, sourceId }) => {
    if (!appState.isAuthenticated()) return;
    const view = appState.getCurrentView();
    if (searchPanel?.hidden !== false) return;

    if (view === "catalogs") {
      void loadCatalogs();
    } else if (view === "catalog") {
      const selected = appState.getCurrentCatalogId();
      if (type === "removed" && Number(sourceId) === selected) {
        void loadCatalogs();
      } else if (type === "updated" &&
                 Number(sourceId) === selected) {
        void loadCatalogStations(selected);
      }
    }
  },
  elements: subscriptionElements,
  getCurrentUser: appState.getCurrentUser,
  getSessionKey: appState.getCsrfToken,
  beforeOpen: () => {
    closeMobileMenu();
    closeOpenDialog();
  },
});

const sessionUiController = createSessionUiController({
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
});
const { renderAuthRequired, updateAuthUi } = sessionUiController;

const authController = createAuthController({
  onAuthReady: () => browserNavigation?.onAuthReady(),
  onLogout: () => browserNavigation?.onLogout(),
  apiFetch,
  authMessageNode,
  loginForm,
  loadDashboard,
  publicStatsController,
  renderAuthRequired,
  resetRadioBrowserView,
  setCsrfToken: appState.setCsrfToken,
  setCurrentUser: appState.setCurrentUser,
  showRecoveryCodes,
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
  stationUrl,
});

const { setupMediaSessionHandlers } = mediaSessionController;

const metadataController = createMetadataController({
  apiFetch,
  titleNode: playerTitleNode,
  copyButton: playerCopyButton,
  stationNode: playerStationNode,
  statusNode: playerStatusNode,
  onMetadataChange: (metadata, fallbackTitle, streamUrl) => {
    mediaSessionController.updateNowPlayingMetadata(
      metadata,
      fallbackTitle,
      streamUrl,
      "metadata-controller",
    );
  },
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
  getCurrentView: appState.getCurrentView,
  getCurrentUser: appState.getCurrentUser,
  isSearchVisible: () => searchPanel?.hidden === false,
  subscribeViewChange: appState.subscribeViewChange,
  resultsNode,
  resultCountNode,
  setResultsHeader,
  renderStation,
  bindResultActions,
  setSearchView: () => {
    showRadioBrowserView();
    appState.setCurrentView("search");
    customStationController.updateVisibility("search");
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
  getCurrentView: appState.getCurrentView,
  getCurrentUser: appState.getCurrentUser,
  isLibraryVisible: () => searchPanel?.hidden === false,
  resultsNode,
  resultCountNode,
  setResultsHeader,
  renderResults,
  renderPlaylists,
  renderSearchError,
  setLibraryView: (view, playlistName = "") => {
    appState.setCurrentPlaylistName(playlistName);
    appState.setCurrentView(view);
    customStationController.updateVisibility(view);
  },
});

const { loadFavorites, loadHistory, loadPlaylists, loadPlaylistStations } = libraryViewsController;


const unifiedLibraryController = createUnifiedLibraryController({
  apiFetch,
  getCurrentUser: appState.getCurrentUser,
  getCurrentView: appState.getCurrentView,
  isLibraryVisible: () => searchPanel?.hidden === false,
  resultsNode,
  resultCountNode,
  setResultsHeader,
  renderResults,
  renderSearchError,
  setLibraryView: (view) => {
    appState.setCurrentPlaylistName("");
    appState.setCurrentCatalogId(0);
    appState.setCurrentView(view);
    customStationController.updateVisibility(view);
  },
  onOpenCatalog: (id) => navigateToPrivateView(
    () => loadCatalogStations(id),
  ),
  onManageCatalogs: () => subscriptionController.openDialog(),
});

const {
  loadMyStations,
  loadCatalogs,
  loadCatalogStations: loadCatalogStationsRaw,
} = unifiedLibraryController;

function loadCatalogStations(id) {
  const pending = loadCatalogStationsRaw(id);
  appState.setCurrentCatalogId(Number(id));
  return pending;
}

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
  subscriptionController,
  stationImportController,
  customStationController,
  accountRequestsController,
  accountPanel,
  adminPanel,
  appState,
  authPanel,
  checkHealth,
  closeMobileMenu,
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
});
const {
  closeOpenDialog,
  navigateToAccount,
  navigateToAdmin,
  navigateToDashboard,
  navigateToPrivateView,
  navigateToSearch,
} = navigationController;

browserNavigation = createBrowserNavigationController({
  appState,
  browser: window,
  navigation: {
    dashboard: navigateToDashboard,
    explore: navigateToSearch,
    favorites: () => navigateToPrivateView(loadFavorites),
    playlists: () => navigateToPrivateView(loadPlaylists),
    history: () => navigateToPrivateView(loadHistory),
    stations: () => navigateToPrivateView(loadMyStations),
    catalogs: () => navigateToPrivateView(loadCatalogs),
    catalog: (id) => navigateToPrivateView(() => loadCatalogStations(id)),
    playlist: (name) => navigateToPrivateView(() => loadPlaylistStations(name)),
    account: navigateToAccount,
    admin: navigateToAdmin,
  },
});
browserNavigation.bind();


customStationController.bind();
stationImportController.bind();
subscriptionController.bind();


bindApplicationEvents({
  customStationController,
  customStationMenuButton,
  accountRequestsController,
  adminCreateUserForm,
  adminLoadUsersButton,
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
  loadMyStations,
  loadCatalogs,
  login,
  loginForm,
  logout,
  logoutButton,
  mutateAdminUser,
  navigateToAccount,
  navigateToAdmin,
  navigateToDashboard,
  navigateToPrivateView,
  navigateToSearch,
  navAccountButton,
  navAdminButton,
  navDashboardButton,
  navFavoritesButton,
  navHistoryButton,
  navPlaylistsButton,
  navStationsButton,
  navCatalogsButton,
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
  recoveryCodesCloseButtons,
  recoveryCodesRegenerateCancelButtons,
  recoveryCodesRegenerateForm,
  recoveryCodesRegenerateOpenButton,
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
