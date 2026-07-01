/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

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

const MAX_PLAYLIST_NAME_LENGTH = 120;

let currentStation = null;
let recordedHistoryUrl = "";
let currentView = "search";
let currentPlaylistName = "";
let currentUser = null;
let csrfToken = "";
let setupAvailable = false;
let setupRequiresToken = false;
let adminUsersLoaded = false;
let dashboardLoaded = false;
let pendingPlaylistStation = null;
let publicStatsLoaded = false;
let publicStatsLoading = false;


function formatHealthSummary(payload) {
  const status = payload.status || payload.state || "ok";
  const version = payload.version ? ` · ${payload.version}` : "";
  const database = payload.database || payload.db || payload.storage || "";
  const databaseText = database ? ` · ${database}` : "";

  const details = `${version}${databaseText}`.trim();

  return {
    state: String(status).toUpperCase(),
    summary: details ? `${details} · checked now` : "checked now",
  };
}

function setHealthSummary(state, summary) {
  if (healthStateNode) {
    healthStateNode.textContent = state;
  }

  if (healthSummaryNode) {
    healthSummaryNode.textContent = summary;
  }
}

async function checkHealth() {
  if (statusNode) {
    statusNode.textContent = "Checking server...";
  }

  setHealthSummary("Checking", "Refreshing server status...");

  try {
    const response = await fetch("/api/health", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    const summary = formatHealthSummary(payload);

    setHealthSummary(summary.state, summary.summary);

    if (statusNode) {
      statusNode.textContent = JSON.stringify(payload, null, 2);
    }
  } catch (error) {
    setHealthSummary("Error", `Server check failed: ${error}`);

    if (statusNode) {
      statusNode.textContent = `Server check failed: ${error}`;
    }
  }
}


function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => {
    const replacements = {
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#039;",
    };

    return replacements[char];
  });
}

function safeExternalUrl(value) {
  const rawUrl = String(value || "").trim();
  if (!rawUrl) return "";

  if (!/^https?:\/\//i.test(rawUrl)) return "";

  try {
    const parsed = new URL(rawUrl);
    if (!["http:", "https:"].includes(parsed.protocol)) return "";
    return parsed.href;
  } catch {
    return "";
  }
}

function stationUrl(station) {
  return safeExternalUrl(station.url_resolved || station.url || "");
}

function stationHomepage(station) {
  return safeExternalUrl(station.homepage || "");
}

function stationTags(station) {
  const tags = String(station.tags || "").trim();
  if (!tags) return "";
  return tags.split(",").slice(0, 8).join(", ");
}

function stationButtonPayload(station) {
  return escapeHtml(JSON.stringify(station));
}

function setResultsHeader(kicker, title) {
  if (resultsKickerNode) {
    resultsKickerNode.textContent = kicker;
  }

  if (resultsTitleNode) {
    resultsTitleNode.textContent = title;
  }
}

function formatPublicStatCount(value, singular, plural) {
  const count = Number(value || 0);
  return `${count} ${count === 1 ? singular : plural}`;
}

function renderPublicStatTile(value, singular, plural) {
  const count = Number(value || 0);
  const label = count === 1 ? singular : plural;
  return `
    <article class="public-stat-tile">
      <strong>${escapeHtml(String(count))}</strong>
      <span>${escapeHtml(label)}</span>
    </article>
  `;
}

function renderPublicStats(payload) {
  if (!publicStatsContentNode) return;

  const topStations = Array.isArray(payload?.top_stations)
    ? payload.top_stations.slice(0, 3)
    : [];
  const totals = payload?.totals || {};
  const plays = Number(totals.plays || 0);
  const favorites = Number(totals.favorites || 0);
  const playlists = Number(totals.playlists || 0);

  if (!topStations.length && !plays && !favorites && !playlists) {
    publicStatsContentNode.innerHTML = '<p class="empty">No public activity yet.</p>';
    return;
  }

  const topStationsMarkup = topStations.length
    ? `
      <ol class="public-stats-list">
        ${topStations
          .map((station) => {
            const name = escapeHtml(station.name || "Unknown station");
            const playCount = formatPublicStatCount(station.play_count, "play", "plays");
            return `
              <li>
                <span>${name}</span>
                <strong>${escapeHtml(playCount)}</strong>
              </li>
            `;
          })
          .join("")}
      </ol>
    `
    : '<p class="empty">No top stations yet.</p>';

  publicStatsContentNode.innerHTML = `
    <section class="public-stats-card public-stats-top" aria-labelledby="public-stats-most-played-title">
      <div class="public-stats-card-heading">
        <p class="eyebrow">Most played</p>
        <h3 id="public-stats-most-played-title">Top stations</h3>
      </div>
      ${topStationsMarkup}
    </section>
    <div class="public-stats-totals" aria-label="Public activity totals">
      ${renderPublicStatTile(plays, "play", "plays")}
      ${renderPublicStatTile(favorites, "saved station", "saved stations")}
      ${renderPublicStatTile(playlists, "playlist", "playlists")}
    </div>
  `;
}

async function loadPublicStats(force = false) {
  if (!publicStatsContentNode || publicStatsLoading) return;
  if (publicStatsLoaded && !force) return;

  publicStatsLoading = true;
  if (publicStatsMessageNode) {
    publicStatsMessageNode.textContent = "Loading server activity...";
  }

  try {
    const response = await fetch("/api/public/stats", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderPublicStats(payload);
    publicStatsLoaded = true;
    if (publicStatsMessageNode) {
      publicStatsMessageNode.textContent = "";
    }
  } catch (_error) {
    publicStatsContentNode.innerHTML = '<p class="empty">Public activity is unavailable.</p>';
    if (publicStatsMessageNode) {
      publicStatsMessageNode.textContent = "";
    }
  } finally {
    publicStatsLoading = false;
  }
}


function clearAdminUsers() {
  adminUsersLoaded = false;

  if (adminMessageNode) {
    adminMessageNode.textContent = "";
  }

  if (adminUsersNode) {
    adminUsersNode.innerHTML = '<p class="empty">Admin users will appear here.</p>';
  }

  if (adminPasswordChangeRequestsNode) {
    adminPasswordChangeRequestsNode.innerHTML =
      '<p class="empty">Password change requests will appear here.</p>';
  }
}

function setAdminMessage(message) {
  if (adminMessageNode) {
    adminMessageNode.textContent = message || "";
  }
}

function renderAdminUsers(users) {
  if (!adminUsersNode) return;

  if (!users.length) {
    adminUsersNode.innerHTML = '<p class="empty">No web users found.</p>';
    return;
  }

  adminUsersNode.innerHTML = `
    <div class="admin-users-table" role="table" aria-label="Web users">
      <div class="admin-users-row admin-users-head" role="row">
        <span role="columnheader">User</span>
        <span role="columnheader">Admin</span>
        <span role="columnheader">Active</span>
        <span role="columnheader">Status</span>
        <span role="columnheader">Actions</span>
      </div>
      ${users
        .map((user) => {
          const username = escapeHtml(user.username || "");
          const displayName = escapeHtml(user.display_name || user.username || "");
          const adminLabel = user.is_admin ? "yes" : "no";
          const activeLabel = user.is_active ? "yes" : "no";
          const approvalStatus = escapeHtml(user.approval_status || "approved");

          return `
            <div class="admin-users-row" role="row">
              <span role="cell">
                <strong>${displayName}</strong>
                <small>${username}</small>
              </span>
              <span role="cell">${adminLabel}</span>
              <span role="cell">${activeLabel}</span>
              <span role="cell">${approvalStatus}</span>
              <span class="admin-user-actions" role="cell">
                ${
                  user.approval_status === "pending"
                    ? `<button type="button" data-admin-user-action="approve" data-admin-username="${username}">Approve</button>
                       <button type="button" data-admin-user-action="reject" data-admin-username="${username}">Reject</button>`
                    : ""
                }
                ${
                  user.is_active
                    ? `<button type="button" data-admin-user-action="deactivate" data-admin-username="${username}">Deactivate</button>`
                    : `<button type="button" data-admin-user-action="activate" data-admin-username="${username}">Activate</button>`
                }
                ${
                  user.is_admin
                    ? `<button type="button" data-admin-user-action="revoke-admin" data-admin-username="${username}">Remove admin</button>`
                    : `<button type="button" data-admin-user-action="grant-admin" data-admin-username="${username}">Make admin</button>`
                }
              </span>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}


function formatDisplayDateTime(value) {
  const text = String(value || "").trim();
  if (!text) return "unknown";

  let normalized = text.includes("T") ? text : text.replace(" ", "T");
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized);
  if (!hasTimezone) normalized = `${normalized}Z`;

  const parsed = new Date(normalized);
  if (Number.isNaN(parsed.getTime())) return escapeHtml(text);

  const year = parsed.getFullYear();
  const month = String(parsed.getMonth() + 1).padStart(2, "0");
  const day = String(parsed.getDate()).padStart(2, "0");
  const hour = String(parsed.getHours()).padStart(2, "0");
  const minute = String(parsed.getMinutes()).padStart(2, "0");

  return `${year}-${month}-${day} ${hour}:${minute}`;
}

function renderPasswordChangeRequests(requests) {
  if (!adminPasswordChangeRequestsNode) return;

  if (!requests.length) {
    adminPasswordChangeRequestsNode.innerHTML =
      '<p class="empty">No pending password change requests.</p>';
    return;
  }

  adminPasswordChangeRequestsNode.innerHTML = `
    <div class="admin-users-table password-change-requests-table" role="table" aria-label="Password change requests">
      <div class="admin-users-row password-change-request-row admin-users-head" role="row">
        <span role="columnheader">User</span>
        <span role="columnheader">Created</span>
        <span role="columnheader">Expires</span>
        <span role="columnheader">Note</span>
        <span role="columnheader">Actions</span>
      </div>
      ${requests
        .map((request) => {
          const id = Number(request.id || 0);
          const username = escapeHtml(request.username || "");
          const displayName = escapeHtml(request.display_name || request.username || "");
          const note = escapeHtml(request.note || "No note provided.");
          const createdAt = formatDisplayDateTime(request.created_at);
          const expiresAt = formatDisplayDateTime(request.expires_at);

          return `
            <div class="admin-users-row password-change-request-row" role="row">
              <span role="cell">
                <strong>${displayName}</strong>
                <small>${username}</small>
              </span>
              <span role="cell">${createdAt}</span>
              <span role="cell">${expiresAt}</span>
              <span role="cell"><small>${note}</small></span>
              <span class="admin-user-actions" role="cell">
                <button type="button" data-admin-password-change-action="approve" data-request-id="${id}">Approve</button>
                <button type="button" data-admin-password-change-action="reject" data-request-id="${id}">Reject</button>
              </span>
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

async function loadPasswordChangeRequests({ silent = false } = {}) {
  if (!currentUser || !currentUser.is_admin || !adminPasswordChangeRequestsNode) return;

  if (!silent) {
    setAdminMessage("Loading password change requests...");
  }

  try {
    const response = await apiFetch("/api/admin/password-change-requests", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Could not load password change requests.");
    }

    const payload = await response.json();
    renderPasswordChangeRequests(payload.requests || []);

    if (!silent) {
      setAdminMessage(`${payload.count ?? 0} password change request(s).`);
    }
  } catch (error) {
    setAdminMessage(String(error));
  }
}

async function mutatePasswordChangeRequest(requestId, action) {
  const id = Number(requestId || 0);
  if (!id || !["approve", "reject"].includes(action)) return;

  setAdminMessage("Updating password change request...");

  try {
    const response = await apiFetch(`/api/admin/password-change-requests/${id}/${action}`, {
      method: "POST",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Could not update password change request.");
    }

    setAdminMessage(
      action === "approve"
        ? "Password change approved. Active sessions for that user were revoked."
        : "Password change request rejected.",
    );
    await loadPasswordChangeRequests({ silent: true });
    await loadDashboard();
  } catch (error) {
    setAdminMessage(String(error));
  }
}

async function loadAdminUsers() {
  if (!currentUser || !currentUser.is_admin) return;

  setAdminMessage("Loading users...");

  try {
    const response = await apiFetch("/api/admin/users", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Could not load users.");
    }

    const payload = await response.json();
    adminUsersLoaded = true;
    renderAdminUsers(payload.users || []);
    await loadPasswordChangeRequests({ silent: true });
    setAdminMessage(`${payload.count ?? 0} web user(s).`);
  } catch (error) {
    setAdminMessage(String(error));
  }
}

async function createAdminUser(event) {
  event.preventDefault();

  if (!adminCreateUserForm) return;

  const formData = new FormData(adminCreateUserForm);
  const username = String(formData.get("username") || "").trim();
  const displayName = String(formData.get("display_name") || "").trim();
  const password = String(formData.get("password") || "");
  const confirmPassword = String(formData.get("confirm_password") || "");
  const isAdmin = formData.get("is_admin") === "on";

  if (password !== confirmPassword) {
    setAdminMessage("Passwords do not match.");
    return;
  }

  setAdminMessage("Creating user...");

  try {
    const response = await apiFetch("/api/admin/users", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        display_name: displayName,
        password,
        is_admin: isAdmin,
        is_active: true,
      }),
    });

    adminCreateUserForm.reset();

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Could not create user.");
    }

    setAdminMessage("User created.");
    await loadAdminUsers();
  } catch (error) {
    setAdminMessage(String(error));
  }
}

async function setAdminUserPassword(event) {
  event.preventDefault();

  if (!adminPasswordForm) return;

  const formData = new FormData(adminPasswordForm);
  const username = String(formData.get("username") || "").trim();
  const password = String(formData.get("password") || "");
  const confirmPassword = String(formData.get("confirm_password") || "");

  if (password !== confirmPassword) {
    setAdminMessage("Passwords do not match.");
    return;
  }

  setAdminMessage("Updating password...");

  try {
    const response = await apiFetch(
      `/api/admin/users/${encodeURIComponent(username)}/password`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ password }),
      },
    );

    adminPasswordForm.reset();

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Could not update password.");
    }

    setAdminMessage("Password updated. Active sessions for that user were revoked.");
    await loadAdminUsers();
  } catch (error) {
    setAdminMessage(String(error));
  }
}

async function mutateAdminUser(username, action) {
  const encodedUsername = encodeURIComponent(username);
  const routes = {
    activate: {
      method: "POST",
      url: `/api/admin/users/${encodedUsername}/activate`,
    },
    deactivate: {
      method: "POST",
      url: `/api/admin/users/${encodedUsername}/deactivate`,
    },
    approve: {
      method: "POST",
      url: `/api/admin/users/${encodedUsername}/approve`,
    },
    reject: {
      method: "POST",
      url: `/api/admin/users/${encodedUsername}/reject`,
    },
    "grant-admin": {
      method: "POST",
      url: `/api/admin/users/${encodedUsername}/admin`,
    },
    "revoke-admin": {
      method: "DELETE",
      url: `/api/admin/users/${encodedUsername}/admin`,
    },
  };

  const route = routes[action];
  if (!route) return;

  setAdminMessage("Updating user...");

  try {
    const response = await apiFetch(route.url, {
      method: route.method,
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Could not update user.");
    }

    setAdminMessage("User updated.");
    await loadAdminUsers();
  } catch (error) {
    setAdminMessage(String(error));
  }
}


function setDashboardMessage(message) {
  if (dashboardMessageNode) {
    dashboardMessageNode.textContent = message || "";
  }
}

function renderDashboardMetric(label, value) {
  return `
    <article class="dashboard-metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </article>
  `;
}

function renderDashboardStations(node, stations, emptyMessage) {
  if (!node) return;

  if (!stations.length) {
    node.innerHTML = `<p class="empty">${escapeHtml(emptyMessage)}</p>`;
    return;
  }

  node.innerHTML = stations.map(renderStation).join("");
  bindResultActions();
}

function renderDashboard(payload) {
  const userMetrics = payload.user || {};
  const adminMetrics = payload.admin || null;

  if (dashboardUserMetricsNode) {
    dashboardUserMetricsNode.innerHTML = [
      renderDashboardMetric("Favorites", Number(userMetrics.favorites_count || 0)),
      renderDashboardMetric("Playlists", Number(userMetrics.playlists_count || 0)),
      renderDashboardMetric("Playlist stations", Number(userMetrics.playlist_stations_count || 0)),
      renderDashboardMetric("History", Number(userMetrics.history_count || 0)),
    ].join("");
  }

  renderDashboardStations(
    dashboardRecentHistoryNode,
    userMetrics.recent_history || [],
    "No recent playback yet.",
  );
  renderDashboardStations(
    dashboardFavoriteHighlightsNode,
    userMetrics.favorite_highlights || [],
    "No favorites yet.",
  );

  if (dashboardAdminPanel) {
    dashboardAdminPanel.hidden = !adminMetrics;
  }

  if (dashboardAdminActionButton) {
    dashboardAdminActionButton.hidden = !adminMetrics;
  }

  if (dashboardAdminMetricsNode && adminMetrics) {
    dashboardAdminMetricsNode.innerHTML = [
      renderDashboardMetric("Users", Number(adminMetrics.users_count || 0)),
      renderDashboardMetric("New today", Number(adminMetrics.users_created_today || 0)),
      renderDashboardMetric("New 7 days", Number(adminMetrics.users_created_7_days || 0)),
      renderDashboardMetric("New 30 days", Number(adminMetrics.users_created_30_days || 0)),
      renderDashboardMetric("Pending approval", Number(adminMetrics.pending_users_count || 0)),
      renderDashboardMetric(
        "Password changes",
        Number(adminMetrics.pending_password_change_requests_count || 0),
      ),
      renderDashboardMetric("Server", String(adminMetrics.server?.status || "unknown")),
    ].join("");
  }
}

async function loadDashboard() {
  if (!currentUser || !dashboardPanel) return;

  currentView = "dashboard";
  currentPlaylistName = "";
  showDashboardView();
  setDashboardMessage("Loading dashboard...");

  try {
    const response = await apiFetch("/api/dashboard", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Could not load dashboard.");
    }

    const payload = await response.json();
    renderDashboard(payload);
    dashboardLoaded = true;
    setDashboardMessage("Dashboard updated.");
  } catch (error) {
    setDashboardMessage(String(error));
  }
}


function setAppContentVisible(visible) {
  appContentNodes.forEach((node) => {
    node.hidden = !visible;
  });
}

const THEME_STORAGE_KEY = "fluxtuner.theme";

function systemThemePreference() {
  if (window.matchMedia?.("(prefers-color-scheme: light)").matches) {
    return "light";
  }

  return "dark";
}

function storedThemePreference() {
  try {
    const storedTheme = window.localStorage.getItem(THEME_STORAGE_KEY);
    return storedTheme === "light" || storedTheme === "dark" ? storedTheme : null;
  } catch {
    return null;
  }
}

function saveThemePreference(theme) {
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Ignore storage failures. The selected theme still applies for this page load.
  }
}

function applyTheme(theme) {
  const nextTheme = theme === "light" ? "light" : "dark";

  document.documentElement.dataset.theme = nextTheme;
  document.documentElement.style.colorScheme = nextTheme;

  if (themeLabelNode) {
    themeLabelNode.textContent = nextTheme === "light" ? "Dark" : "Light";
  }

  if (themeToggleButton) {
    const label = nextTheme === "light" ? "Switch to dark theme" : "Switch to light theme";
    themeToggleButton.setAttribute("aria-label", label);
    themeToggleButton.title = label;
  }
}

function toggleTheme() {
  const currentTheme = document.documentElement.dataset.theme === "light" ? "light" : "dark";
  const nextTheme = currentTheme === "light" ? "dark" : "light";

  applyTheme(nextTheme);
  saveThemePreference(nextTheme);
}

applyTheme(storedThemePreference() || systemThemePreference());

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
    closeRegisterDialog();
    return true;
  }

  if (passwordChangeDialog && !passwordChangeDialog.hidden) {
    closePasswordChangeDialog();
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

function updateSetupUi() {
  const authenticated = Boolean(currentUser);

  setPlayerVisible(!setupAvailable && authenticated);

  if (appContent) {
    appContent.hidden = !authenticated || setupAvailable;
  }

  if (setupPanel) {
    setupPanel.hidden = !setupAvailable;
  }

  if (authPanel) {
    authPanel.hidden = setupAvailable || authenticated;
  }

  setAppContentVisible(!setupAvailable && authenticated);

  if (setupTokenField) {
    setupTokenField.hidden = !setupRequiresToken;
  }

  if (setupMessageNode && setupAvailable) {
    setupMessageNode.textContent = setupRequiresToken
      ? "Enter the setup verification value configured on the server."
      : "Local first-run setup is available. Create the first administrator.";
  }
}

async function loadSetupState() {
  try {
    const response = await fetch("/api/setup/status", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      setupAvailable = false;
      setupRequiresToken = false;
      updateSetupUi();
      await loadAuthState();
      return;
    }

    const payload = await response.json();
    setupAvailable = Boolean(payload.available);
    setupRequiresToken = Boolean(payload.requires_setup_token);
    updateSetupUi();

    if (!setupAvailable) {
      await loadAuthState();
      return;
    }

    currentUser = null;
    csrfToken = "";
    updateAuthUi();
  } catch (_error) {
    setupAvailable = false;
    setupRequiresToken = false;
    updateSetupUi();
    await loadAuthState();
  }
}

async function createFirstAdmin(event) {
  event.preventDefault();

  if (!setupForm || !setupMessageNode) return;

  const formData = new FormData(setupForm);
  const username = String(formData.get("username") || "").trim();
  const password = String(formData.get("password") || "");
  const confirmPassword = String(formData.get("confirm_password") || "");
  const setupToken = String(formData.get("setup_token") || "");

  if (password !== confirmPassword) {
    setupMessageNode.textContent = "Passwords do not match.";
    return;
  }

  setupMessageNode.textContent = "Creating administrator...";

  try {
    const body = {
      username,
      password,
    };

    if (setupRequiresToken) {
      body.setup_token = setupToken;
    }

    const response = await fetch("/api/setup/create-admin", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });

    setupForm.reset();

    if (!response.ok) {
      if (response.status === 429) {
        throw new Error("Too many setup attempts. Try again later.");
      }

      const payload = await response.json().catch(() => ({}));
      throw new Error(payload.detail || "Could not complete first-run setup.");
    }

    const payload = await response.json();
    currentUser = payload.user || null;
    csrfToken = payload.csrf_token || "";
    setupAvailable = false;
    setupRequiresToken = false;
    resetRadioBrowserView();
    updateSetupUi();
    updateAuthUi();
    scrollToSection(searchPanel);
  } catch (error) {
    currentUser = null;
    csrfToken = "";
    updateAuthUi();
    setupMessageNode.textContent = String(error);
  }
}


function updateAuthUi() {
  const authenticated = Boolean(currentUser);

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
    loadPublicStats();
  }

  setAppContentVisible(!setupAvailable && authenticated);

  const showAdminPanel = authenticated && Boolean(currentUser.is_admin) && !setupAvailable;

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

  if (!showAdminPanel) {
    clearAdminUsers();
  }

  if (loginForm) {
    loginForm.hidden = authenticated;
  }

  if (registerDialog && authenticated) {
    closeRegisterDialog();
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

async function apiFetch(url, options = {}) {
  const requestOptions = { ...options };
  const method = String(requestOptions.method || "GET").toUpperCase();

  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) {
    requestOptions.headers = {
      ...(requestOptions.headers || {}),
      "X-FluxTuner-CSRF": csrfToken,
    };
  }

  const response = await fetch(url, requestOptions);

  if (response.status === 401) {
    csrfToken = "";
    currentUser = null;
    csrfToken = "";
    updateAuthUi();
    renderAuthRequired();
  }

  return response;
}

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


function setPasswordChangeMessage(message) {
  if (passwordChangeMessageNode) {
    passwordChangeMessageNode.textContent = message || "";
  }
}

function openPasswordChangeDialog() {
  if (!passwordChangeDialog) return;

  setPasswordChangeMessage("");
  passwordChangeDialog.hidden = false;

  const firstInput = passwordChangeDialog.querySelector("input, button");
  if (firstInput) {
    firstInput.focus();
  }
}

function closePasswordChangeDialog() {
  if (!passwordChangeDialog) return;

  passwordChangeDialog.hidden = true;
  setPasswordChangeMessage("");

  if (passwordChangeForm) {
    passwordChangeForm.reset();
  }
}

async function requestPasswordChange(event) {
  event.preventDefault();

  if (!passwordChangeForm || !authMessageNode) return;

  const formData = new FormData(passwordChangeForm);
  const username = String(formData.get("username") || "").trim();
  const newPassword = String(formData.get("new_password") || "");
  const confirmPassword = String(formData.get("confirm_password") || "");
  const note = String(formData.get("note") || "").trim();

  if (newPassword !== confirmPassword) {
    setPasswordChangeMessage("Passwords do not match.");
    return;
  }

  setPasswordChangeMessage("Requesting password change...");

  try {
    const response = await fetch("/api/auth/password-change-requests", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        new_password: newPassword,
        note,
      }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || "Could not request password change.");
    }

    closePasswordChangeDialog();
    authMessageNode.textContent = payload.message || "Password change request received.";
  } catch (error) {
    setPasswordChangeMessage(String(error));
  }
}

function setRegisterMessage(message) {
  if (registerMessageNode) {
    registerMessageNode.textContent = message || "";
  }
}

function openRegisterDialog() {
  if (!registerDialog) return;

  setRegisterMessage("");
  registerDialog.hidden = false;

  const firstInput = registerDialog.querySelector("input, button");
  if (firstInput) {
    firstInput.focus();
  }
}

function closeRegisterDialog() {
  if (!registerDialog) return;

  registerDialog.hidden = true;
  setRegisterMessage("");

  if (registerForm) {
    registerForm.reset();
  }
}

async function registerAccount(event) {
  event.preventDefault();

  if (!registerForm || !authMessageNode) return;

  const formData = new FormData(registerForm);
  const username = String(formData.get("username") || "").trim();
  const password = String(formData.get("password") || "");
  const displayName = String(formData.get("display_name") || "").trim();
  const note = String(formData.get("note") || "").trim();

  setRegisterMessage("Requesting account...");

  try {
    const response = await fetch("/api/auth/register", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        username,
        password,
        display_name: displayName,
        note,
      }),
    });

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(payload.detail || "Could not request account.");
    }

    closeRegisterDialog();
    authMessageNode.textContent = payload.message || "Account request received.";
  } catch (error) {
    setRegisterMessage(String(error));
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
    publicStatsLoaded = false;
    resetRadioBrowserView();
    updateAuthUi();
    renderAuthRequired();
  }
}


function setPlayerState(state, message) {
  if (playerBar) {
    playerBar.dataset.state = state;
  }

  if (playerStatusNode) {
    playerStatusNode.textContent = message;
  }
}

function updatePlayerControls() {
  if (!audioNode || !playerToggleButton || !playerStopButton) return;

  const hasSource = Boolean(audioNode.currentSrc || audioNode.src);
  playerToggleButton.disabled = !hasSource;
  playerStopButton.disabled = !hasSource;

  if (audioNode.paused) {
    playerToggleButton.textContent = "Resume";
  } else {
    playerToggleButton.textContent = "Pause";
  }

  if (playerOpenLink) {
    const hasStream = Boolean(currentStation && stationUrl(currentStation));
    playerOpenLink.hidden = !hasStream;

    if (!hasStream) {
      playerOpenLink.removeAttribute("href");
    }
  }
}

async function recordHistory(station) {
  const url = stationUrl(station);
  if (!currentUser || !url || recordedHistoryUrl === url) return;

  recordedHistoryUrl = url;

  try {
    const response = await apiFetch("/api/history", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(station),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
  } catch (error) {
    console.warn("Could not record playback history", error);
  }
}

async function addFavorite(station) {
  const url = stationUrl(station);
  if (!url) {
    setPlayerState("error", "This station has no URL to save as favorite.");
    return;
  }

  try {
    const response = await apiFetch("/api/favorites", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify(station),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    setPlayerState(
      "idle",
      payload.added ? "Saved to favorites." : "Station is already in favorites.",
    );
  } catch (error) {
    setPlayerState("error", `Could not save favorite. ${error}`);
  }
}

async function removeFavorite(station) {
  const url = stationUrl(station);
  if (!url) {
    setPlayerState("error", "This station has no URL to remove.");
    return;
  }

  try {
    const response = await apiFetch(`/api/favorites?url=${encodeURIComponent(url)}`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    setPlayerState(
      "idle",
      payload.removed ? "Removed from favorites." : "Station was not in favorites.",
    );

    if (currentView === "favorites") {
      await loadFavorites();
    }
  } catch (error) {
    setPlayerState("error", `Could not remove favorite. ${error}`);
  }
}


function setPlaylistDialogMessage(message) {
  if (playlistMessageNode) {
    playlistMessageNode.textContent = message || "";
  }
}

function closePlaylistDialog() {
  pendingPlaylistStation = null;

  if (playlistDialog) {
    playlistDialog.hidden = true;
  }

  if (playlistForm) {
    playlistForm.reset();
  }

  setPlaylistDialogMessage("");
}

function renderPlaylistOptions(playlists) {
  if (!playlistSelect) return;

  const items = playlists || [];
  const options = items
    .map((playlist) => {
      const name = escapeHtml(playlist.name || "");
      const count = Number(playlist.count || 0);
      const suffix = `${count} station${count === 1 ? "" : "s"}`;
      return `<option value="${name}">${name} · ${suffix}</option>`;
    })
    .join("");

  playlistSelect.innerHTML =
    '<option value="">Choose existing playlist...</option>' +
    options;
}

async function loadPlaylistChoices() {
  if (!playlistSelect) return;

  playlistSelect.innerHTML = '<option value="">Loading playlists...</option>';

  const response = await apiFetch("/api/playlists", {
    headers: {
      Accept: "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }

  const payload = await response.json();
  renderPlaylistOptions(payload.playlists || []);

  if (!(payload.playlists || []).length) {
    setPlaylistDialogMessage("No playlists yet. Enter a new playlist name below.");
  } else {
    setPlaylistDialogMessage("Choose an existing playlist or enter a new name.");
  }
}

async function openPlaylistDialog(station) {
  const url = stationUrl(station);
  if (!url) {
    setPlayerState("error", "This station has no URL to add to a playlist.");
    return;
  }

  if (!playlistDialog || !playlistForm) {
    setPlayerState("error", "Playlist dialog is not available.");
    return;
  }

  pendingPlaylistStation = station;
  playlistDialog.hidden = false;

  if (playlistStationNameNode) {
    playlistStationNameNode.textContent = station.name
      ? `Station: ${station.name}`
      : "Station selected.";
  }

  setPlaylistDialogMessage("Loading playlists...");

  try {
    await loadPlaylistChoices();
  } catch (error) {
    setPlaylistDialogMessage(`Could not load playlists. ${error}`);
  }

  const firstInput = playlistDialog.querySelector("select, input, button");
  if (firstInput) {
    firstInput.focus();
  }
}

async function submitPlaylistDialog(event) {
  event.preventDefault();

  if (!pendingPlaylistStation || !playlistForm) {
    closePlaylistDialog();
    return;
  }

  const formData = new FormData(playlistForm);
  const selectedPlaylist = String(formData.get("playlist") || "").trim();
  const newPlaylist = String(formData.get("new_playlist") || "").trim();
  const playlistName = newPlaylist || selectedPlaylist;

  if (playlistName.length > MAX_PLAYLIST_NAME_LENGTH) {
    setPlaylistDialogMessage(`Playlist name must be ${MAX_PLAYLIST_NAME_LENGTH} characters or less.`);
    return;
  }

  if (!playlistName) {
    setPlaylistDialogMessage("Choose an existing playlist or enter a new playlist name.");
    return;
  }

  setPlaylistDialogMessage("Adding station...");

  try {
    const response = await apiFetch(
      `/api/playlists/${encodeURIComponent(playlistName)}/stations`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(pendingPlaylistStation),
      },
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    closePlaylistDialog();
    setPlayerState(
      "idle",
      payload.added
        ? `Added to playlist "${payload.name}".`
        : `Station is already in playlist "${payload.name}".`,
    );

    if (currentView === "playlists") {
      await loadPlaylists();
    } else if (currentView === "playlist" && currentPlaylistName === payload.name) {
      await loadPlaylistStations(currentPlaylistName);
    }
  } catch (error) {
    setPlaylistDialogMessage(`Could not add station. ${error}`);
  }
}


async function addToPlaylist(station) {
  await openPlaylistDialog(station);
}

async function removeFromPlaylist(station) {
  const url = stationUrl(station);
  if (!url || currentView !== "playlist") {
    return;
  }

  try {
    const response = await apiFetch(
      `/api/playlists/${encodeURIComponent(currentPlaylistName)}/stations?url=${encodeURIComponent(url)}`,
      {
        method: "DELETE",
        headers: {
          Accept: "application/json",
        },
      },
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    setPlayerState(
      "idle",
      payload.removed
        ? `Removed from playlist "${payload.name}".`
        : `Station was not in playlist "${payload.name}".`,
    );

    await loadPlaylistStations(currentPlaylistName);
  } catch (error) {
    setPlayerState("error", `Could not remove station from playlist. ${error}`);
  }
}

async function createPlaylistFromPrompt() {
  const playlistName = window.prompt("New playlist name:");
  if (!playlistName || !playlistName.trim()) {
    return;
  }

  const cleanPlaylistName = playlistName.trim();
  if (cleanPlaylistName.length > MAX_PLAYLIST_NAME_LENGTH) {
    setPlayerState("error", `Playlist name must be ${MAX_PLAYLIST_NAME_LENGTH} characters or less.`);
    return;
  }

  try {
    const response = await apiFetch("/api/playlists", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name: cleanPlaylistName }),
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    setPlayerState(
      "idle",
      payload.created
        ? `Created playlist "${payload.name}".`
        : `Playlist "${payload.name}" already exists.`,
    );

    await loadPlaylists();
  } catch (error) {
    setPlayerState("error", `Could not create playlist. ${error}`);
  }
}

async function deletePlaylist(name) {
  if (!window.confirm(`Delete playlist "${name}"? Stations will stay in favorites.`)) {
    return;
  }

  try {
    const response = await apiFetch(`/api/playlists/${encodeURIComponent(name)}`, {
      method: "DELETE",
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    setPlayerState(
      "idle",
      payload.removed
        ? `Deleted playlist "${payload.name}".`
        : `Playlist "${payload.name}" was not found.`,
    );

    await loadPlaylists();
  } catch (error) {
    setPlayerState("error", `Could not delete playlist. ${error}`);
  }
}

async function playStation(station) {
  if (!audioNode || !playerTitleNode || !playerOpenLink) return;

  const streamUrl = stationUrl(station);
  if (!streamUrl) {
    setPlayerState("error", "This station has no playable stream URL.");
    return;
  }

  currentStation = station;
  recordedHistoryUrl = "";
  playerTitleNode.textContent = station.name || "Unknown station";
  playerOpenLink.href = streamUrl;
  playerOpenLink.hidden = false;

  setPlayerState("loading", "Loading stream...");
  audioNode.src = streamUrl;

  try {
    await audioNode.play();
    setPlayerState("playing", "Playing in browser.");
    await recordHistory(station);
  } catch (error) {
    setPlayerState(
      "error",
      `Browser playback failed. Try opening the stream directly. ${error}`,
    );
  }

  updatePlayerControls();
}

function stopPlayback() {
  if (!audioNode || !playerTitleNode || !playerOpenLink) return;

  audioNode.pause();
  audioNode.removeAttribute("src");
  audioNode.load();

  currentStation = null;
  recordedHistoryUrl = "";
  playerTitleNode.textContent = "Nothing playing yet";
  playerOpenLink.hidden = true;
  playerOpenLink.removeAttribute("href");

  setPlayerState("idle", "Idle");
  updatePlayerControls();
}

async function togglePlayback() {
  if (!audioNode || !currentStation) return;

  if (audioNode.paused) {
    try {
      setPlayerState("loading", "Resuming stream...");
      await audioNode.play();
      setPlayerState("playing", "Playing in browser.");
      await recordHistory(currentStation);
    } catch (error) {
      setPlayerState("error", `Could not resume playback. ${error}`);
    }
  } else {
    audioNode.pause();
    setPlayerState("paused", "Paused.");
  }

  updatePlayerControls();
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
        if (station) addToPlaylist(station);
      } catch (error) {
        setPlayerState("error", `Could not read station data. ${error}`);
      }
    });
  });

  document.querySelectorAll("[data-remove-from-playlist]").forEach((button) => {
    button.addEventListener("click", () => {
      try {
        const station = parseStationButton(button);
        if (station) removeFromPlaylist(station);
      } catch (error) {
        setPlayerState("error", `Could not read station data. ${error}`);
      }
    });
  });
}

function renderResults(payload) {
  if (!resultsNode || !resultCountNode) return;

  const stations = payload.stations || [];
  resultCountNode.textContent = `${payload.count ?? stations.length} result${
    stations.length === 1 ? "" : "s"
  }`;

  if (!stations.length) {
    resultsNode.innerHTML = '<p class="empty">No stations found.</p>';
    return;
  }

  resultsNode.innerHTML = stations.map(renderStation).join("");
  bindResultActions();
}

function renderSearchError(error) {
  if (!resultsNode || !resultCountNode) return;

  resultCountNode.textContent = "Search failed.";
  resultsNode.innerHTML = `<p class="error">${escapeHtml(error)}</p>`;
}

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
    button.addEventListener("click", createPlaylistFromPrompt);
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
        deletePlaylist(name);
      }
    });
  });
}

async function searchStations(event) {
  event.preventDefault();

  if (!searchForm || !resultsNode || !resultCountNode) return;

  const formData = new FormData(searchForm);
  const params = new URLSearchParams();

  params.set("q", String(formData.get("q") || "").trim());
  params.set("country", String(formData.get("country") || "").trim());
  params.set("min_bitrate", String(formData.get("min_bitrate") || "0"));
  params.set("limit", "25");

  if (!params.get("q") && !params.get("country")) {
    renderSearchError("Search text or country is required.");
    return;
  }

  currentView = "search";
  currentPlaylistName = "";
  setResultsHeader("Radio Browser", "Search stations");
  resultCountNode.textContent = "Searching...";
  resultsNode.innerHTML = '<p class="empty">Searching Radio Browser...</p>';

  try {
    const response = await fetch(`/api/search?${params.toString()}`, {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderResults(payload);
  } catch (error) {
    renderSearchError(error);
  }
}

async function loadHistory() {
  if (!resultsNode || !resultCountNode) return;

  currentView = "history";
  currentPlaylistName = "";
  setResultsHeader("Playback", "History");
  resultCountNode.textContent = "Loading history...";
  resultsNode.innerHTML = '<p class="empty">Loading playback history...</p>';

  try {
    const response = await fetch("/api/history?limit=25", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderResults(payload);
  } catch (error) {
    renderSearchError(error);
  }
}

async function loadFavorites() {
  if (!resultsNode || !resultCountNode) return;

  currentView = "favorites";
  currentPlaylistName = "";
  setResultsHeader("Library", "Favorites");
  resultCountNode.textContent = "Loading favorites...";
  resultsNode.innerHTML = '<p class="empty">Loading favorites...</p>';

  try {
    const response = await apiFetch("/api/favorites", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderResults(payload);
  } catch (error) {
    renderSearchError(error);
  }
}

async function loadPlaylists() {
  if (!resultsNode || !resultCountNode) return;

  currentView = "playlists";
  currentPlaylistName = "";
  setResultsHeader("Library", "Playlists");
  resultCountNode.textContent = "Loading playlists...";
  resultsNode.innerHTML = '<p class="empty">Loading playlists...</p>';

  try {
    const response = await apiFetch("/api/playlists", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderPlaylists(payload);
  } catch (error) {
    renderSearchError(error);
  }
}

async function loadPlaylistStations(name) {
  if (!resultsNode || !resultCountNode) return;

  currentView = "playlist";
  currentPlaylistName = name;
  setResultsHeader("Playlist", name);
  resultCountNode.textContent = "Loading playlist...";
  resultsNode.innerHTML = '<p class="empty">Loading playlist stations...</p>';

  try {
    const response = await apiFetch(
      `/api/playlists/${encodeURIComponent(name)}/stations`,
      {
        headers: {
          Accept: "application/json",
        },
      },
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderResults(payload);
  } catch (error) {
    renderSearchError(error);
  }
}

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
    mutateAdminUser(button.dataset.adminUsername || "", button.dataset.adminUserAction || "");
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
  playlistForm.addEventListener("submit", submitPlaylistDialog);
}

playlistCancelButtons.forEach((button) => {
  button.addEventListener("click", closePlaylistDialog);
});

if (setupForm) {
  setupForm.addEventListener("submit", createFirstAdmin);
}

if (loginForm) {
  loginForm.addEventListener("submit", login);
}

if (registerOpenButton) {
  registerOpenButton.addEventListener("click", openRegisterDialog);
}

if (passwordChangeOpenButton) {
  passwordChangeOpenButton.addEventListener("click", openPasswordChangeDialog);
}

passwordChangeCancelButtons.forEach((button) => {
  button.addEventListener("click", closePasswordChangeDialog);
});

if (passwordChangeForm) {
  passwordChangeForm.addEventListener("submit", requestPasswordChange);
}

registerCancelButtons.forEach((button) => {
  button.addEventListener("click", closeRegisterDialog);
});

if (registerForm) {
  registerForm.addEventListener("submit", registerAccount);
}

if (logoutButton) {
  logoutButton.addEventListener("click", logout);
}

if (healthButton) {
  healthButton.addEventListener("click", checkHealth);
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

    if (!adminUsersLoaded) {
      adminUsersLoaded = true;
      await loadAdminUsers();
    }

    scrollToSection(adminPanel);
  });
}

if (searchForm) {
  searchForm.addEventListener("submit", searchStations);
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

if (playerToggleButton) {
  playerToggleButton.addEventListener("click", togglePlayback);
}

if (playerStopButton) {
  playerStopButton.addEventListener("click", stopPlayback);
}

if (audioNode) {
  audioNode.addEventListener("playing", () => {
    setPlayerState("playing", "Playing in browser.");

    if (currentStation) {
      recordHistory(currentStation);
    }

    updatePlayerControls();
  });

  audioNode.addEventListener("pause", () => {
    if (currentStation) {
      setPlayerState("paused", "Paused.");
    }
    updatePlayerControls();
  });

  audioNode.addEventListener("waiting", () => {
    if (currentStation) {
      setPlayerState("loading", "Buffering stream...");
    }
  });

  audioNode.addEventListener("error", () => {
    if (currentStation) {
      setPlayerState("error", "Browser playback failed. Try Open stream.");
    }
    updatePlayerControls();
  });
}

updatePlayerControls();

async function initializeAuthFlow() {
  updateSetupUi();
  updateAuthUi();

  await loadSetupState();

  if (setupAvailable) {
    updateSetupUi();
    updateAuthUi();
    return;
  }

  await loadAuthState();
}

initializeAuthFlow();
