/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "./stations.js";

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

function renderPublicStats(contentNode, payload, trendingPayload = null, featuredPayload = null) {
  if (!contentNode) return;

  const topStations = Array.isArray(payload?.top_stations)
    ? payload.top_stations.slice(0, 3)
    : [];
  const totals = payload?.totals || {};
  const plays = Number(totals.plays || 0);
  const favorites = Number(totals.favorites || 0);
  const playlists = Number(totals.playlists || 0);
  const users = Number(totals.users || 0);
  const trendingStations = Array.isArray(trendingPayload?.stations)
    ? trendingPayload.stations.slice(0, 3)
    : [];
  const featuredName = typeof featuredPayload?.station?.name === "string"
    ? featuredPayload.station.name.trim() : "";
  const featuredSelection = typeof featuredPayload?.selection === "string" &&
    /^v1\.[0-9]{10}\.[A-Za-z0-9_-]{43}$/.test(featuredPayload.selection)
    ? featuredPayload.selection : "";

  if (!topStations.length && !plays && !favorites && !playlists && !users) {
    contentNode.innerHTML = '<p class="empty">No public activity yet.</p>';
    return;
  }

  const topStationsMarkup = topStations.length
    ? `
      <ol class="public-stats-list">
        ${topStations
          .map((station) => {
            const name = escapeHtml(station.name || "Unknown station");
            const playCount = formatPublicStatCount(station.play_count, "play", "plays");
            const artworkUrl = String(station.artwork_url || "");
            const safeArtworkUrl = /^\/api\/public\/stations\/[1-9][0-9]*\/artwork$/.test(artworkUrl)
              ? artworkUrl : "";
            return `
              <li>
                <span class="public-station-artwork" aria-hidden="true">
                  <span class="public-station-artwork-fallback">♫</span>
                  ${safeArtworkUrl ? `<img src="${safeArtworkUrl}" alt="" loading="lazy" decoding="async">` : ""}
                </span>
                <span>${name}</span>
                <strong>${escapeHtml(playCount)}</strong>
              </li>
            `;
          })
          .join("")}
      </ol>
    `
    : '<p class="empty">No top stations yet.</p>';

  const trendingMarkup = trendingStations.length
    ? `<ol class="public-trending-list">
        ${trendingStations.map((station) => `<li>${escapeHtml(station.name || "Unknown station")}</li>`).join("")}
      </ol>`
    : `<p class="empty">${trendingPayload === null
      ? "Weekly trends are unavailable right now."
      : "Weekly trends will appear when enough listening activity is available."}</p>`;

  contentNode.innerHTML = `
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
      ${renderPublicStatTile(users, "active user", "active users")}
    </div>
    <section class="public-stats-card public-stats-trending" aria-labelledby="public-stats-trending-title">
      <div class="public-stats-card-heading">
        <p class="eyebrow">This week</p>
        <h3 id="public-stats-trending-title">Trending stations</h3>
        <p class="public-trending-note">Growing in popularity over the last seven completed UTC days.</p>
      </div>
      ${trendingMarkup}
    </section>
    <section class="public-stats-card public-stats-featured" aria-labelledby="public-stats-featured-title">
      <div class="public-stats-card-heading">
        <p class="eyebrow">Discover</p>
        <h3 id="public-stats-featured-title">Station to discover</h3>
        <p class="public-trending-note">A new suggestion each UTC day, from the public station directory.</p>
      </div>
      ${featuredName
        ? `<div class="public-featured-choice">
             <p class="public-featured-name">${escapeHtml(featuredName)}</p>
             ${featuredSelection ? '<button type="button" class="public-featured-save" data-featured-save>Save for listening</button>' : ""}
           </div>`
        : '<p class="empty">A station suggestion is not available yet.</p>'}
    </section>
  `;
  contentNode.querySelectorAll(".public-station-artwork img").forEach((img) => {
    img.addEventListener("error", () => { img.hidden = true; }, { once: true });
  });
}

export function createPublicStatsController({
  contentNode, messageNode, fetchImpl = fetch, onSelect = () => {},
}) {
  let loaded = false;
  let loading = false;
  let selection = "";

  contentNode?.addEventListener("click", (event) => {
    if (!event.target.closest("[data-featured-save]") || !selection) return;
    onSelect(selection);
  });

  async function loadPublicStats(force = false) {
    if (!contentNode || loading) return;
    if (loaded && !force) return;

    loading = true;
    if (messageNode) {
      messageNode.textContent = "Loading server activity...";
    }

    try {
      const response = await fetchImpl("/api/public/stats", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      let trendingPayload = null;
      let featuredPayload = null;
      try {
        const trendingResponse = await fetchImpl("/api/public/trending", {
          headers: { Accept: "application/json" },
        });
        if (trendingResponse.ok) {
          trendingPayload = await trendingResponse.json();
        }
      } catch (_trendingError) {
        // Trending availability must never hide existing public statistics.
      }
      try {
        const featuredResponse = await fetchImpl("/api/public/featured", {
          headers: { Accept: "application/json" },
        });
        if (featuredResponse.ok) featuredPayload = await featuredResponse.json();
      } catch (_featuredError) {
        // Featured availability must never hide existing public statistics.
      }
      selection = typeof featuredPayload?.selection === "string" ? featuredPayload.selection : "";
      renderPublicStats(contentNode, payload, trendingPayload, featuredPayload);
      loaded = true;
      if (messageNode) {
        messageNode.textContent = "";
      }
    } catch (_error) {
      selection = "";
      contentNode.innerHTML = '<p class="empty">Public activity is unavailable.</p>';
      if (messageNode) {
        messageNode.textContent = "";
      }
    } finally {
      loading = false;
    }
  }

  function reset() {
    loaded = false;
    selection = "";
  }

  return {
    loadPublicStats,
    reset,
  };
}
