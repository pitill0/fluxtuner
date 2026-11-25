/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

const BASE = "/api/stations/subscriptions";

export function createRemoteSubscriptionController({
  presentation,
  knownApiErrorKey = () => undefined,
  elements, apiFetch, getCurrentUser, getSessionKey, beforeOpen,
  confirmDelete = (message) => window.confirm(message),
  onChanged = () => {},
}) {
  let epoch = 0;
  let identity = "";
  let pending = null;
  let busy = false;
  const actionButtons = new Set();

  const e = elements;
  const identityNow = () =>
    `${getCurrentUser()?.id ?? ""}:${getSessionKey() ?? ""}`;
  const current = (mark) =>
    mark === epoch && identity === identityNow() && Boolean(getCurrentUser());

  function setBusy(value) {
    busy = value;
    for (const node of actionButtons) node.disabled = value;
    e.confirmButton.disabled = value;
  }

  let workingMessage = false;
  function message(value, key) {
    workingMessage = key === "subscriptions.feedback.working";
    if (key && presentation) presentation.present(e.messageNode, key, value);
    else { presentation?.clear(e.messageNode); e.messageNode.textContent = value; }
  }

  function clearPreview() {
    pending = null;
    e.previewNode.hidden = true;
    presentation?.clear(e.previewNode);
    e.previewNode.textContent = "";
    e.confirmButton.hidden = true;
  }

  function invalidate() {
    epoch += 1;
    setBusy(false);
    clearPreview();
  }

  function syncSession() {
    const next = identityNow();
    if (next === identity) return;
    identity = next;
    invalidate();
    e.listNode.replaceChildren();
    actionButtons.clear();
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

  function button(label, action, key) {
    const node = e.listNode.ownerDocument.createElement("button");
    node.type = "button";
    node.textContent = label;
    presentation?.present(node, key, label);
    node.disabled = busy;
    actionButtons.add(node);
    node.addEventListener("click", action);
    return node;
  }

  async function load() {
    const mark = epoch;
    const payload = await request(BASE, { method: "GET" });
    if (!current(mark)) return;
    e.listNode.replaceChildren();
    actionButtons.clear();

    const items = payload.subscriptions || [];
    if (!items.length) {
      const empty = e.listNode.ownerDocument.createElement("p");
      empty.textContent = "No remote catalogs subscribed.";
      presentation?.present(empty, "subscriptions.empty", empty.textContent);
      e.listNode.append(empty);
      return;
    }

    for (const item of items) {
      const container = e.listNode.ownerDocument.createElement("div");
      container.className = "subscription-row";
      const info = e.listNode.ownerDocument.createElement("div");
      info.className = "subscription-info";
      const name = e.listNode.ownerDocument.createElement("strong");
      // Never render catalog names or untrusted remote strings as HTML.
      name.textContent = item.label || `Catalog #${item.source_id}`;
      const meta = e.listNode.ownerDocument.createElement("small");
      meta.textContent = `Catalog #${item.source_id} · revision ${item.revision}`;
      if (!item.label) presentation?.present(name, "subscriptions.catalog", name.textContent, "textContent", { id: item.source_id });
      presentation?.present(meta, "subscriptions.revision", meta.textContent, "textContent", { id: item.source_id, revision: item.revision });
      info.append(name, meta);
      const actions = e.listNode.ownerDocument.createElement("div");
      actions.className = "subscription-actions";
      actions.append(
        button("Check updates", () => preview(item.source_id), "subscriptions.action.check"),
        button("Unsubscribe", () => remove(item.source_id), "subscriptions.action.remove"),
      );
      container.append(info, actions);
      e.listNode.append(container);
    }
  }

  async function operate(callback) {
    if (busy || !getCurrentUser()) return;
    setBusy(true);
    const mark = epoch;
    message("Working…", "subscriptions.feedback.working");
    try {
      await callback(mark);
    } catch (error) {
      if (current(mark)) {
        const text = error.message || "Operation failed.";
        const key = text === "Collection URL required." ? "subscriptions.feedback.url_required"
          : text === "Catalog name is too long." ? "subscriptions.feedback.name_long"
          : (text === "Operation failed." || text === "Request failed.") ? "subscriptions.feedback.error" : knownApiErrorKey(text);
        message(text, key);
      }
    } finally {
      if (current(mark)) {
        setBusy(false);
        if (workingMessage) message("");
      }
    }
  }

  async function add(event) {
    event.preventDefault();
    await operate(async (mark) => {
      const url = e.urlInput.value.trim();
      const displayName = e.nameInput?.value?.trim() || "";
      if (!url) throw new Error("Collection URL required.");
      if (displayName.length > 120) throw new Error("Catalog name is too long.");
      await request(BASE, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, display_name: displayName || null }),
      });
      if (!current(mark)) return;
      e.urlInput.value = "";
      if (e.nameInput) e.nameInput.value = "";
      clearPreview();
      if (current(mark)) {
        onChanged({ type: "added" });
      }
      await load();
      if (current(mark)) message("Subscription added.", "subscriptions.feedback.added");
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
        message("Catalog is already up to date.", "subscriptions.feedback.current");
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
      e.previewNode.textContent = lines.join("\n");
      if (presentation) {
        const counts = [payload.added.length, payload.removed.length, payload.changed.length, payload.unchanged];
        const keys = ["added", "removed", "changed", "unchanged"];
        presentation.presentParts(e.previewNode, [
          ...keys.map((key, index) => ({ key: `subscriptions.preview.${key}`, fallback: lines[index], params: { count: counts[index] } })),
          ...lines.slice(4),
        ], "\n");
      }
      e.previewNode.hidden = false;
      e.confirmButton.hidden = false;
      message("Review the changes before applying.", "subscriptions.feedback.review");
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
      if (current(mark)) {
        onChanged({ type: "updated", sourceId: chosen.sourceId });
      }
      await load();
      if (current(mark)) message("Catalog updated.", "subscriptions.feedback.updated");
    });
  }

  async function remove(sourceId) {
    const warning = "Unsubscribe from this catalog? Saved favorites and playlists will remain.";
    if (!confirmDelete(presentation?.translate("subscriptions.confirm.remove", warning) ?? warning)) {
      return;
    }
    await operate(async (mark) => {
      await request(`${BASE}/${sourceId}`, { method: "DELETE" });
      if (!current(mark)) return;
      clearPreview();
      if (current(mark)) {
        onChanged({ type: "removed", sourceId });
      }
      await load();
      if (current(mark)) message("Subscription removed.", "subscriptions.feedback.removed");
    });
  }

  async function openDialog() {
    if (!getCurrentUser() || e.dialog.open) return;
    beforeOpen?.();
    identity = identityNow();
    invalidate();
    e.dialog.showModal();
    await operate(async () => load());
  }

  function bind({ skipOpenButton = false } = {}) {
    identity = identityNow();
    if (!skipOpenButton) e.openButton.addEventListener("click", openDialog);
    e.form.addEventListener("submit", add);
    e.confirmButton.addEventListener("click", confirm);
    e.closeButton.addEventListener("click", closeIfOpen);
    e.dialog.addEventListener("close", () => {
      if (!e.dialog.open) invalidate();
    });
  }

  return { bind, syncSession, closeIfOpen, openDialog, load, preview, confirm, remove };
}
