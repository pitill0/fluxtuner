const statusNode = document.querySelector("[data-status]");
const healthButton = document.querySelector("[data-health-check]");
const searchForm = document.querySelector("[data-search-form]");
const resultsNode = document.querySelector("[data-results]");
const resultCountNode = document.querySelector("[data-result-count]");
const resultsKickerNode = document.querySelector("[data-results-kicker]");
const resultsTitleNode = document.querySelector("[data-results-title]");
const loadHistoryButton = document.querySelector("[data-load-history]");

const playerBar = document.querySelector("[data-player-bar]");
const audioNode = document.querySelector("[data-audio]");
const playerTitleNode = document.querySelector("[data-player-title]");
const playerStatusNode = document.querySelector("[data-player-status]");
const playerToggleButton = document.querySelector("[data-player-toggle]");
const playerStopButton = document.querySelector("[data-player-stop]");
const playerOpenLink = document.querySelector("[data-player-open]");

let currentStation = null;
let recordedHistoryUrl = "";

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
  if (!url || recordedHistoryUrl === url) return;

  recordedHistoryUrl = url;

  try {
    const response = await fetch("/api/history", {
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

  return `
    <article class="station-card">
      <header>
        <div>
          <h3>${escapeHtml(station.name || "Unknown station")}</h3>
        </div>
        <div class="station-meta">
          <span>${escapeHtml(station.country || "Unknown")}</span>
          <span>${escapeHtml(station.codec || "Unknown codec")}</span>
          <span>${Number(station.bitrate || 0)} kbps</span>
          ${playCount ? `<span>${playCount} play${playCount === 1 ? "" : "s"}</span>` : ""}
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

function bindResultActions() {
  document.querySelectorAll("[data-play-station]").forEach((button) => {
    button.addEventListener("click", () => {
      const payload = button.getAttribute("data-play-station");
      if (!payload) return;

      try {
        playStation(JSON.parse(payload));
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

if (healthButton) {
  healthButton.addEventListener("click", checkHealth);
}

if (searchForm) {
  searchForm.addEventListener("submit", searchStations);
}

if (loadHistoryButton) {
  loadHistoryButton.addEventListener("click", loadHistory);
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
