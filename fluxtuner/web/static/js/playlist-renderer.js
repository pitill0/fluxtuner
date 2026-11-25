/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml } from "./stations.js";

export function createPlaylistRenderer({
  resultsNode,
  resultCountNode,
  onCreatePlaylist,
  onOpenPlaylist,
  onDeletePlaylist,
  onExportPlaylist,
  onSharePlaylist,
  presentation,
}) {
  function translateRenderedPlaylists() {
    if (!presentation) return;
    const labels = [
      ["[data-create-playlist-form] .sr-only", "playlists.new_name", "New playlist name"],
      ["[data-create-playlist-form] input", "playlists.new_name", "New playlist name", "placeholder"],
      ["[data-create-playlist-form] button", "playlists.create", "Create playlist"],
      ["[data-open-playlist]", "playlists.open", "Open playlist"],
      ["[data-delete-playlist]", "playlists.delete", "Delete playlist"],
      ["[data-export-playlist-m3u]", "library.export_format_m3u", "Export M3U"],
      ["[data-export-playlist-pls]", "library.export_format_pls", "Export PLS"],
      ["[data-share-playlist]", "library.share", "Share"],
      ["[data-playlists-empty]", "playlists.empty", "No playlists yet."],
    ];
    for (const [selector, key, fallback, attribute] of labels) {
      for (const node of resultsNode.querySelectorAll(selector)) {
        presentation.present(node, key, fallback, attribute);
      }
    }
    for (const node of resultsNode.querySelectorAll("[data-playlist-station-count]")) {
      const count = Number(node.dataset.playlistStationCount);
      presentation.present(node, "stations.count", node.textContent, "textContent", { count });
    }
  }

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
    const count = payload.count ?? playlists.length;
    const countText = `${count} playlist${count === 1 ? "" : "s"}`;
    if (presentation) presentation.present(resultCountNode, "playlists.count", countText, "textContent", { count: Number(count) });
    else resultCountNode.textContent = countText;

    if (!playlists.length) {
      resultsNode.innerHTML = `
        <p class="empty" data-playlists-empty>No playlists yet.</p>
        ${renderCreatePlaylistForm()}
      `;
      translateRenderedPlaylists();
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
                  <span data-playlist-station-count="${Number(playlist.count || 0)}">${Number(playlist.count || 0)} station${
                    Number(playlist.count || 0) === 1 ? "" : "s"
                  }</span>
                </div>
              </header>

              <div class="station-actions">
                <button type="button" data-open-playlist="${escapeHtml(
                  playlist.name,
                )}">Open playlist</button>
                <button type="button" data-export-playlist-m3u="${escapeHtml(
                  playlist.name,
                )}">Export M3U</button>
                <button type="button" data-export-playlist-pls="${escapeHtml(
                  playlist.name,
                )}">Export PLS</button>
                <button type="button" data-share-playlist="${escapeHtml(
                  playlist.name,
                )}">Share</button>
                <button type="button" data-delete-playlist="${escapeHtml(
                  playlist.name,
                )}">Delete playlist</button>
              </div>
            </article>
          `,
        )
        .join("")}
    `;

    translateRenderedPlaylists();
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

    for (const format of ["m3u", "pls"]) {
      document.querySelectorAll(`[data-export-playlist-${format}]`).forEach((button) => {
        if (button.dataset.playlistExportBound === "true") {
          return;
        }

        button.dataset.playlistExportBound = "true";
        button.addEventListener("click", () => {
          const name = button.getAttribute(`data-export-playlist-${format}`);
          if (name) {
            onExportPlaylist(name, format);
          }
        });
      });
    }

    document.querySelectorAll("[data-share-playlist]").forEach((button) => {
      if (button.dataset.playlistShareBound === "true") return;
      button.dataset.playlistShareBound = "true";
      button.addEventListener("click", () => {
        const name = button.getAttribute("data-share-playlist");
        if (name) onSharePlaylist?.(name);
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
