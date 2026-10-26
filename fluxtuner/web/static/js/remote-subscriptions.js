/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const BASE = "/api/stations/subscriptions";

export function createRemoteSubscriptionController({
  elements, apiFetch, getCurrentUser, getSessionKey, beforeOpen,
  confirmDelete = (message) => window.confirm(message),
}) {
  let epoch = 0;
  let identity = "";
  let pending = null;
  let busy = false;

  const e = elements;
  const identityNow = () =>
    `${getCurrentUser()?.id ?? ""}:${getSessionKey() ?? ""}`;
  const current = (mark) =>
    mark === epoch && identity === identityNow() && Boolean(getCurrentUser());

  function message(value) {
    e.messageNode.textContent = value;
  }

  function clearPreview() {
    pending = null;
    e.previewNode.hidden = true;
    e.previewNode.textContent = "";
    e.confirmButton.hidden = true;
  }

  function invalidate() {
    epoch += 1;
    busy = false;
    clearPreview();
  }

  function syncSession() {
    const next = identityNow();
    if (next === identity) return;
    identity = next;
    invalidate();
    e.listNode.replaceChildren();
    message("");
    if (e.dialog.open) e.dialog.close();
  }

  function closeIfOpen() {
    if (!e.dialog.open || busy) return false;
    invalidate();
    e.dialog.close();
    return true;
  }

  async function request(path, options) {
    const response = await apiFetch(path, options);
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.detail || "Request failed.");
    return payload;
  }

  function button(label, action) {
    const node = e.listNode.ownerDocument.createElement("button");
    node.type = "button";
    node.textContent = label;
    node.disabled = busy;
    node.addEventListener("click", action);
    return node;
  }

  async function load() {
    const mark = epoch;
    const payload = await request(BASE, { method: "GET" });
    if (!current(mark)) return;
    e.listNode.replaceChildren();

    const items = payload.subscriptions || [];
    if (!items.length) {
      const empty = e.listNode.ownerDocument.createElement("p");
      empty.textContent = "No remote catalogs subscribed.";
      e.listNode.append(empty);
      return;
    }

    for (const item of items) {
      const container = e.listNode.ownerDocument.createElement("div");
      container.className = "station-actions";
      const name = e.listNode.ownerDocument.createElement("span");
      // Never render an untrusted remote URL as HTML.
      name.textContent = `Catalog #${item.source_id} · revision ${item.revision}`;
      container.append(
        name,
        button("Check updates", () => preview(item.source_id)),
        button("Unsubscribe", () => remove(item.source_id)),
      );
      e.listNode.append(container);
    }
  }

  async function operate(callback) {
    if (busy || !getCurrentUser()) return;
    busy = true;
    const mark = epoch;
    message("Working…");
    try {
      await callback(mark);
    } catch (error) {
      if (current(mark)) message(error.message || "Operation failed.");
    } finally {
      if (current(mark)) busy = false;
    }
  }

  async function add(event) {
    event.preventDefault();
    await operate(async (mark) => {
      const url = e.urlInput.value.trim();
      if (!url) throw new Error("Collection URL required.");
      await request(BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!current(mark)) return;
      e.urlInput.value = "";
      clearPreview();
      await load();
      if (current(mark)) message("Subscription added.");
    });
  }

  async function preview(sourceId) {
    await operate(async (mark) => {
      clearPreview();
      const payload = await request(`${BASE}/${sourceId}/preview`, {
        method: "POST",
      });
      if (!current(mark)) return;
      if (payload.not_modified === true) {
        clearPreview();
        message("Catalog is already up to date.");
        return;
      }
      pending = {
        sourceId,
        revision: payload.revision,
        receipt: payload.receipt,
      };
      const lines = [
        `Added: ${payload.added.length}`,
        `Removed: ${payload.removed.length}`,
        `Changed: ${payload.changed.length}`,
        `Unchanged: ${payload.unchanged}`,
        "",
        ...payload.added.map((item) => `+ ${item.name}: ${item.url}`),
        ...payload.removed.map((item) => `- ${item.name}: ${item.url}`),
        ...payload.changed.map((item) => `~ ${JSON.stringify(item)}`),
      ];
      e.previewNode.textContent = lines.join("\\n");
      e.previewNode.hidden = false;
      e.confirmButton.hidden = false;
      message("Review the changes before applying.");
    });
  }

  async function confirm() {
    if (!pending) return;
    const chosen = pending;
    await operate(async (mark) => {
      await request(
        `${BASE}/${chosen.sourceId}/confirm?revision=${chosen.revision}`,
        {
          method: "POST",
          headers: { "X-FluxTuner-Refresh-Receipt": chosen.receipt },
        },
      );
      if (!current(mark)) return;
      clearPreview();
      await load();
      if (current(mark)) message("Catalog updated.");
    });
  }

  async function remove(sourceId) {
    if (!confirmDelete("Unsubscribe from this catalog? Saved favorites and playlists will remain.")) {
      return;
    }
    await operate(async (mark) => {
      await request(`${BASE}/${sourceId}`, { method: "DELETE" });
      if (!current(mark)) return;
      clearPreview();
      await load();
      if (current(mark)) message("Subscription removed.");
    });
  }

  async function openDialog() {
    if (!getCurrentUser()) return;
    beforeOpen?.();
    identity = identityNow();
    invalidate();
    e.dialog.showModal();
    await operate(async () => load());
  }

  function bind() {
    identity = identityNow();
    e.openButton.addEventListener("click", openDialog);
    e.form.addEventListener("submit", add);
    e.confirmButton.addEventListener("click", confirm);
    e.closeButton.addEventListener("click", closeIfOpen);
    e.dialog.addEventListener("close", () => {
      if (!e.dialog.open) invalidate();
    });
  }

  return { bind, syncSession, closeIfOpen, openDialog, load, preview, confirm, remove };
}
