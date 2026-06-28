const statusNode = document.querySelector("[data-status]");
const healthButton = document.querySelector("[data-health-check]");
const searchForm = document.querySelector("[data-search-form]");
const resultsNode = document.querySelector("[data-results]");
const resultCountNode = document.querySelector("[data-result-count]");
const resultsKickerNode = document.querySelector("[data-results-kicker]");
const resultsTitleNode = document.querySelector("[data-results-title]");
const loadHistoryButton = document.querySelector("[data-load-history]");
const loadFavoritesButton = document.querySelector("[data-load-favorites]");
const loadPlaylistsButton = document.querySelector("[data-load-playlists]");
const authPanel = document.querySelector("[data-auth-panel]");
const loginForm = document.querySelector("[data-login-form]");
const authMessageNode = document.querySelector("[data-auth-message]");
const authUserPanel = document.querySelector("[data-auth-user]");
const authUsernameNode = document.querySelector("[data-auth-username]");
const logoutButton = document.querySelector("[data-logout]");
const privateActionNodes = document.querySelectorAll("[data-private-action]");
const setupPanel = document.querySelector("[data-setup-panel]");
const setupForm = document.querySelector("[data-setup-form]");
const setupTokenField = document.querySelector("[data-setup-token-field]");
const setupMessageNode = document.querySelector("[data-setup-message]");
const adminPanel = document.querySelector("[data-admin-panel]");
const adminLoadUsersButton = document.querySelector("[data-admin-load-users]");
const adminCreateUserForm = document.querySelector("[data-admin-create-user-form]");
const adminPasswordForm = document.querySelector("[data-admin-password-form]");
const adminMessageNode = document.querySelector("[data-admin-message]");
const adminUsersNode = document.querySelector("[data-admin-users]");

const playerBar = document.querySelector("[data-player-bar]");
const audioNode = document.querySelector("[data-audio]");
const playerTitleNode = document.querySelector("[data-player-title]");
const playerStatusNode = document.querySelector("[data-player-status]");
const playerToggleButton = document.querySelector("[data-player-toggle]");
const playerStopButton = document.querySelector("[data-player-stop]");
const playerOpenLink = document.querySelector("[data-player-open]");

let currentStation = null;
let recordedHistoryUrl = "";
let currentView = "search";
let currentPlaylistName = "";
let currentUser = null;
let csrfToken = "";
let setupAvailable = false;
let setupRequiresToken = false;

async function checkHealth() {
  if (!statusNode) return;

  statusNode.textContent = "Checking server...";

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
    statusNode.textContent = JSON.stringify(payload, null, 2);
  } catch (error) {
    statusNode.textContent = `Server check failed: ${error}`;
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

function stationUrl(station) {
  return station.url_resolved || station.url || "";
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
        <span role="columnheader">Actions</span>
      </div>
      ${users
        .map((user) => {
          const username = escapeHtml(user.username || "");
          const displayName = escapeHtml(user.display_name || user.username || "");
          const adminLabel = user.is_admin ? "yes" : "no";
          const activeLabel = user.is_active ? "yes" : "no";

          return `
            <div class="admin-users-row" role="row">
              <span role="cell">
                <strong>${displayName}</strong>
                <small>${username}</small>
              </span>
              <span role="cell">${adminLabel}</span>
              <span role="cell">${activeLabel}</span>
              <span class="admin-user-actions" role="cell">
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
    renderAdminUsers(payload.users || []);
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


function updateSetupUi() {
  if (setupPanel) {
    setupPanel.hidden = !setupAvailable;
  }

  if (authPanel) {
    authPanel.hidden = setupAvailable;
  }

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
      await       return;
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
    updateSetupUi();
    updateAuthUi();
  } catch (error) {
    currentUser = null;
    csrfToken = "";
    updateAuthUi();
    setupMessageNode.textContent = String(error);
  }
}


function updateAuthUi() {
  const authenticated = Boolean(currentUser);

  if (authPanel) {
    authPanel.dataset.authenticated = authenticated ? "true" : "false";
  }

  if (adminPanel) {
    adminPanel.hidden = !authenticated || !currentUser.is_admin || setupAvailable;
  }

  if (loginForm) {
    loginForm.hidden = authenticated;
  }

  if (authUserPanel) {
    authUserPanel.hidden = !authenticated;
  }

  if (authUsernameNode) {
    authUsernameNode.textContent = authenticated
      ? `Signed in as ${currentUser.username}`
      : "";
  }

  privateActionNodes.forEach((node) => {
    node.disabled = !authenticated;
  });

  if (authMessageNode) {
    authMessageNode.textContent = authenticated
      ? "Private library tools are available."
      : "Sign in to use favorites, history and playlists.";
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
    updateAuthUi();
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

      throw new Error("Invalid username or password.");
    }

    const payload = await response.json();
    currentUser = payload.user || null;
    csrfToken = payload.csrf_token || "";
    updateAuthUi();
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
    currentUser = null;
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

async function addToPlaylist(station) {
  const url = stationUrl(station);
  if (!url) {
    setPlayerState("error", "This station has no URL to add to a playlist.");
    return;
  }

  const playlistName = window.prompt("Playlist name:");
  if (!playlistName || !playlistName.trim()) {
    return;
  }

  try {
    const response = await apiFetch(
      `/api/playlists/${encodeURIComponent(playlistName.trim())}/stations`,
      {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(station),
      },
    );

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    setPlayerState(
      "idle",
      payload.added
        ? `Added to playlist "${payload.name}".`
        : `Station is already in playlist "${payload.name}".`,
    );
  } catch (error) {
    setPlayerState("error", `Could not add station to playlist. ${error}`);
  }
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

  try {
    const response = await apiFetch("/api/playlists", {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ name: playlistName.trim() }),
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
  const homepage = station.homepage || "";
  const tags = stationTags(station);
  const playCount = Number(station.play_count || 0);
  const lastPlayedAt = station.last_played_at || "";
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
        lastPlayedAt
          ? `<p class="station-tags">Last played: ${escapeHtml(lastPlayedAt)}</p>`
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
            ? `<a href="${escapeHtml(streamUrl)}" target="_blank" rel="noopener noreferrer">Stream URL</a>`
            : ""
        }
        ${
          homepage
            ? `<a href="${escapeHtml(homepage)}" target="_blank" rel="noopener noreferrer">Homepage</a>`
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

if (setupForm) {
  setupForm.addEventListener("submit", createFirstAdmin);
}

if (loginForm) {
  loginForm.addEventListener("submit", login);
}

if (logoutButton) {
  logoutButton.addEventListener("click", logout);
}

if (healthButton) {
  healthButton.addEventListener("click", checkHealth);
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
loadAuthState();
async function initializeAuthFlow() {
  updateSetupUi();
  updateAuthUi();
  await loadSetupState();
}

initializeAuthFlow();
