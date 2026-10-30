/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createCustomStationController({
  apiFetch, dialog, form, messageNode, openButton, cancelButtons, toolsNode,
  getCurrentUser, getSessionKey, onSaved, beforeOpen,
}) {
  let opener = openButton;
  let generation = 0;
  let pending = false;
  let context = null;
  let view = "search";
  let bound = false;
  const submitButton = form?.querySelector('button[type="submit"]');

  function sameSession(captured) {
    return Boolean(
      captured &&
      getCurrentUser()?.id === captured.userId &&
      getSessionKey() === captured.sessionKey
    );
  }

  function updateVisibility(nextView) {
    view = nextView;
    const authenticated = Boolean(getCurrentUser());
    if (toolsNode) toolsNode.hidden = !authenticated || view !== "favorites";
    if (openButton) openButton.disabled = !authenticated;
  }

  function closeDialog() {
    generation += 1;
    context = null;
    pending = false;
    if (submitButton) submitButton.disabled = false;
    if (dialog?.open) dialog.close();
    form?.reset();
    if (messageNode) messageNode.textContent = "";
    opener?.focus();
  }

  function closeIfOpen() {
    if (!dialog?.open) return false;
    closeDialog();
    return true;
  }

  function syncSession() {
    if (context && !sameSession(context)) closeDialog();
    updateVisibility(view);
  }

  function openDialog(event) {
    const user = getCurrentUser();
    if (!user || !dialog || !form || dialog.open) return;
    opener = event?.currentTarget || openButton;
    beforeOpen?.();
    generation += 1;
    context = { userId: user.id, sessionKey: getSessionKey() };
    pending = false;
    if (submitButton) submitButton.disabled = false;
    if (messageNode) messageNode.textContent = "";
    if (toolsNode) toolsNode.open = false;
    dialog.showModal();
    form.elements.namedItem("name")?.focus();
  }

  async function submit(event) {
    event.preventDefault();
    if (pending || !dialog?.open) return;
    if (!sameSession(context)) {
      closeDialog();
      return;
    }

    const requestGeneration = generation;
    const requestContext = context;
    const station = {
      name: String(form.elements.namedItem("name")?.value || "").trim(),
      url: String(form.elements.namedItem("url")?.value || "").trim(),
    };
    pending = true;
    if (submitButton) submitButton.disabled = true;
    if (messageNode) messageNode.textContent = "Saving station…";

    try {
      const response = await apiFetch("/api/stations/custom", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
        body: JSON.stringify(station),
      });
      if (requestGeneration !== generation || !sameSession(requestContext)) return;
      const payload = await response.json();
      if (requestGeneration !== generation || !sameSession(requestContext)) return;
      if (!response.ok) {
        throw new Error(
          typeof payload?.detail === "string"
            ? payload.detail
            : "Could not save station. Please try again."
        );
      }
      closeDialog();
      await onSaved(Boolean(payload.added));
    } catch (error) {
      if (requestGeneration !== generation || !sameSession(requestContext)) return;
      if (messageNode) {
        messageNode.textContent = error?.message || "Could not save station. Please try again.";
      }
    } finally {
      if (requestGeneration === generation) {
        pending = false;
        if (submitButton) submitButton.disabled = false;
      }
    }
  }

  function bind({ skipOpenButton = false } = {}) {
    if (bound) return;
    bound = true;
    if (!skipOpenButton) openButton?.addEventListener("click", openDialog);
    form?.addEventListener("submit", submit);
    cancelButtons.forEach((button) => button.addEventListener("click", closeDialog));
    dialog?.addEventListener("cancel", (event) => {
      event.preventDefault();
      closeDialog();
    });
  }

  return {
    bind, closeDialog, closeIfOpen, openDialog, submit, syncSession, updateVisibility,
  };
}
