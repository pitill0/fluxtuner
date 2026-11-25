/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { escapeHtml, stationUrl } from "./stations.js";

const MAX_PLAYLIST_NAME_LENGTH = 120;

export function createPlaylistController({
  apiFetch,
  presentation,
  knownApiErrorKey = () => undefined,
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

  function setPlaylistDialogMessage(message, key, params = {}) {
    if (messageNode) {
      if (presentation && key) presentation.present(messageNode, key, message, "textContent", params);
      else {
        presentation?.clear(messageNode);
        messageNode.textContent = message || "";
      }
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
    if (presentation && selectNode.options) {
      presentation.present(selectNode.options[0], "playlist.dialog.choose_option", "Choose existing playlist...");
      items.forEach((playlist, index) => {
        const option = selectNode.options[index + 1];
        presentation.present(option, "playlist.dialog.option", option.textContent, "textContent", { name: playlist.name || "", count: Number(playlist.count || 0) });
      });
    }
  }

  async function loadPlaylistChoices() {
    if (!selectNode) return;

    selectNode.innerHTML = '<option value="">Loading playlists...</option>';
    if (selectNode.options) presentation?.present(selectNode.options[0], "playlist.dialog.loading", "Loading playlists...");

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
      setPlaylistDialogMessage("No playlists yet. Enter a new playlist name below.", "playlist.dialog.empty");
    } else {
      setPlaylistDialogMessage("Choose an existing playlist or enter a new name.", "playlist.dialog.choose");
    }
  }

  async function openPlaylistDialog(station) {
    const url = stationUrl(station);
    if (!url) {
      setPlayerState("error", "This station has no URL to add to a playlist.", undefined, "playlist.no_station_url");
      return;
    }

    if (!dialog || !form) {
      setPlayerState("error", "Playlist dialog is not available.", undefined, "playlist.dialog_unavailable");
      return;
    }

    pendingPlaylistStation = station;
    dialog.hidden = false;

    if (stationNameNode) {
      const label = station.name ? `Station: ${station.name}` : "Station selected.";
      if (presentation) presentation.present(stationNameNode, station.name ? "playlist.dialog.station" : "playlist.dialog.selected", label, "textContent", { name: station.name });
      else stationNameNode.textContent = label;
    }

    setPlaylistDialogMessage("Loading playlists...", "playlist.dialog.loading");

    try {
      await loadPlaylistChoices();
    } catch (error) {
      setPlaylistDialogMessage(`Could not load playlists. ${error}`, "playlist.dialog.load_error", { error: String(error) });
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
        "playlist.dialog.length", { limit: MAX_PLAYLIST_NAME_LENGTH },
      );
      return;
    }

    if (!playlistName) {
      setPlaylistDialogMessage("Choose an existing playlist or enter a new playlist name.", "playlist.dialog.required");
      return;
    }

    setPlaylistDialogMessage("Adding station...", "playlist.dialog.adding");

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
        undefined, payload.added ? "playlist.added" : "playlist.station_exists", { name: payload.name },
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
      setPlaylistDialogMessage(`Could not add station. ${error}`, "playlist.dialog.add_error", { error: String(error) });
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
        undefined, payload.removed ? "playlist.removed" : "playlist.station_absent", { name: payload.name },
      );

      await loadPlaylistStations(getCurrentPlaylistName());
    } catch (error) {
      setPlayerState("error", `Could not remove station from playlist. ${error}`, undefined, "playlist.remove_failed", { error: String(error) });
    }
  }

  async function createPlaylist(playlistName) {
    const cleanPlaylistName = String(playlistName || "").trim();
    if (!cleanPlaylistName) {
      setPlayerState("error", "Enter a playlist name.", undefined, "playlist.name_required");
      return;
    }
    if (cleanPlaylistName.length > MAX_PLAYLIST_NAME_LENGTH) {
      setPlayerState(
        "error",
        `Playlist name must be ${MAX_PLAYLIST_NAME_LENGTH} characters or less.`, undefined, "playlist.name_length", { limit: MAX_PLAYLIST_NAME_LENGTH }
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
        const payload = await response.json().catch(() => ({}));
        const key = knownApiErrorKey(payload.detail);
        if (key) {
          setPlayerState("error", payload.detail, undefined, key);
          return;
        }
        throw new Error(`HTTP ${response.status}`);
      }

      const payload = await response.json();
      setPlayerState(
        "idle",
        payload.created
          ? `Created playlist "${payload.name}".`
          : `Playlist "${payload.name}" already exists.`,
        undefined, payload.created ? "playlist.created" : "playlist.exists", { name: payload.name },
      );

      await loadPlaylists();
    } catch (error) {
      setPlayerState("error", `Could not create playlist. ${error}`, undefined, "playlist.create_failed", { error: String(error) });
    }
  }

  async function deletePlaylist(name) {
    const warning = `Delete playlist "${name}"? Stations will stay in favorites.`;
    if (!window.confirm(presentation?.translate("playlist.confirm_delete", warning, { name }) ?? warning)) {
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
        undefined, payload.removed ? "playlist.deleted" : "playlist.not_found", { name: payload.name },
      );

      await loadPlaylists();
    } catch (error) {
      setPlayerState("error", `Could not delete playlist. ${error}`, undefined, "playlist.delete_failed", { error: String(error) });
    }
  }

  return {
    addToPlaylist,
    closePlaylistDialog,
    createPlaylist,
    deletePlaylist,
    removeFromPlaylist,
    submitPlaylistDialog,
  };
}
