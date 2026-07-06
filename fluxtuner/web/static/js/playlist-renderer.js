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
  function renderCreatePlaylistForm() {
    return `
      <form class="playlist-create-form station-actions" data-create-playlist-form>
        <label>
          <span class="sr-only">New playlist name</span>
          <input
            name="playlist"
            type="text"
            autocomplete="off"
            maxlength="120"
            placeholder="New playlist name"
            required
          >
        </label>
        <button type="submit">Create playlist</button>
      </form>
    `;
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
        ${renderCreatePlaylistForm()}
      `;
      bindPlaylistActions();
      return;
    }

    resultsNode.innerHTML = `
      ${renderCreatePlaylistForm()}
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
    document.querySelectorAll("[data-create-playlist-form]").forEach((form) => {
      if (form.dataset.playlistCreateBound === "true") {
        return;
      }

      form.dataset.playlistCreateBound = "true";
      form.addEventListener("submit", async (event) => {
        event.preventDefault();
        const formData = new FormData(form);
        const name = String(formData.get("playlist") || "").trim();
        await onCreatePlaylist(name);
        form.reset();
      });
    });

    document.querySelectorAll("[data-open-playlist]").forEach((button) => {
      if (button.dataset.playlistOpenBound === "true") {
        return;
      }

      button.dataset.playlistOpenBound = "true";
      button.addEventListener("click", () => {
        const name = button.getAttribute("data-open-playlist");
        if (name) {
          onOpenPlaylist(name);
        }
      });
    });

    document.querySelectorAll("[data-delete-playlist]").forEach((button) => {
      if (button.dataset.playlistDeleteBound === "true") {
        return;
      }

      button.dataset.playlistDeleteBound = "true";
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
