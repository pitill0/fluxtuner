/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

/*
 * UX-02 navigation model.
 *
 * Pure application navigation state. No DOM, network,
 * browser history, or player runtime dependencies.
 *
 * This module is not wired into the current UI yet.
 */

const DESTINATIONS = Object.freeze({
  dashboard: { parent: null, authenticated: true },
  explore: { parent: null, authenticated: true },
  library: { parent: null, authenticated: true },
  favorites: { parent: "library", authenticated: true },
  playlists: { parent: "library", authenticated: true },
  stations: { parent: "library", authenticated: true },
  catalogs: { parent: "library", authenticated: true },
  history: { parent: "library", authenticated: true },
  account: { parent: null, authenticated: true },
  admin: { parent: null, authenticated: true, admin: true },
});

export const NAVIGATION_DESTINATIONS = DESTINATIONS;

export function canNavigate(destination, user) {
  const definition = DESTINATIONS[destination];
  if (!definition) return false;
  if (definition.authenticated && !user) return false;
  if (definition.admin && !user?.is_admin) return false;
  return true;
}

export function navigationPath(destination) {
  const definition = DESTINATIONS[destination];
  if (!definition) return [];

  return definition.parent
    ? [definition.parent, destination]
    : [destination];
}

export function availableDestinations(user) {
  return Object.keys(DESTINATIONS).filter(
    (destination) => canNavigate(destination, user),
  );
}

export function createNavigationModel({
  user = null,
  initialDestination = "explore",
} = {}) {
  let currentUser = user;
  let currentDestination = canNavigate(initialDestination, user)
    ? initialDestination
    : null;

  function navigate(destination) {
    if (!canNavigate(destination, currentUser)) {
      return false;
    }
    currentDestination = destination;
    return true;
  }

  function updateUser(user) {
    currentUser = user;

    if (!canNavigate(currentDestination, currentUser)) {
      currentDestination = null;
    }
  }

  function snapshot() {
    return Object.freeze({
      destination: currentDestination,
      path: Object.freeze(navigationPath(currentDestination)),
      authenticated: Boolean(currentUser),
      available: Object.freeze(
        availableDestinations(currentUser),
      ),
    });
  }

  return Object.freeze({
    navigate,
    updateUser,
    snapshot,
  });
}
