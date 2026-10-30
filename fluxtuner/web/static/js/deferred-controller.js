/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createDeferredController({
  options,
  loadModule,
  createName,
  getIdentity,
  onError,
  onReady,
}) {
  let controller = null;
  let pending = null;
  let generation = 0;
  let identity = getIdentity();

  function syncSession() {
    const next = getIdentity();
    if (next !== identity) {
      identity = next;
      generation += 1;
    }
    controller?.syncSession();
  }

  function ensureController() {
    if (controller) return Promise.resolve(controller);
    if (!pending) {
      pending = Promise.resolve()
        .then(loadModule)
        .then((module) => {
          const factory = module[createName];
          if (typeof factory !== "function") {
            throw new Error(`Missing controller factory: ${createName}`);
          }
          controller = factory(options);
          controller.bind({ skipOpenButton: true });
          controller.syncSession();
          onReady?.(controller);
          return controller;
        })
        .catch((error) => {
          pending = null;
          throw error;
        });
    }
    return pending;
  }

  async function invoke(name, ...args) {
    syncSession();
    const requestedGeneration = generation;
    const requestedIdentity = identity;

    if (!options.getCurrentUser?.()) return undefined;

    try {
      const target = await ensureController();
      syncSession();
      if (
        requestedGeneration !== generation ||
        requestedIdentity !== identity
      ) {
        return undefined;
      }
      return await target[name](...args);
    } catch (error) {
      syncSession();
      if (
        requestedGeneration === generation &&
        requestedIdentity === identity
      ) {
        onError?.(error);
      }
      return undefined;
    }
  }

  function closeIfOpen() {
    if (controller) return controller.closeIfOpen();

    // A pending module load represents a queued opening. Cancel it
    // synchronously so navigation does not open another dialog over it.
    if (pending) {
      generation += 1;
      return true;
    }

    return false;
  }

  return {
    invoke,
    syncSession,
    closeIfOpen,
    getController: () => controller,
  };
}
