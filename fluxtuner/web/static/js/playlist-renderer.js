/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "/static/js/stations.js";

export function createPlaylistRenderer({
  resultsNode,
  resultCountNode,
  onCreatePlaylist,
  onOpenPlaylist,
  onDeletePlaylist,
}) {
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
      button.addEventListener("click", onCreatePlaylist);
    });

    document.querySelectorAll("[data-open-playlist]").forEach((button) => {
      button.addEventListener("click", () => {
        const name = button.getAttribute("data-open-playlist");
        if (name) {
          onOpenPlaylist(name);
        }
      });
    });

    document.querySelectorAll("[data-delete-playlist]").forEach((button) => {
      button.addEventListener("click", () => {
        const name = button.getAttribute("data-delete-playlist");
        if (name) {
          onDeletePlaylist(name);
        }
      });
    });
  }

  return {
    bindPlaylistActions,
    renderPlaylists,
  };
}
