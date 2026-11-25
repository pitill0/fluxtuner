/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

/*
 * Preserve the administrative controller's public interface while keeping
 * admin.js outside the initial static import graph.
 */
export function createLazyAdminController(options, {
  loadModule = () => import("./admin.js"),
} = {}) {
  let controller = null;
  let pending = null;
  let generation = 0;

  function showError(error) {
    if (options.messageNode) {
      options.presentation?.clear(options.messageNode);
      const message = `Could not load administration controls. ${String(error)}`;
      if (options.presentation) options.presentation.present(options.messageNode, "admin.lazy_error", message, "textContent", { error: String(error) });
      else options.messageNode.textContent = message;
    }
  }

  function ensureController() {
    if (controller) return Promise.resolve(controller);
    if (!pending) {
      pending = Promise.resolve()
        .then(loadModule)
        .then(({ createAdminController }) => {
          controller = createAdminController(options);
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
    const requestedGeneration = generation;
    const requestedUser = options.getCurrentUser?.();

    // Never initialize administrative work without an active admin session.
    if (!requestedUser?.is_admin) return undefined;

    try {
      const admin = await ensureController();

      // A logout, session refresh or reset invalidates waiting actions.
      if (
        requestedGeneration !== generation ||
        options.getCurrentUser?.() !== requestedUser
      ) {
        return undefined;
      }

      return await admin[name](...args);
    } catch (error) {
      if (
        requestedGeneration === generation &&
        options.getCurrentUser?.() === requestedUser
      ) {
        showError(error);
      }
      return undefined;
    }
  }

  function submit(name, event) {
    event?.preventDefault();
    return invoke(name, event);
  }

  return {
    createUser: (event) => submit("createUser", event),
    loadUsers: () => invoke("loadUsers"),
    loadUsersIfNeeded: () => invoke("loadUsersIfNeeded"),
    mutateUser: (...args) => invoke("mutateUser", ...args),
    reset: () => {
      generation += 1;
      controller?.reset();

      // Preserve synchronous UI cleanup while the module is still loading.
      if (!controller) {
        if (options.messageNode) {
          options.presentation?.clear(options.messageNode);
          options.messageNode.textContent = "";
        }
        if (options.usersNode) {
          options.usersNode.innerHTML = '<p class="empty" data-render-i18n="admin.users_empty">Admin users will appear here.</p>';
          options.presentation?.bindRendered(options.usersNode);
        }
      }
    },
    setUserPassword: (event) => submit("setUserPassword", event),
  };
}
