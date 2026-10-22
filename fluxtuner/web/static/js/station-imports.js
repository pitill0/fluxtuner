/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createStationImportController({
  apiFetch, elements, getCurrentUser, getSessionKey, beforeOpen, onSaved,
}) {
  const {
    openButton, dialog, form, fileInput, urlInput, previewButton, previewNode,
    destinationNode, selectNode, nameField, nameInput, messageNode,
    submitButton, cancelButton,
  } = elements;
  const MAX_BYTES = 1024 * 1024;
  let generation = 0;
  let context = null;
  let bytes = null;
  let playlists = [];
  let pending = "";
  let bound = false;

  function sameSession(captured) {
    return Boolean(
      captured &&
      getCurrentUser()?.id === captured.userId &&
      getSessionKey() === captured.sessionKey
    );
  }

  function current(requestGeneration, requestContext) {
    return requestGeneration === generation && sameSession(requestContext);
  }

  function updateControls() {
    const ready = bytes !== null;
    const busy = Boolean(pending);
    fileInput.disabled = busy;
    if (urlInput) urlInput.disabled = busy;
    previewButton.disabled = busy;
    selectNode.disabled = busy || !ready;
    nameField.hidden = selectNode.value !== "";
    nameInput.disabled = busy || !ready || nameField.hidden;
    submitButton.disabled = busy || !ready;
    cancelButton.disabled = pending === "import";
    destinationNode.hidden = !ready;
  }

  function clearPreview() {
    bytes = null;
    playlists = [];
    selectNode.replaceChildren();
    selectNode.value = "";
    previewNode.textContent = "";
    previewNode.hidden = true;
    updateControls();
  }

  function closeDialog() {
    generation += 1;
    context = null;
    pending = "";
    if (dialog.open) dialog.close();
    form.reset();
    clearPreview();
    messageNode.textContent = "";
    openButton?.focus();
  }

  function closeIfOpen() {
    if (!dialog.open) return false;
    if (pending !== "import") closeDialog();
    return true;
  }

  function syncSession() {
    if (context && !sameSession(context)) closeDialog();
    if (openButton) openButton.disabled = !getCurrentUser();
  }

  function openDialog() {
    const user = getCurrentUser();
    if (!user || dialog.open) return;
    beforeOpen?.();
    generation += 1;
    context = { userId: user.id, sessionKey: getSessionKey() };
    pending = "";
    form.reset();
    clearPreview();
    messageNode.textContent = "";
    dialog.showModal();
    fileInput.focus();
  }

  function fileChanged() {
    generation += 1;
    pending = "";
    clearPreview();
    messageNode.textContent = "";
  }

  async function post(endpoint, body) {
    return apiFetch(endpoint, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/octet-stream",
      },
      body,
    });
  }

  async function readPayload(response) {
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(
        typeof payload?.detail === "string"
          ? payload.detail
          : "Could not import this file. Please try again."
      );
    }
    return payload;
  }

  function renderPreview(payload) {
    playlists = payload.playlists;
    const option = (value, label) => {
      const node = selectNode.ownerDocument.createElement("option");
      node.value = value;
      node.textContent = label;
      return node;
    };
    selectNode.replaceChildren(
      option("", "Create new playlist…"),
      ...playlists.map((name, index) => option(String(index), name)),
    );
    selectNode.value = "";
    const lines = payload.entries.slice(0, 200).map((entry) =>
      `${entry.name}${entry.existing ? " — already in favorites" : " — new"}\n${entry.url}`
    );
    if (payload.entries.length > 200) {
      lines.push(`Showing the first 200 of ${payload.entries.length} stations. All will be imported.`);
    }
    if (payload.issues.length) {
      lines.push("Skipped entries:");
      lines.push(...payload.issues.slice(0, 100).map((issue) =>
        `Line ${issue.line_number}: ${issue.reason}`
      ));
      if (payload.issues.length > 100) lines.push("Additional skipped entries omitted.");
    }
    previewNode.textContent = lines.join("\n\n");
    previewNode.hidden = false;
    messageNode.textContent =
      `${payload.entries.length} valid stations; ${payload.duplicates} repeated URLs; ` +
      `${payload.issues.length} skipped entries. Nothing has been saved yet.`;
  }

  async function preview() {
    if (pending || !dialog.open) return;
    if (!sameSession(context)) {
      closeDialog();
      return;
    }
    clearPreview();
    const url = urlInput?.value.trim() || "";
    const file = fileInput.files?.[0];
    if (!url && !file) {
      messageNode.textContent = "Choose a playlist file or enter an HTTP/HTTPS URL.";
      return;
    }
    if (!url && file.size > MAX_BYTES) {
      messageNode.textContent = "The playlist exceeds 1 MiB.";
      return;
    }
    if (url && !/^https?:\/\//i.test(url)) {
      messageNode.textContent = "Enter an HTTP/HTTPS collection URL.";
      return;
    }

    const requestGeneration = ++generation;
    const requestContext = context;
    pending = "preview";
    updateControls();
    messageNode.textContent = url ? "Downloading collection…" : "Reading playlist…";
    try {
      let data;
      if (url) {
        const download = await apiFetch("/api/stations/import/remote", {
          method: "POST",
          headers: { Accept: "application/octet-stream", "Content-Type": "application/json" },
          body: JSON.stringify({ url }),
        });
        if (!current(requestGeneration, requestContext)) return;
        if (!download.ok) {
          let detail = "Could not download remote collection.";
          try {
            const payload = await download.json();
            if (typeof payload?.detail === "string") detail = payload.detail;
          } catch { /* Keep the fallback message. */ }
          throw new Error(detail);
        }
        data = await download.arrayBuffer();
        if (!current(requestGeneration, requestContext)) return;
        if (data.byteLength > MAX_BYTES) throw new Error("The playlist exceeds 1 MiB.");
      } else {
        data = await file.arrayBuffer();
      }
      if (!current(requestGeneration, requestContext)) return;
      const response = await post("/api/stations/import/preview", data);
      if (!current(requestGeneration, requestContext)) return;
      const payload = await readPayload(response);
      if (!current(requestGeneration, requestContext)) return;
      bytes = data;
      let sourceName = file?.name || "Imported stations";
      if (url) {
        const parsed = new URL(url);
        sourceName = parsed.pathname.split("/").filter(Boolean).pop() || parsed.hostname;
      }
      nameInput.value = sourceName.replace(/\.(?:m3u8?|pls)$/i, "").slice(0, 120) || "Imported stations";
      renderPreview(payload);
    } catch (error) {
      if (!current(requestGeneration, requestContext)) return;
      clearPreview();
      messageNode.textContent = error?.message || "Could not read playlist.";
    } finally {
      if (requestGeneration === generation) {
        pending = "";
        updateControls();
      }
    }
  }

  async function submit(event) {
    event.preventDefault();
    if (pending || bytes === null || !dialog.open) return;
    if (!sameSession(context)) {
      closeDialog();
      return;
    }

    const existing = selectNode.value !== "";
    const index = Number(selectNode.value);
    const name = existing
      ? playlists[index]
      : nameInput.value.trim();
    if (!name || (existing && (!Number.isInteger(index) || index < 0))) {
      messageNode.textContent = "Choose a destination playlist.";
      return;
    }

    const requestGeneration = generation;
    const requestContext = context;
    pending = "import";
    updateControls();
    messageNode.textContent = "Importing stations…";
    try {
      const query = new URLSearchParams({ playlist: name, existing: String(existing) });
      const response = await post(`/api/stations/import?${query}`, bytes);
      if (!current(requestGeneration, requestContext)) return;
      const payload = await readPayload(response);
      if (!current(requestGeneration, requestContext)) return;
      closeDialog();
      await onSaved(payload);
    } catch (error) {
      if (!current(requestGeneration, requestContext)) return;
      messageNode.textContent = error?.message || "Could not import stations.";
    } finally {
      if (requestGeneration === generation) {
        pending = "";
        updateControls();
      }
    }
  }

  function bind() {
    if (bound) return;
    bound = true;
    openButton?.addEventListener("click", openDialog);
    fileInput.addEventListener("change", fileChanged);
    urlInput?.addEventListener("input", fileChanged);
    previewButton.addEventListener("click", preview);
    selectNode.addEventListener("change", updateControls);
    form.addEventListener("submit", submit);
    cancelButton.addEventListener("click", closeIfOpen);
    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      closeIfOpen();
    });
    syncSession();
  }

  return { bind, openDialog, closeIfOpen, syncSession, preview, submit, fileChanged };
}
