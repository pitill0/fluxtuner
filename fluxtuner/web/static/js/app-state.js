/*
 * SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
 */

export function createAppState() {
  let currentView = "search";
  let currentPlaylistName = "";
  let currentUser = null;
  let csrfToken = "";

  return {
    getCsrfToken: () => csrfToken,
    getCurrentPlaylistName: () => currentPlaylistName,
    getCurrentUser: () => currentUser,
    getCurrentView: () => currentView,
    isAuthenticated: () => Boolean(currentUser),
    setCsrfToken: (value) => {
      csrfToken = value;
    },
    setCurrentPlaylistName: (value) => {
      currentPlaylistName = value;
    },
    setCurrentUser: (value) => {
      currentUser = value;
    },
    setCurrentView: (value) => {
      currentView = value;
    },
  };
}
