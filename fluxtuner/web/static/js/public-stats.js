/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "./stations.js";

function renderPublicStatTile(value, singular, plural, key) {
  const count = Number(value || 0);
  const label = count === 1 ? singular : plural;
  return `
    <article class="public-stat-tile">
      <strong data-render-number="${count}">${escapeHtml(String(count))}</strong>
      <span data-render-i18n="${key}" data-render-count="${count}">${escapeHtml(label)}</span>
    </article>
  `;
}

function renderPublicStats(contentNode, payload, trendingPayload = null, featuredPayload = null, genresPayload = null, presentation) {
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
  const popularGenres = Array.isArray(genresPayload?.genres)
    ? genresPayload.genres.filter((genre) => typeof genre?.name === "string" && genre.name.trim()).slice(0, 5)
    : [];
  const featuredName = typeof featuredPayload?.station?.name === "string"
    ? featuredPayload.station.name.trim() : "";
  const featuredSelection = typeof featuredPayload?.selection === "string" &&
    /^v1\.[0-9]{10}\.[A-Za-z0-9_-]{43}$/.test(featuredPayload.selection)
    ? featuredPayload.selection : "";

  // A newly installed server may already have an eligible discovery candidate
  // before anyone has played or saved a station. Do not hide that suggestion.
  if (!topStations.length && !plays && !favorites && !playlists && !users && !featuredName && !popularGenres.length) {
    contentNode.innerHTML = '<p class="empty" data-render-i18n="public.no_activity">No public activity yet.</p>';
    presentation?.bindRendered(contentNode);
    return;
  }

  const topStationsMarkup = topStations.length
    ? `
      <ol class="public-stats-list">
        ${topStations
          .map((station) => {
            const name = escapeHtml(station.name || "Unknown station");
            const count = Number(station.play_count || 0);
            const label = count === 1 ? "play" : "plays";
            const artworkUrl = String(station.artwork_url || "");
            const safeArtworkUrl = /^\/api\/public\/stations\/[1-9][0-9]*\/artwork$/.test(artworkUrl)
              ? artworkUrl : "";
            return `
              <li>
                <span class="public-station-artwork" aria-hidden="true">
                  <span class="public-station-artwork-fallback">♫</span>
                  ${safeArtworkUrl ? `<img src="${safeArtworkUrl}" alt="" loading="lazy" decoding="async">` : ""}
                </span>
                <span${station.name ? "" : ' data-render-i18n="station.unknown_station"'}>${name}</span>
                <strong data-render-i18n="public.play_count" data-render-count="${count}" data-render-formatted-count>${count} ${label}</strong>
              </li>
            `;
          })
          .join("")}
      </ol>
    `
    : '<p class="empty" data-render-i18n="public.no_top">No top stations yet.</p>';

  const trendingMarkup = trendingStations.length
    ? `<ol class="public-trending-list">
        ${trendingStations.map((station) => `<li${station.name ? "" : ' data-render-i18n="station.unknown_station"'}>${escapeHtml(station.name || "Unknown station")}</li>`).join("")}
      </ol>`
    : `<p class="empty" data-render-i18n="${trendingPayload === null ? "public.trends_unavailable" : "public.trends_empty"}">${trendingPayload === null
      ? "Weekly trends are unavailable right now."
      : "Weekly trends will appear when enough listening activity is available."}</p>`;

  const genresMarkup = popularGenres.length
    ? `<ul class="public-genres-list">
        ${popularGenres.map((genre) => `<li>${escapeHtml(genre.name.trim())}</li>`).join("")}
      </ul>`
    : `<p class="empty" data-render-i18n="${genresPayload === null ? "public.genres_unavailable" : "public.genres_empty"}">${genresPayload === null
      ? "Popular genres are unavailable right now."
      : "Popular genres will appear when enough listening activity is available."}</p>`;

  contentNode.innerHTML = `
    <section class="public-stats-card public-stats-top" aria-labelledby="public-stats-most-played-title">
      <div class="public-stats-card-heading">
        <p class="eyebrow" data-render-i18n="public.most_played">Most played</p>
        <h3 id="public-stats-most-played-title" data-render-i18n="public.top_stations">Top stations</h3>
      </div>
      ${topStationsMarkup}
    </section>
    <div class="public-stats-totals" aria-label="Public activity totals" data-render-aria="public.totals">
      ${renderPublicStatTile(plays, "play", "plays", "public.count_play")}
      ${renderPublicStatTile(favorites, "saved station", "saved stations", "public.count_favorite")}
      ${renderPublicStatTile(playlists, "playlist", "playlists", "public.count_playlist")}
      ${renderPublicStatTile(users, "active user", "active users", "public.count_user")}
    </div>
    <section class="public-stats-card public-stats-trending" aria-labelledby="public-stats-trending-title">
      <div class="public-stats-card-heading">
        <p class="eyebrow" data-render-i18n="public.this_week">This week</p>
        <h3 id="public-stats-trending-title" data-render-i18n="public.trending">Trending stations</h3>
        <p class="public-trending-note" data-render-i18n="public.trending_note">Growing in popularity over the last seven completed UTC days.</p>
      </div>
      ${trendingMarkup}
    </section>
    <section class="public-stats-card public-stats-featured" aria-labelledby="public-stats-featured-title">
      <div class="public-stats-card-heading">
        <p class="eyebrow" data-render-i18n="public.discover">Discover</p>
        <h3 id="public-stats-featured-title" data-render-i18n="public.featured">Station to discover</h3>
        <p class="public-trending-note" data-render-i18n="public.featured_note">A new suggestion each UTC day, from the public station directory.</p>
      </div>
      ${featuredName
        ? `<div class="public-featured-choice">
             <p class="public-featured-name">${escapeHtml(featuredName)}</p>
             ${featuredSelection ? '<button type="button" class="public-featured-save" data-featured-save data-render-i18n="public.save">Save for listening</button>' : ""}
           </div>`
        : '<p class="empty" data-render-i18n="public.featured_empty">A station suggestion is not available yet.</p>'}
    </section>
    <section class="public-stats-card public-stats-genres" aria-labelledby="public-stats-genres-title">
      <div class="public-stats-card-heading">
        <p class="eyebrow" data-render-i18n="public.explore">Explore</p>
        <h3 id="public-stats-genres-title" data-render-i18n="public.genres">Popular genres</h3>
        <p class="public-trending-note" data-render-i18n="public.genres_note">Most listened-to genres over the last seven completed UTC days.</p>
      </div>
      ${genresMarkup}
    </section>
  `;
  presentation?.bindRendered(contentNode);
  contentNode.querySelectorAll(".public-station-artwork img").forEach((img) => {
    img.addEventListener("error", () => { img.hidden = true; }, { once: true });
  });
}

export function createPublicStatsController({
  presentation, contentNode, messageNode, fetchImpl = fetch, onSelect = () => {},
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
      if (presentation) presentation.present(messageNode, "public.loading_server", "Loading server activity...");
      else messageNode.textContent = "Loading server activity...";
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
      let genresPayload = null;
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
      try {
        const genresResponse = await fetchImpl("/api/public/genres", {
          headers: { Accept: "application/json" },
        });
        if (genresResponse.ok) genresPayload = await genresResponse.json();
      } catch (_genresError) {
        // Genre availability must never hide existing public statistics.
      }
      selection = typeof featuredPayload?.selection === "string" ? featuredPayload.selection : "";
      renderPublicStats(contentNode, payload, trendingPayload, featuredPayload, genresPayload, presentation);
      loaded = true;
      if (messageNode) {
        presentation?.clear(messageNode);
        messageNode.textContent = "";
      }
    } catch (_error) {
      selection = "";
      contentNode.innerHTML = '<p class="empty" data-render-i18n="public.unavailable">Public activity is unavailable.</p>';
      presentation?.bindRendered(contentNode);
      if (messageNode) {
        presentation?.clear(messageNode);
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
