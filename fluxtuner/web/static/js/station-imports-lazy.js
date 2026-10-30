/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { createDeferredController } from "./deferred-controller.js";

export function createLazyStationImportController(options) {
  const { elements, getCurrentUser, getSessionKey } = options;
  let bound = false;

  const deferred = createDeferredController({
    options,
    loadModule: () => import("./station-imports.js"),
    createName: "createStationImportController",
    getIdentity: () =>
      `${getCurrentUser()?.id ?? ""}:${getSessionKey() ?? ""}:${options.getProfileName?.() ?? ""}`,
    onError: () => {
      elements.messageNode.textContent = "Could not load station import controls.";
    },
  });

  function syncSession() {
    deferred.syncSession();
    if (elements.openButton) {
      elements.openButton.disabled = !getCurrentUser();
    }
  }

  function openDialog() {
    return deferred.invoke("openDialog");
  }

  function bind() {
    if (bound) return;
    bound = true;
    elements.openButton?.addEventListener("click", openDialog);
    syncSession();
  }

  return {
    bind,
    syncSession,
    closeIfOpen: deferred.closeIfOpen,
    openDialog,
  };
}
