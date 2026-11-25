/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

import { createDeferredController } from "./deferred-controller.js";

export function createLazyRemoteSubscriptionController(options) {
  const { elements } = options;
  let bound = false;

  const deferred = createDeferredController({
    options,
    loadModule: () => import("./remote-subscriptions.js"),
    createName: "createRemoteSubscriptionController",
    getIdentity: () =>
      `${options.getCurrentUser()?.id ?? ""}:${options.getSessionKey() ?? ""}`,
    onError: () => {
      elements.messageNode.textContent = "Could not load subscriptions.";
      options.presentation?.present(elements.messageNode, "subscriptions.lazy.error", elements.messageNode.textContent);
    },
  });

  function bind() {
    if (bound) return;
    bound = true;
    elements.openButton?.addEventListener("click", () => {
      void deferred.invoke("openDialog");
    });
    deferred.syncSession();
  }

  return {
    bind,
    syncSession: deferred.syncSession,
    closeIfOpen: deferred.closeIfOpen,
    openDialog: () => deferred.invoke("openDialog"),
  };
}
