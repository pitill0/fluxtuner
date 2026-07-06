/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "/static/js/stations.js";

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

function renderPublicStats(contentNode, payload) {
  if (!contentNode) return;

  const topStations = Array.isArray(payload?.top_stations)
    ? payload.top_stations.slice(0, 3)
    : [];
  const totals = payload?.totals || {};
  const plays = Number(totals.plays || 0);
  const favorites = Number(totals.favorites || 0);
  const playlists = Number(totals.playlists || 0);
  const users = Number(totals.users || 0);

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
      ${renderPublicStatTile(users, "user", "users")}
    </div>
  `;
}

export function createPublicStatsController({ contentNode, messageNode, fetchImpl = fetch }) {
  let loaded = false;
  let loading = false;

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
      renderPublicStats(contentNode, payload);
      loaded = true;
      if (messageNode) {
        messageNode.textContent = "";
      }
    } catch (_error) {
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
  }

  return {
    loadPublicStats,
    reset,
  };
}
