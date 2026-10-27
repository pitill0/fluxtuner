/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createAppState() {
  let currentView = "search";
  let currentSection = "explore";

  const libraryDestinations = Object.freeze({
    search: "explore",
    favorites: "favorites",
    playlists: "playlists",
    playlist: "playlists",
    history: "history",
  });

  function currentDestination() {
    if (currentSection !== "explore") return currentSection;
    return libraryDestinations[currentView] || "explore";
  }
  const viewListeners = new Set();
  const navigationListeners = new Set();

  function notifyNavigationChange() {
    for (const listener of navigationListeners) listener();
  }
  let currentPlaylistName = "";
  let currentUser = null;
  let csrfToken = "";

  return {
    getCsrfToken: () => csrfToken,
    getCurrentPlaylistName: () => currentPlaylistName,
    getCurrentUser: () => currentUser,
    getCurrentView: () => currentView,
    getCurrentSection: () => currentSection,
    getCurrentDestination: currentDestination,
    isAuthenticated: () => Boolean(currentUser),
    setCsrfToken: (value) => {
      csrfToken = value;
    },
    setCurrentPlaylistName: (value) => {
      currentPlaylistName = value;
    },
    setCurrentUser: (value) => {
      currentUser = value;
      notifyNavigationChange();
    },
    setCurrentSection: (value) => {
      if (!["explore", "dashboard", "account", "admin"].includes(value)) {
        return false;
      }
      if (currentSection === value) return true;
      currentSection = value;
      notifyNavigationChange();
      return true;
    },
    setCurrentView: (value) => {
      currentView = value;
      for (const listener of viewListeners) listener(value);
      notifyNavigationChange();
    },
    subscribeNavigationChange: (listener) => {
      navigationListeners.add(listener);
      return () => navigationListeners.delete(listener);
    },
    subscribeViewChange: (listener) => {
      viewListeners.add(listener);
      return () => viewListeners.delete(listener);
    },
  };
}
