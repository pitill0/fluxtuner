/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml, stationUrl } from "/static/js/stations.js";

const MAX_PLAYLIST_NAME_LENGTH = 120;

export function createPlaylistController({
  apiFetch,
  dialog,
  form,
  selectNode,
  messageNode,
  stationNameNode,
  setPlayerState,
  getCurrentView,
  getCurrentPlaylistName,
  loadPlaylists,
  loadPlaylistStations,
}) {
  let pendingPlaylistStation = null;

  function setPlaylistDialogMessage(message) {
    if (messageNode) {
      messageNode.textContent = message || "";
    }
  }

  function closePlaylistDialog() {
    pendingPlaylistStation = null;

    if (dialog) {
      dialog.hidden = true;
    }

    if (form) {
      form.reset();
    }

    setPlaylistDialogMessage("");
  }

  function renderPlaylistOptions(playlists) {
    if (!selectNode) return;

    const items = playlists || [];
    const options = items
      .map((playlist) => {
        const name = escapeHtml(playlist.name || "");
        const count = Number(playlist.count || 0);
        const suffix = `${count} station${count === 1 ? "" : "s"}`;
        return `<option value="${name}">${name} · ${suffix}</option>`;
      })
      .join("");

    selectNode.innerHTML =
      '<option value="">Choose existing playlist...</option>' + options;
  }

  async function loadPlaylistChoices() {
    if (!selectNode) return;

    selectNode.innerHTML = '<option value="">Loading playlists...</option>';

    const response = await apiFetch("/api/playlists", {
      headers: {
        Accept: "application/json",
      },
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderPlaylistOptions(payload.playlists || []);

    if (!(payload.playlists || []).length) {
      setPlaylistDialogMessage("No playlists yet. Enter a new playlist name below.");
    } else {
      setPlaylistDialogMessage("Choose an existing playlist or enter a new name.");
    }
  }

  async function openPlaylistDialog(station) {
    const url = stationUrl(station);
    if (!url) {
      setPlayerState("error", "This station has no URL to add to a playlist.");
      return;
    }

    if (!dialog || !form) {
      setPlayerState("error", "Playlist dialog is not available.");
      return;
    }

    pendingPlaylistStation = station;
    dialog.hidden = false;

    if (stationNameNode) {
      stationNameNode.textContent = station.name
        ? `Station: ${station.name}`
        : "Station selected.";
    }

    setPlaylistDialogMessage("Loading playlists...");

    try {
      await loadPlaylistChoices();
    } catch (error) {
      setPlaylistDialogMessage(`Could not load playlists. ${error}`);
    }

    const firstInput = dialog.querySelector("select, input, button");
    if (firstInput) {
      firstInput.focus();
    }
  }

  async function submitPlaylistDialog(event) {
    event.preventDefault();

    if (!pendingPlaylistStation || !form) {
      closePlaylistDialog();
      return;
    }

    const formData = new FormData(form);
    const selectedPlaylist = String(formData.get("playlist") || "").trim();
    const newPlaylist = String(formData.get("new_playlist") || "").trim();
    const playlistName = newPlaylist || selectedPlaylist;

    if (playlistName.length > MAX_PLAYLIST_NAME_LENGTH) {
      setPlaylistDialogMessage(
        `Playlist name must be ${MAX_PLAYLIST_NAME_LENGTH} characters or less.`,
      );
      return;
    }

    if (!playlistName) {
      setPlaylistDialogMessage("Choose an existing playlist or enter a new playlist name.");
      return;
    }

    setPlaylistDialogMessage("Adding station...");

    try {
      const response = await apiFetch(
        `/api/playlists/${encodeURIComponent(playlistName)}/stations`,
        {
          method: "POST",
          headers: {
            Accept: "application/json",
            "Content-Type": "application/json",
          },
          body: JSON.stringify(pendingPlaylistStation),
        },
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      closePlaylistDialog();
      setPlayerState(
        "idle",
        payload.added
          ? `Added to playlist "${payload.name}".`
          : `Station is already in playlist "${payload.name}".`,
      );

      if (getCurrentView() === "playlists") {
        await loadPlaylists();
      } else if (
        getCurrentView() === "playlist" &&
        getCurrentPlaylistName() === payload.name
      ) {
        await loadPlaylistStations(getCurrentPlaylistName());
      }
    } catch (error) {
      setPlaylistDialogMessage(`Could not add station. ${error}`);
    }
  }

  async function addToPlaylist(station) {
    await openPlaylistDialog(station);
  }

  async function removeFromPlaylist(station) {
    const url = stationUrl(station);
    if (!url || getCurrentView() !== "playlist") {
      return;
    }

    try {
      const response = await apiFetch(
        `/api/playlists/${encodeURIComponent(getCurrentPlaylistName())}/stations?url=${encodeURIComponent(url)}`,
        {
          method: "DELETE",
          headers: {
            Accept: "application/json",
          },
        },
      );

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      setPlayerState(
        "idle",
        payload.removed
          ? `Removed from playlist "${payload.name}".`
          : `Station was not in playlist "${payload.name}".`,
      );

      await loadPlaylistStations(getCurrentPlaylistName());
    } catch (error) {
      setPlayerState("error", `Could not remove station from playlist. ${error}`);
    }
  }

  async function createPlaylistFromPrompt() {
    const playlistName = window.prompt("New playlist name:");
    if (!playlistName || !playlistName.trim()) {
      return;
    }

    const cleanPlaylistName = playlistName.trim();
    if (cleanPlaylistName.length > MAX_PLAYLIST_NAME_LENGTH) {
      setPlayerState(
        "error",
        `Playlist name must be ${MAX_PLAYLIST_NAME_LENGTH} characters or less.`,
      );
      return;
    }

    try {
      const response = await apiFetch("/api/playlists", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: cleanPlaylistName }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      setPlayerState(
        "idle",
        payload.created
          ? `Created playlist "${payload.name}".`
          : `Playlist "${payload.name}" already exists.`,
      );

      await loadPlaylists();
    } catch (error) {
      setPlayerState("error", `Could not create playlist. ${error}`);
    }
  }

  async function deletePlaylist(name) {
    if (!window.confirm(`Delete playlist "${name}"? Stations will stay in favorites.`)) {
      return;
    }

    try {
      const response = await apiFetch(`/api/playlists/${encodeURIComponent(name)}`, {
        method: "DELETE",
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      setPlayerState(
        "idle",
        payload.removed
          ? `Deleted playlist "${payload.name}".`
          : `Playlist "${payload.name}" was not found.`,
      );

      await loadPlaylists();
    } catch (error) {
      setPlayerState("error", `Could not delete playlist. ${error}`);
    }
  }

  return {
    addToPlaylist,
    closePlaylistDialog,
    createPlaylistFromPrompt,
    deletePlaylist,
    removeFromPlaylist,
    submitPlaylistDialog,
  };
}
