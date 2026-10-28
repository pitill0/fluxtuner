/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import { canNavigate } from "./navigation-model.js";

/*
 * Visual navigation state derives from existing application state.
 * No independent active-destination variable is maintained.
 */

const BUTTONS = Object.freeze({
  dashboard: "dashboard",
  explore: "search",
  favorites: "favorites",
  playlists: "playlists",
  catalogs: "catalogs",
  stations: "stations",
  history: "history",
  account: "account",
  admin: "admin",
});

const LIBRARY_VIEWS = Object.freeze({
  search: "explore",
  favorites: "favorites",
  playlists: "playlists",
  playlist: "playlists",
  stations: "stations",
  catalogs: "catalogs",
  catalog: "catalogs",
  history: "history",
});

export function resolveActiveDestination({
  accountVisible,
  adminVisible,
  dashboardVisible,
  libraryView,
}) {
  if (accountVisible) return "account";
  if (adminVisible) return "admin";
  if (dashboardVisible) return "dashboard";
  return LIBRARY_VIEWS[libraryView] || "explore";
}

export function createNavigationPresentation({
  appState,
  root,
  accountPanel,
  adminPanel,
  dashboardPanel,
  searchPanel,
}) {
  function currentDestination() {
    return appState.getCurrentDestination();
  }

  function render() {
    const user = appState.getCurrentUser();
    const active = currentDestination();

    for (const [destination, identifier] of Object.entries(BUTTONS)) {
      const button = root.querySelector(`[data-nav-${identifier}]`);
      if (!button) continue;

      const isActive = canNavigate(destination, user) &&
        destination === active;

      if (isActive) {
        button.setAttribute("aria-current", "page");
      } else {
        button.removeAttribute("aria-current");
      }
    }
  }

  function bind() {
    const unsubscribe = appState.subscribeNavigationChange(render);
    render();

    return () => {
      unsubscribe();
    };
  }

  return { bind, render };
}
