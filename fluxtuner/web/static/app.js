/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { createAccountRequestsController } from "/static/js/account-requests.js";
import { createAdminController } from "/static/js/admin.js";
import { createApiFetch } from "/static/js/api.js";
import { createDashboardController } from "/static/js/dashboard.js";
import { createFavoriteController } from "/static/js/favorites.js";
import { createHealthController } from "/static/js/health.js";
import { createLibraryViewsController } from "/static/js/library-views.js";
import { createPlayerDebugController } from "/static/js/player-debug.js";
import { createPlaylistController } from "/static/js/playlists.js";
import { createPublicStatsController } from "/static/js/public-stats.js";
import { createSearchController } from "/static/js/search.js";
import { createSetupController } from "/static/js/setup.js";
import { createThemeController } from "/static/js/theme.js";
import {
  escapeHtml,
  stationButtonPayload,
  stationHomepage,
  stationTags,
  stationUrl,
} from "/static/js/stations.js";

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

let currentStation = null;
let currentView = "search";
let currentPlaylistName = "";
let currentUser = null;
let csrfToken = "";
let dashboardLoaded = false;
let startingPlayback = false;
let softPausingPlayback = false;
let stoppingPlayback = false;
function setResultsHeader(kicker, title) {
  if (resultsKickerNode) {
    resultsKickerNode.textContent = kicker;
  }

  if (resultsTitleNode) {
    resultsTitleNode.textContent = title;
  }
}

function setAppContentVisible(visible) {
  appContentNodes.forEach((node) => {
    node.hidden = !visible;
  });
}

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

function audioDebugSnapshot() {
  if (!audioNode) return null;

  return {
    paused: audioNode.paused,
    ended: audioNode.ended,
    readyState: audioNode.readyState,
    networkState: audioNode.networkState,
    currentSrc: audioNode["currentSrc"] || "",
    src: audioNode.getAttribute("src") || "",
    errorCode: audioNode.error?.code || null,
    errorMessage: audioNode.error?.message || "",
  };
}

function mediaSessionDebugSnapshot() {
  if (!("mediaSession" in navigator)) return null;

  try {
    return {
      playbackState: navigator.mediaSession.playbackState || "",
      hasMetadata: Boolean(navigator.mediaSession.metadata),
    };
  } catch (_error) {
    return { unavailable: true };
  }
}

function playerDebugSnapshot(details = {}) {
  return {
    state: playerBar?.dataset.state || "",
    station: currentStation
      ? {
          name: currentStation.name || currentStation.custom_name || "",
          url: stationUrl(currentStation),
        }
      : null,
    flags: {
      startingPlayback,
      softPausingPlayback,
      stoppingPlayback,
    },
    audio: audioDebugSnapshot(),
    mediaSession: mediaSessionDebugSnapshot(),
    visibilityState: document.visibilityState || "",
    details,
  };
}

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
  getSnapshot: playerDebugSnapshot,
  isVisible: () => Boolean(currentUser?.is_admin) && !isSetupAvailable(),
});

const logPlayerEvent = playerDebugController.logEvent;

playerDebugController.initialize();

function scrollToSection(node) {
  if (!node) return;
  node.scrollIntoView({ behavior: "smooth", block: "start" });
}

function setMobileMenuOpen(open) {
  if (!appHeader || !navToggleButton) return;

  const nextState = open ? "true" : "false";
  appHeader.dataset.mobileMenuOpen = nextState;
  navToggleButton.setAttribute("aria-expanded", nextState);
}

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

function closeMobileMenu() {
  setMobileMenuOpen(false);
}

function setPlayerVisible(isVisible) {
  if (!playerBar) return;

  if (isVisible) {
    playerBar.removeAttribute("hidden");
  } else {
    playerBar.setAttribute("hidden", "");
  }
}

function resetRadioBrowserView() {
  showRadioBrowserView();
  currentView = "search";
  currentPlaylistName = "";
  setResultsHeader("Radio Browser", "Search stations");

  if (resultCountNode) {
    resultCountNode.textContent = "";
  }

  if (resultsNode) {
    resultsNode.innerHTML = '<p class="empty">Search Radio Browser to find internet radio stations.</p>';
  }
}

function showRadioBrowserView() {
  if (searchPanel) {
    searchPanel.hidden = false;
  }

  if (dashboardPanel) {
    dashboardPanel.hidden = true;
  }

  if (adminPanel) {
    adminPanel.hidden = true;
  }
}

function showDashboardView() {
  if (searchPanel) {
    searchPanel.hidden = true;
  }

  if (dashboardPanel) {
    dashboardPanel.hidden = false;
  }

  if (adminPanel) {
    adminPanel.hidden = true;
  }
}

function showAdminView() {
  if (searchPanel) {
    searchPanel.hidden = true;
  }

  if (dashboardPanel) {
    dashboardPanel.hidden = true;
  }

  if (adminPanel) {
    adminPanel.hidden = false;
  }
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

async function loadAuthState() {
  try {
    const response = await fetch("/api/auth/me", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      currentUser = null;
      csrfToken = "";
      updateAuthUi();
      return;
    }

    const payload = await response.json();
    currentUser = payload.user || null;
    csrfToken = payload.csrf_token || "";
    resetRadioBrowserView();
    updateAuthUi();
    await loadDashboard();
  } catch (_error) {
    currentUser = null;
    updateAuthUi();
  }
}

async function login(event) {
  event.preventDefault();

  if (!loginForm || !authMessageNode) return;

  const formData = new FormData(loginForm);
  const username = String(formData.get("username") || "").trim();
  const password = String(formData.get("password") || "");

  authMessageNode.textContent = "Signing in...";

  try {
    const response = await fetch("/api/auth/login", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ username, password }),
    });

    loginForm.reset();

    if (!response.ok) {
      if (response.status === 429) {
        throw new Error("Too many login attempts. Try again later.");
      }

      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Invalid username or password.");
    }

    const payload = await response.json();
    currentUser = payload.user || null;
    csrfToken = payload.csrf_token || "";
    resetRadioBrowserView();
    updateAuthUi();
    await loadDashboard();
  } catch (error) {
    currentUser = null;
    csrfToken = "";
    updateAuthUi();
    authMessageNode.textContent = String(error);
  }
}


async function logout() {
  try {
    await apiFetch("/api/auth/logout", {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });
  } finally {
    stopPlayback();
    currentUser = null;
    publicStatsController.reset();
    resetRadioBrowserView();
    updateAuthUi();
    renderAuthRequired();
  }
}



function setPlayerState(state, message) {
  logPlayerEvent("player-state", { state, message });
  if (playerBar) {
    playerBar.dataset.state = state;
  }

  if (playerStatusNode) {
    playerStatusNode.textContent = message;
  }

  updateMediaSessionState(state);
}

function setMediaSessionMetadata(station) {
  if (!("mediaSession" in navigator) || !("MediaMetadata" in window) || !station) return;

  try {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: station.name || station.custom_name || "Unknown station",
      artist: "FluxTuner Web",
      album: "Internet radio",
    });
  } catch (_error) {
    // MediaMetadata is optional even when mediaSession exists.
  }
}

function clearMediaSessionMetadata() {
  if (!("mediaSession" in navigator)) return;

  try {
    navigator.mediaSession.metadata = null;
    navigator.mediaSession.playbackState = "none";
  } catch (_error) {
    // Some browsers expose mediaSession only partially.
  }
}

function updateMediaSessionState(state) {
  if (!("mediaSession" in navigator)) return;

  try {
    if (currentStation) {
      setMediaSessionMetadata(currentStation);
    }

    if (state === "playing" || state === "loading") {
      navigator.mediaSession.playbackState = "playing";
    } else if (state === "paused" || currentStation) {
      navigator.mediaSession.playbackState = "paused";
    } else {
      navigator.mediaSession.playbackState = "none";
    }
  } catch (_error) {
    // Media Session support varies across desktop and mobile browsers.
  }
}

function updatePlayerControls() {
  if (!audioNode || !playerToggleButton || !playerStopButton) return;

  const hasStream = Boolean(currentStation && stationUrl(currentStation));
  playerToggleButton.disabled = !hasStream;
  playerStopButton.disabled = !hasStream;

  if (audioNode.paused || playerBar?.dataset.state === "loading") {
    playerToggleButton.textContent = "Resume";
  } else {
    playerToggleButton.textContent = "Pause";
  }

  if (playerOpenLink) {
    playerOpenLink.hidden = !hasStream;

    if (hasStream) {
      playerOpenLink.href = stationUrl(currentStation);
    } else {
      playerOpenLink.removeAttribute("href");
    }
  }
}


function clearAudioSource() {
  if (!audioNode) return;

  audioNode.pause();
  audioNode.removeAttribute("src");
  audioNode.load();
}

function waitForAudioPlaybackStart(timeoutMs = 4500) {
  if (!audioNode) return Promise.reject(new Error("Audio element is unavailable."));

  return new Promise((resolve, reject) => {
    let timeoutId = 0;

    const cleanup = () => {
      window.clearTimeout(timeoutId);
      audioNode.removeEventListener("playing", handleStarted);
      audioNode.removeEventListener("canplay", handleStarted);
      audioNode.removeEventListener("error", handleError);
    };

    const handleStarted = () => {
      cleanup();
      resolve();
    };

    const handleError = () => {
      cleanup();
      reject(new Error("stream failed to start after reload"));
    };

    timeoutId = window.setTimeout(() => {
      cleanup();
      reject(new Error("stream did not start after reload"));
    }, timeoutMs);

    audioNode.addEventListener("playing", handleStarted, { once: true });
    audioNode.addEventListener("canplay", handleStarted, { once: true });
    audioNode.addEventListener("error", handleError, { once: true });
  });
}

async function attemptCurrentStationPlayback(streamUrl) {
  if (!audioNode) return;

  logPlayerEvent("playback-attempt", { streamUrl });
  clearAudioSource();
  audioNode.src = streamUrl;
  audioNode.load();

  const playbackStarted = waitForAudioPlaybackStart();
  await audioNode.play();
  await playbackStarted;
  logPlayerEvent("playback-attempt-started", { streamUrl });
}

async function startCurrentStationPlayback(message = "Loading stream...") {
  if (!audioNode || !currentStation) return;

  logPlayerEvent("playback-start-request", { message });

  const streamUrl = stationUrl(currentStation);
  if (!streamUrl) {
    setPlayerState("error", "This station has no playable stream URL.");
    updatePlayerControls();
    return;
  }

  startingPlayback = true;
  setMediaSessionMetadata(currentStation);
  setPlayerState("loading", message);
  updatePlayerControls();

  try {
    try {
      await attemptCurrentStationPlayback(streamUrl);
    } catch (firstError) {
      logPlayerEvent("playback-retry", { error: String(firstError) });
      await attemptCurrentStationPlayback(streamUrl);
    }

    setPlayerState("playing", "Playing in browser.");
    await recordHistory(currentStation);
  } catch (error) {
    logPlayerEvent("playback-start-failed", { error: String(error) });
    audioNode.pause();
    setPlayerState(
      "error",
      `Browser playback failed. Try opening the stream directly. ${error}`,
    );
  } finally {
    startingPlayback = false;
    updatePlayerControls();
  }
}

function pauseCurrentStationPlayback(message = "Paused.") {
  if (!audioNode || !currentStation) return;

  logPlayerEvent("playback-pause-request", { message });
  softPausingPlayback = true;
  audioNode.pause();
  setMediaSessionMetadata(currentStation);
  setPlayerState("paused", message);
  updatePlayerControls();
  window.setTimeout(() => {
    softPausingPlayback = false;
  }, 0);
}

async function playStation(station) {
  if (!audioNode || !playerTitleNode || !playerOpenLink) return;

  const streamUrl = stationUrl(station);
  if (!streamUrl) {
    setPlayerState("error", "This station has no playable stream URL.");
    return;
  }

  currentStation = station;
  favoriteController.resetRecordedHistory();
  playerTitleNode.textContent = station.name || "Unknown station";
  playerOpenLink.href = streamUrl;
  playerOpenLink.hidden = false;

  await startCurrentStationPlayback("Loading stream...");
}

function stopPlayback() {
  if (!audioNode || !playerTitleNode || !playerOpenLink) return;

  logPlayerEvent("playback-stop-request");
  stoppingPlayback = true;
  clearAudioSource();

  currentStation = null;
  favoriteController.resetRecordedHistory();
  playerTitleNode.textContent = "Nothing playing yet";
  playerOpenLink.hidden = true;
  playerOpenLink.removeAttribute("href");

  clearMediaSessionMetadata();
  setPlayerState("idle", "Idle");
  updatePlayerControls();
  window.setTimeout(() => {
    stoppingPlayback = false;
  }, 0);
}

async function togglePlayback() {
  if (!audioNode || !currentStation) return;

  logPlayerEvent("playback-toggle");

  if (audioNode.paused || playerBar?.dataset.state === "loading") {
    await startCurrentStationPlayback("Resuming stream...");
  } else {
    pauseCurrentStationPlayback("Paused.");
  }
}

function renderStation(station) {
  const streamUrl = stationUrl(station);
  const homepage = stationHomepage(station);
  const tags = stationTags(station);
  const playCount = Number(station.play_count || 0);
  const lastPlayedAt = formatDisplayDateTime(station.last_played_at);
  const favoriteTags = Array.isArray(station.favorite_tags) ? station.favorite_tags : [];

  return `
    <article class="station-card">
      <header>
        <div>
          <h3>${escapeHtml(station.custom_name || station.name || "Unknown station")}</h3>
        </div>
        <div class="station-meta">
          <span>${escapeHtml(station.country || "Unknown")}</span>
          <span>${escapeHtml(station.codec || "Unknown codec")}</span>
          <span>${Number(station.bitrate || 0)} kbps</span>
          ${playCount ? `<span>${playCount} play${playCount === 1 ? "" : "s"}</span>` : ""}
          ${favoriteTags.length ? `<span>${escapeHtml(favoriteTags.join(", "))}</span>` : ""}
        </div>
      </header>

      ${
        tags
          ? `<p class="station-tags">${escapeHtml(tags)}</p>`
          : '<p class="station-tags">No tags available.</p>'
      }

      ${
        lastPlayedAt !== "unknown"
          ? `<p class="station-tags">Last played: ${lastPlayedAt}</p>`
          : ""
      }

      <div class="station-actions">
        ${
          streamUrl
            ? `<button type="button" data-play-station="${stationButtonPayload(
                station,
              )}">Play</button>`
            : ""
        }
        ${
          currentUser && streamUrl
            ? `<button type="button" data-add-favorite="${stationButtonPayload(
                station,
              )}">Add favorite</button>`
            : ""
        }
        ${
          currentUser && streamUrl
            ? `<button type="button" data-add-to-playlist="${stationButtonPayload(
                station,
              )}">Add to playlist</button>`
            : ""
        }
        ${
          currentUser && currentView === "favorites" && streamUrl
            ? `<button type="button" data-remove-favorite="${stationButtonPayload(
                station,
              )}">Remove favorite</button>`
            : ""
        }
        ${
          currentUser && currentView === "playlist" && streamUrl
            ? `<button type="button" data-remove-from-playlist="${stationButtonPayload(
                station,
              )}">Remove from playlist</button>`
            : ""
        }
        ${
          streamUrl
            ? `<a class="station-external-link" href="${escapeHtml(streamUrl)}" target="_blank" rel="noopener noreferrer">Stream URL</a>`
            : ""
        }
        ${
          homepage
            ? `<a class="station-external-link" href="${escapeHtml(homepage)}" target="_blank" rel="noopener noreferrer">Homepage</a>`
            : ""
        }
      </div>
    </article>
  `;
}

function parseStationButton(button) {
  const payload =
    button.getAttribute("data-play-station") ||
    button.getAttribute("data-add-favorite") ||
    button.getAttribute("data-remove-favorite") ||
    button.getAttribute("data-add-to-playlist") ||
    button.getAttribute("data-remove-from-playlist");

  if (!payload) return null;
  return JSON.parse(payload);
}

function bindResultActions() {
  document.querySelectorAll("[data-play-station]").forEach((button) => {
    button.addEventListener("click", () => {
      try {
        const station = parseStationButton(button);
        if (station) playStation(station);
      } catch (error) {
        setPlayerState("error", `Could not read station data. ${error}`);
      }
    });
  });

  document.querySelectorAll("[data-add-favorite]").forEach((button) => {
    button.addEventListener("click", () => {
      try {
        const station = parseStationButton(button);
        if (station) addFavorite(station);
      } catch (error) {
        setPlayerState("error", `Could not read station data. ${error}`);
      }
    });
  });

  document.querySelectorAll("[data-remove-favorite]").forEach((button) => {
    button.addEventListener("click", () => {
      try {
        const station = parseStationButton(button);
        if (station) removeFavorite(station);
      } catch (error) {
        setPlayerState("error", `Could not read station data. ${error}`);
      }
    });
  });

  document.querySelectorAll("[data-add-to-playlist]").forEach((button) => {
    button.addEventListener("click", () => {
      try {
        const station = parseStationButton(button);
        if (station) playlistController.addToPlaylist(station);
      } catch (error) {
        setPlayerState("error", `Could not read station data. ${error}`);
      }
    });
  });

  document.querySelectorAll("[data-remove-from-playlist]").forEach((button) => {
    button.addEventListener("click", () => {
      try {
        const station = parseStationButton(button);
        if (station) playlistController.removeFromPlaylist(station);
      } catch (error) {
        setPlayerState("error", `Could not read station data. ${error}`);
      }
    });
  });
}

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

function setupMediaSessionHandlers() {
  if (!("mediaSession" in navigator)) return;

  try {
    navigator.mediaSession.setActionHandler("play", () => {
      logPlayerEvent("media-session-play");
      if (currentStation) {
        void startCurrentStationPlayback("Starting stream from system controls...");
      }
    });
    navigator.mediaSession.setActionHandler("pause", () => {
      logPlayerEvent("media-session-pause");
      pauseCurrentStationPlayback();
    });
    navigator.mediaSession.setActionHandler("stop", () => {
      logPlayerEvent("media-session-stop", { behavior: "pause-with-station-preserved" });
      pauseCurrentStationPlayback("Playback paused by system controls.");
    });
  } catch (_error) {
    // Some browsers expose mediaSession without supporting all handlers.
  }
}

setupMediaSessionHandlers();

if (playerToggleButton) {
  playerToggleButton.addEventListener("click", togglePlayback);
}

if (playerStopButton) {
  playerStopButton.addEventListener("click", stopPlayback);
}

if (playerDebugEnableInput) {
  playerDebugEnableInput.addEventListener("change", () => {
    playerDebugController.applyState(playerDebugEnableInput.checked);
    logPlayerEvent("player-debug-toggle", { enabled: playerDebugController.enabled });
  });
}

if (audioNode) {
  audioNode.addEventListener("play", () => {
    logPlayerEvent("audio-play");
    if (currentStation && !startingPlayback && !softPausingPlayback && !stoppingPlayback) {
      startCurrentStationPlayback("Restarting live stream...");
    }
  });

  audioNode.addEventListener("playing", () => {
    logPlayerEvent("audio-playing");
    if (currentStation) {
      setPlayerState("playing", "Playing in browser.");
      recordHistory(currentStation);
    }

    updatePlayerControls();
  });

  audioNode.addEventListener("pause", () => {
    logPlayerEvent("audio-pause");
    if (currentStation && !startingPlayback && !stoppingPlayback) {
      setMediaSessionMetadata(currentStation);
      setPlayerState("paused", "Paused.");
    }
    updatePlayerControls();
  });

  audioNode.addEventListener("waiting", () => {
    logPlayerEvent("audio-waiting");
    if (currentStation) {
      setPlayerState("loading", "Buffering stream...");
    }
  });

  audioNode.addEventListener("error", () => {
    logPlayerEvent("audio-error");
    if (currentStation) {
      setPlayerState("error", "Browser playback failed. Try Open stream.");
    }
    updatePlayerControls();
  });

  ["abort", "canplay", "emptied", "ended", "loadstart", "stalled", "suspend"].forEach((eventName) => {
    audioNode.addEventListener(eventName, () => {
      logPlayerEvent(`audio-${eventName}`);
    });
  });
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    logPlayerEvent("document-visibilitychange");
  });
}

window.addEventListener("pagehide", () => {
  logPlayerEvent("window-pagehide");
});

window.addEventListener("pageshow", () => {
  logPlayerEvent("window-pageshow");
});

window.addEventListener("online", () => {
  logPlayerEvent("window-online");
});

window.addEventListener("offline", () => {
  logPlayerEvent("window-offline");
});


updatePlayerControls();


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
