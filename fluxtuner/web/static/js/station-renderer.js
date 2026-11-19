/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import {
  escapeHtml,
  formatDisplayDateTime,
  stationButtonPayload,
  stationHomepage,
  stationTags,
  stationUrl,
} from "./stations.js";

export function createStationRenderer({
  renderState,
  onPlayStation,
  onAddFavorite,
  onRemoveFavorite,
  onAddToPlaylist,
  onRemoveFromPlaylist,
  onShareStation,
  onStationActionError,
}) {
  function currentRenderState() {
    return renderState?.() || {};
  }

  function renderStation(station) {
    const { currentUser, currentView } = currentRenderState();
    const streamUrl = stationUrl(station);
    const homepage = stationHomepage(station);
    const tags = stationTags(station);
    const playCount = Number(station.play_count || 0);
    const lastPlayedAt = formatDisplayDateTime(station.last_played_at);
    const favoriteTags = Array.isArray(station.favorite_tags) ? station.favorite_tags : [];
    const stationName = String(station.custom_name || station.name || "Unknown station");
    const artworkRef = typeof station.artwork_ref === "string" ? station.artwork_ref : "";
    const artworkUrl = artworkRef.length <= 4096 && /^v1\.[0-9]+\.[A-Za-z0-9_-]+\.[a-f0-9]{64}$/.test(artworkRef)
      ? `/api/artwork/${encodeURIComponent(artworkRef)}`
      : "";

    return `
      <article class="station-card" data-station-card>
        <header>
          <div class="station-identity">
            <span class="station-artwork" aria-hidden="true">
              <span class="station-artwork-fallback">${escapeHtml(stationName.trim().charAt(0).toUpperCase() || "♫")}</span>
              ${artworkUrl ? `<img data-station-artwork src="${artworkUrl}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">` : ""}
            </span>
            <h3>${escapeHtml(stationName)}</h3>
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
                )}"${artworkUrl ? ` data-station-artwork-ref="${artworkRef}"` : ""}>Play</button>`
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
            currentUser && ["favorites", "playlist"].includes(currentView) && streamUrl
              ? `<button type="button" data-share-station="${stationButtonPayload(
                  station,
                )}">Share</button>`
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
      button.getAttribute("data-share-station") ||
      button.getAttribute("data-remove-from-playlist");

    if (!payload) return null;
    return JSON.parse(payload);
  }

  function bindStationAction(selector, callback) {
    document.querySelectorAll(selector).forEach((button) => {
      if (button.dataset.stationActionBound === "true") {
        return;
      }

      button.dataset.stationActionBound = "true";
      button.addEventListener("click", () => {
        try {
          const station = parseStationButton(button);
          if (station) callback(station, button.getAttribute("data-station-artwork-ref") || "");
        } catch (error) {
          onStationActionError?.(error);
        }
      });
    });
  }

  function bindResultActions() {
    document.querySelectorAll("img[data-station-artwork]").forEach((image) => {
      if (image.dataset.artworkBound === "true") return;
      image.dataset.artworkBound = "true";
      image.addEventListener("error", () => { image.hidden = true; }, { once: true });
      if (image.complete && image.naturalWidth === 0) image.hidden = true;
    });
    bindStationAction("[data-play-station]", onPlayStation);
    bindStationAction("[data-add-favorite]", onAddFavorite);
    bindStationAction("[data-remove-favorite]", onRemoveFavorite);
    bindStationAction("[data-add-to-playlist]", onAddToPlaylist);
    bindStationAction("[data-share-station]", onShareStation);
    bindStationAction("[data-remove-from-playlist]", onRemoveFromPlaylist);
  }

  return {
    bindResultActions,
    renderStation,
  };
}
