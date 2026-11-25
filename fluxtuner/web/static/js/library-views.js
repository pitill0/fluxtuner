/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

function setLoadingState({ resultsNode, resultCountNode, countText, emptyText, countKey, emptyKey, presentation }) {
  if (resultCountNode) {
    if (presentation) presentation.present(resultCountNode, countKey, countText);
    else resultCountNode.textContent = countText;
  }

  if (resultsNode) {
    resultsNode.innerHTML = `<p class="empty">${emptyText}</p>`;
    if (presentation) presentation.present(resultsNode.querySelector?.(".empty"), emptyKey, emptyText);
  }
}

export function createLibraryViewsController({
  apiFetch,
  resultsNode,
  resultCountNode,
  setResultsHeader,
  renderResults,
  renderPlaylists,
  renderSearchError,
  onExportFavorites,
  setLibraryView,
  getCurrentView,
  getCurrentUser,
  isLibraryVisible,
  presentation,
}) {
  let generation = 0;

  function currentRequest(request, view, user) {
    return request === generation &&
      getCurrentView() === view &&
      getCurrentUser() === user &&
      isLibraryVisible();
  }

  function ensureResultsContainer() {
    return Boolean(resultsNode && resultCountNode);
  }

  async function loadHistory() {
    if (!ensureResultsContainer()) return;
    const requestGeneration = ++generation;
    const requestUser = getCurrentUser();
    const stillCurrent = () => currentRequest(
      requestGeneration, "history", requestUser,
    );

    setLibraryView("history", "");
    setResultsHeader("Playback", "History", "player.playback", "nav.history");
    setLoadingState({
      presentation,
      resultsNode,
      resultCountNode,
      countText: "Loading history...",
      countKey: "library.loading_history",
      emptyText: "Loading playback history...",
      emptyKey: "library.loading_playback",
    });

    try {
      const response = await apiFetch("/api/history?limit=25", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!stillCurrent()) return;

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      if (!stillCurrent()) return;
      renderResults(payload);
    } catch (error) {
      if (stillCurrent()) renderSearchError(error);
    }
  }

  async function loadFavorites() {
    if (!ensureResultsContainer()) return;
    const requestGeneration = ++generation;
    const requestUser = getCurrentUser();
    const stillCurrent = () => currentRequest(
      requestGeneration, "favorites", requestUser,
    );

    setLibraryView("favorites", "");
    setResultsHeader("Library", "Favorites", "shell.library", "nav.favorites");
    setLoadingState({
      presentation,
      resultsNode,
      resultCountNode,
      countText: "Loading favorites...",
      countKey: "library.loading_favorites",
      emptyText: "Loading favorites...",
      emptyKey: "library.loading_favorites",
    });

    try {
      const response = await apiFetch("/api/favorites", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!stillCurrent()) return;

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      if (!stillCurrent()) return;
      renderResults(payload);
      if (onExportFavorites && typeof resultsNode.insertAdjacentHTML === "function") {
        const count = Number(payload.count || payload.stations?.length || 0);
        resultsNode.insertAdjacentHTML("afterbegin", `
        <div class="station-actions">
          <button type="button" data-export-favorites="m3u"${count ? "" : " disabled"}>Export favorites M3U</button>
          <button type="button" data-export-favorites="pls"${count ? "" : " disabled"}>Export favorites PLS</button>
        </div>
      `);
        resultsNode.querySelectorAll("[data-export-favorites]").forEach((button) => {
          const format = button.dataset.exportFavorites;
          presentation?.present(button, format === "m3u" ? "library.export_m3u" : "library.export_pls",
            format === "m3u" ? "Export favorites M3U" : "Export favorites PLS");
          button.addEventListener("click", () => onExportFavorites(button.dataset.exportFavorites));
        });
      }
    } catch (error) {
      if (stillCurrent()) renderSearchError(error);
    }
  }

  async function loadPlaylists() {
    if (!ensureResultsContainer()) return;
    const requestGeneration = ++generation;
    const requestUser = getCurrentUser();
    const stillCurrent = () => currentRequest(
      requestGeneration, "playlists", requestUser,
    );

    setLibraryView("playlists", "");
    setResultsHeader("Library", "Playlists", "shell.library", "nav.playlists");
    setLoadingState({
      presentation,
      resultsNode,
      resultCountNode,
      countText: "Loading playlists...",
      countKey: "library.loading_playlists",
      emptyText: "Loading playlists...",
      emptyKey: "library.loading_playlists",
    });

    try {
      const response = await apiFetch("/api/playlists", {
        headers: {
          Accept: "application/json",
        },
      });

      if (!stillCurrent()) return;

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      if (!stillCurrent()) return;
      renderPlaylists(payload);
    } catch (error) {
      if (stillCurrent()) renderSearchError(error);
    }
  }

  async function loadPlaylistStations(name) {
    if (!ensureResultsContainer()) return;
    const requestGeneration = ++generation;
    const requestUser = getCurrentUser();
    const stillCurrent = () => currentRequest(
      requestGeneration, "playlist", requestUser,
    );

    setLibraryView("playlist", name);
    setResultsHeader("Playlist", name, "playlists.single");
    setLoadingState({
      presentation,
      resultsNode,
      resultCountNode,
      countText: "Loading playlist...",
      countKey: "library.loading_playlist",
      emptyText: "Loading playlist stations...",
      emptyKey: "library.loading_playlist_stations",
    });

    try {
      const response = await apiFetch(
        `/api/playlists/${encodeURIComponent(name)}/stations`,
        {
          headers: {
            Accept: "application/json",
          },
        },
      );

      if (!stillCurrent()) return;

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      if (!stillCurrent()) return;
      renderResults(payload);
    } catch (error) {
      if (stillCurrent()) renderSearchError(error);
    }
  }

  return {
    loadFavorites,
    loadHistory,
    loadPlaylistStations,
    loadPlaylists,
  };
}
