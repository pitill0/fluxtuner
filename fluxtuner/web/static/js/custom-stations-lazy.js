/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { createDeferredController } from "./deferred-controller.js";

export function createLazyCustomStationController(options) {
  let bound = false;
  let view = "search";

  const deferred = createDeferredController({
    options,
    loadModule: () => import("./custom-stations.js"),
    createName: "createCustomStationController",
    onReady: (controller) => controller.updateVisibility(view),
    getIdentity: () =>
      `${options.getCurrentUser()?.id ?? ""}:${options.getSessionKey() ?? ""}`,
    onError: () => {
      if (options.messageNode) {
        options.messageNode.textContent = "Could not load custom station controls.";
      }
    },
  });

  function updateVisibility(nextView) {
    view = nextView;
    const authenticated = Boolean(options.getCurrentUser());

    if (options.toolsNode) {
      options.toolsNode.hidden = !authenticated || view !== "favorites";
    }
    if (options.openButton) {
      options.openButton.disabled = !authenticated;
    }

    deferred.getController()?.updateVisibility(view);
  }

  function syncSession() {
    deferred.syncSession();
    updateVisibility(view);
  }

  function openDialog(event) {
    // Preserve the opener before asynchronous module loading.
    const opener = event?.currentTarget;
    return deferred.invoke(
      "openDialog",
      opener ? { currentTarget: opener } : undefined,
    );
  }

  function bind() {
    if (bound) return;
    bound = true;
    options.openButton?.addEventListener("click", openDialog);
    syncSession();
  }

  return {
    bind,
    syncSession,
    updateVisibility,
    closeIfOpen: deferred.closeIfOpen,
    openDialog,
  };
}
