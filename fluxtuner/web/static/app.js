const statusNode = document.querySelector("[data-status]");
const healthButton = document.querySelector("[data-health-check]");
const searchForm = document.querySelector("[data-search-form]");
const resultsNode = document.querySelector("[data-results]");
const resultCountNode = document.querySelector("[data-result-count]");

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

function renderStation(station) {
  const streamUrl = stationUrl(station);
  const homepage = station.homepage || "";
  const tags = stationTags(station);

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
        </div>
      </header>

      ${
        tags
          ? `<p class="station-tags">${escapeHtml(tags)}</p>`
          : '<p class="station-tags">No tags available.</p>'
      }

      <div class="station-actions">
        ${
          streamUrl
            ? `<a href="${escapeHtml(streamUrl)}" target="_blank" rel="noopener noreferrer">Open stream</a>`
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

if (healthButton) {
  healthButton.addEventListener("click", checkHealth);
}

if (searchForm) {
  searchForm.addEventListener("submit", searchStations);
}
