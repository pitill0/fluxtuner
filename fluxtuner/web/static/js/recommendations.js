/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import { stationUrl } from "./stations.js";

const PAGE_SIZE = 20;

export function createRecommendationsController({
  presentation,
  apiFetch, dialog, openButton, getCurrentUser, getSessionKey,
  beforeOpen, onOpenAccepted,
}) {
  let identity = "";
  let revision = 0;
  let selection = null;
  let direction = "inbox";
  let offset = 0;
  let acceptedDestination = null;

  const byRole = (role) => dialog?.querySelector(`[data-recommendations-${role}]`);

  function sessionIdentity() {
    const user = getCurrentUser();
    return user ? `${user.id}:${getSessionKey() || ""}` : "";
  }

  function current(ticket, captured) {
    return Boolean(captured && ticket === revision && captured === sessionIdentity());
  }

  function message(value, key, params = {}) {
    const node = byRole("message");
    if (node) {
      if (key && presentation) presentation.present(node, key, value, "textContent", params);
      else { presentation?.clear(node); node.textContent = value; }
    }
    acceptedDestination = null;
    const destination = byRole("destination");
    if (destination) destination.hidden = true;
  }

  function acceptedMessage(kind, outcome) {
    if (kind === "station") {
      const existing = outcome.existing_favorites > 0;
      message(existing
        ? "Station already in Favorites. Find and play it in My Library → Favorites."
        : "Station added to Favorites. Find and play it in My Library → Favorites.",
        existing ? "recommendations.feedback.existing" : "recommendations.feedback.station_added");
      acceptedDestination = { kind: "station" };
    } else if (kind === "playlist" &&
               typeof outcome.playlist_name === "string" &&
               outcome.playlist_name.trim()) {
      message("Playlist added to your library. Find it in My Library → Playlists.", "recommendations.feedback.playlist_added");
      acceptedDestination = {
        kind: "playlist",
        playlistName: outcome.playlist_name,
      };
    } else {
      message("Recommendation accepted.", "recommendations.feedback.accepted");
      return;
    }

    const destination = byRole("destination");
    const viewButton = byRole("view");
    if (!destination || !viewButton) return;
    viewButton.textContent = acceptedDestination.kind === "station"
      ? "View Favorites" : "View Playlist";
    presentation?.present(viewButton, acceptedDestination.kind === "station"
      ? "recommendations.view.favorites" : "recommendations.view.playlist", viewButton.textContent);
    destination.hidden = false;
  }

  function closeIfOpen() {
    if (!dialog?.open) return false;
    dialog.close();
    selection = null;
    revision += 1;
    return true;
  }

  function syncSession() {
    const next = sessionIdentity();
    if (next === identity) return;
    identity = next;
    revision += 1;
    selection = null;
    if (dialog?.open) dialog.close();
    byRole("items")?.replaceChildren();
    message("");
  }

  function renderItems(items) {
    const container = byRole("items");
    if (!container) return;
    container.replaceChildren();
    if (!items.length) {
      const empty = document.createElement("p");
      empty.className = "empty";
      empty.textContent = offset ? "No more recommendations." : "No recommendations here yet.";
      presentation?.present(empty, offset ? "recommendations.empty.more" : "recommendations.empty.initial", empty.textContent);
      container.append(empty);
      return;
    }
    for (const item of items) {
      const card = document.createElement("article");
      card.className = "station-card";
      const title = document.createElement("h3");
      title.textContent = item.title;
      const details = document.createElement("p");
      details.className = "station-tags";
      const other = direction === "inbox" ? "From" : "To";
      details.textContent = `${other} ${item.counterpart_username} · ${item.kind} · ${item.status}`;
      if (presentation) {
        details.textContent = "";
        const counterpart = document.createElement("span");
        presentation.present(counterpart, direction === "inbox" ? "rec.from" : "rec.to", `${other} ${item.counterpart_username}`, "textContent", { user: item.counterpart_username });
        const kind = document.createElement("span");
        if (["station", "playlist"].includes(item.kind)) presentation.present(kind, `rec.${item.kind}`, item.kind);
        else kind.textContent = item.kind;
        const status = document.createElement("span");
        if (["pending", "accepted", "rejected"].includes(item.status)) presentation.present(status, `status.${item.status}`, item.status);
        else status.textContent = item.status;
        details.append(counterpart, " · ", kind, " · ", status);
      }
      card.append(title, details);
      if (direction === "inbox" && item.status === "pending") {
        const actions = document.createElement("div");
        actions.className = "station-actions";
        for (const action of ["accept", "reject"]) {
          const button = document.createElement("button");
          button.type = "button";
          button.dataset.recommendationAction = action;
          button.dataset.recommendationId = String(item.id);
          button.dataset.recommendationKind = item.kind;
          button.textContent = action === "accept" ? "Accept" : "Reject";
          presentation?.present(button, action === "accept" ? "recommendations.action.accept" : "recommendations.action.reject", button.textContent);
          actions.append(button);
        }
        card.append(actions);
      }
      container.append(card);
    }
  }

  async function load() {
    syncSession();
    const captured = identity;
    const ticket = ++revision;
    if (!captured) return;
    message("Loading recommendations...", "recommendations.feedback.loading");
    try {
      const params = new URLSearchParams({ direction, limit: String(PAGE_SIZE), offset: String(offset) });
      const response = await apiFetch(`/api/recommendations?${params}`, {
        headers: { Accept: "application/json" },
      });
      if (!current(ticket, captured)) return;
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!current(ticket, captured)) return;
      const items = Array.isArray(data.recommendations) ? data.recommendations : [];
      renderItems(items);
      byRole("prev").disabled = offset === 0;
      byRole("next").disabled = items.length < PAGE_SIZE;
      message(`${direction === "inbox" ? "Received" : "Sent"} · page ${offset / PAGE_SIZE + 1}`,
        direction === "inbox" ? "recommendations.page.inbox" : "recommendations.page.sent", { page: offset / PAGE_SIZE + 1 });
    } catch (_error) {
      if (current(ticket, captured)) message("Could not load recommendations. Please retry.", "recommendations.feedback.load_error");
    }
  }

  function show() {
    if (!sessionIdentity() || !dialog) return;
    beforeOpen?.();
    syncSession();
    if (!dialog.open) dialog.showModal();
    byRole("compose").hidden = true;
    byRole("title").textContent = "Recommendations";
    presentation?.present(byRole("title"), "recommendations.title", "Recommendations");
    load();
  }

  function openShare(kind, title, key) {
    if (!sessionIdentity() || !dialog || !key) return;
    beforeOpen?.();
    syncSession();
    selection = { kind, key };
    if (!dialog.open) dialog.showModal();
    byRole("compose").hidden = false;
    byRole("title").textContent = `Share ${kind}: ${title}`;
    presentation?.present(byRole("title"), kind === "station" ? "recommendations.share.station" : "recommendations.share.playlist",
      byRole("title").textContent, "textContent", { title });
    byRole("recipient").value = "";
    message("");
    byRole("recipient").focus();
  }

  function shareStation(station) {
    openShare("station", station.custom_name || station.name || "station", stationUrl(station));
  }

  function sharePlaylist(name) {
    openShare("playlist", name, name);
  }

  async function send(event) {
    event.preventDefault();
    if (!selection) return;
    syncSession();
    const captured = identity;
    const ticket = ++revision;
    const recipient = String(byRole("recipient")?.value || "").trim();
    if (!recipient) return message("Enter a recipient username.", "recommendations.feedback.recipient_required");
    const data = { recipient_username: recipient, kind: selection.kind };
    data[selection.kind === "station" ? "station_key" : "playlist_name"] = selection.key;
    message("Sending recommendation...", "recommendations.feedback.sending");
    try {
      const response = await apiFetch("/api/recommendations", {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify(data),
      });
      if (!current(ticket, captured)) return;
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      selection = null;
      byRole("compose").hidden = true;
      direction = "sent";
      offset = 0;
      await load();
      if (captured === identity) message("Recommendation sent.", "recommendations.feedback.sent");
    } catch (_error) {
      if (current(ticket, captured)) message("Could not send recommendation. Check the recipient and try again.", "recommendations.feedback.send_error");
    }
  }

  async function resolve(button) {
    const action = button.dataset.recommendationAction;
    const identifier = button.dataset.recommendationId;
    const kind = button.dataset.recommendationKind;
    if (!["accept", "reject"].includes(action) || !/^[1-9][0-9]*$/.test(identifier || "")) return;
    syncSession();
    const captured = identity;
    const ticket = ++revision;
    button.disabled = true;
    message(`${action === "accept" ? "Accepting" : "Rejecting"} recommendation...`,
      action === "accept" ? "recommendations.feedback.accepting" : "recommendations.feedback.rejecting");
    try {
      const response = await apiFetch(`/api/recommendations/${identifier}/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: "{}",
      });
      if (!current(ticket, captured)) return;
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const outcome = action === "accept" ? await response.json() : null;
      if (!current(ticket, captured)) return;
      if (action === "accept" && outcome?.status !== "accepted") {
        throw new Error("Unexpected acceptance result.");
      }

      const refreshing = load();
      const refreshTicket = revision;
      await refreshing;
      if (!current(refreshTicket, captured) || !dialog?.open) return;

      if (action === "accept") {
        acceptedMessage(kind, outcome);
      } else {
        message("Recommendation rejected.", "recommendations.feedback.rejected");
      }
    } catch (_error) {
      if (current(ticket, captured)) {
        button.disabled = false;
        message("Could not resolve recommendation. Please retry.", "recommendations.feedback.resolve_error");
      }
    }
  }

  function bind() {
    if (!dialog) return;
    dialog.addEventListener("close", () => { selection = null; revision += 1; });
    byRole("close")?.addEventListener("click", closeIfOpen);
    byRole("view")?.addEventListener("click", () => {
      if (!acceptedDestination || !sessionIdentity() ||
          identity !== sessionIdentity()) return;
      const destination = acceptedDestination;
      closeIfOpen();
      onOpenAccepted?.(destination);
    });
    openButton?.addEventListener("click", show);
    byRole("form")?.addEventListener("submit", send);
    byRole("cancel")?.addEventListener("click", () => {
      selection = null;
      byRole("compose").hidden = true;
      load();
    });
    byRole("received")?.addEventListener("click", () => {
      direction = "inbox"; offset = 0; byRole("compose").hidden = true; load();
    });
    byRole("sent")?.addEventListener("click", () => {
      direction = "sent"; offset = 0; byRole("compose").hidden = true; load();
    });
    byRole("prev")?.addEventListener("click", () => {
      offset = Math.max(0, offset - PAGE_SIZE); load();
    });
    byRole("next")?.addEventListener("click", () => {
      offset += PAGE_SIZE; load();
    });
    byRole("items")?.addEventListener("click", (event) => {
      const button = event.target.closest("[data-recommendation-action]");
      if (button) resolve(button);
    });
  }

  return { bind, show, shareStation, sharePlaylist, syncSession, closeIfOpen };
}
