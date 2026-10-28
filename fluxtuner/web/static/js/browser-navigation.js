/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

// Browser URLs describe supported views, not dialogs, requests or playback.
// Unknown query parameters (e.g. player-debug) are preserved.
const ROUTES = new Set([
  "dashboard", "explore", "favorites", "playlists",
  "history", "account", "admin", "playlist",
  "stations", "catalogs", "catalog",
]);

export function readNavigationUrl(href) {
  const url = new URL(href);
  const view = url.searchParams.get("view") || "dashboard";
  if (!ROUTES.has(view)) return { view: "dashboard", invalid: true };
  if (view === "catalog") {
    const id = url.searchParams.get("catalog") || "";
    if (!/^[1-9][0-9]*$/.test(id) ||
        !Number.isSafeInteger(Number(id))) {
      return { view: "catalogs", invalid: true };
    }
    return {
      view,
      name: id,
      invalid: url.searchParams.has("playlist"),
    };
  }
  if (url.searchParams.has("catalog")) {
    return { view: "catalogs", invalid: true };
  }
  if (view === "playlist") {
    const name = url.searchParams.get("playlist") || "";
    if (!name || name.length > 200) {
      return { view: "playlists", invalid: true };
    }
    return { view, name, invalid: false };
  }
  return { view, invalid: url.searchParams.has("playlist") };
}

export function navigationUrl(href, view, name = "") {
  const url = new URL(href);
  url.searchParams.delete("view");
  url.searchParams.delete("playlist");
  url.searchParams.delete("catalog");
  if (view && view !== "dashboard") {
    url.searchParams.set("view", view);
    if (view === "playlist") url.searchParams.set("playlist", name);
    if (view === "catalog") url.searchParams.set("catalog", String(name));
  }
  return `${url.pathname}${url.search}${url.hash}`;
}

function activeRoute(appState) {
  if (appState.getCurrentSection() !== "explore") {
    return { view: appState.getCurrentSection() };
  }
  const view = appState.getCurrentView();
  if (view === "catalog") {
    return {
      view,
      name: String(appState.getCurrentCatalogId()),
    };
  }
  if (view === "playlist") {
    return { view, name: appState.getCurrentPlaylistName() };
  }
  return { view: view === "search" ? "explore" : view };
}

export function createBrowserNavigationController({ appState, browser, navigation }) {
  let ready = false;
  let replaying = false;
  let queued = false;
  let initialRestoration = true;
  let sequence = 0;
  let unbind = null;
  const locationHref = () => browser.location.href;

  function replace(route) {
    browser.history.replaceState(null, "", navigationUrl(
      locationHref(), route.view, route.name,
    ));
  }

  function record() {
    if (!ready || replaying || queued) return;
    queued = true;
    // Coalesces the synchronous section/view/playlist mutations of one transition.
    queueMicrotask(() => {
      queued = false;
      if (!ready || replaying || !appState.isAuthenticated()) return;
      const route = activeRoute(appState);
      if (!ROUTES.has(route.view) ||
          ((route.view === "playlist" || route.view === "catalog") && !route.name)) return;
      const next = navigationUrl(locationHref(), route.view, route.name);
      const here = new URL(locationHref());
      if (next === `${here.pathname}${here.search}${here.hash}`) return;
      browser.history.pushState(null, "", next);
    });
  }

  async function replay(route, { fromPop = false } = {}) {
    const thisSequence = ++sequence;
    replaying = true;
    const user = appState.getCurrentUser();
    let chosen = route;
    if (!user) {
      // A reload before login may retain a deep link for a future login.
      if (fromPop) replace({ view: "dashboard" });
      replaying = false;
      return;
    }
    if (route.invalid || (route.view === "admin" && !user.is_admin)) {
      chosen = { view: "dashboard" };
    }
    const execute = navigation[chosen.view];
    if (!execute) chosen = { view: "dashboard" };
    try {
      await navigation[chosen.view](chosen.name);
    } finally {
      if (thisSequence === sequence) {
        // Preserve current history position when replaying a popstate.
        replace(chosen);
        replaying = false;
      }
    }
  }

  function onAuthReady() {
    if (!appState.isAuthenticated()) return;
    if (!initialRestoration && ready) return;
    initialRestoration = false;
    ready = true;
    return replay(readNavigationUrl(locationHref()));
  }

  function onLogout() {
    ++sequence;
    ready = false;
    replaying = false;
    initialRestoration = true;
    replace({ view: "dashboard" });
  }

  function onPopState() {
    if (!ready) {
      if (!appState.isAuthenticated()) replace({ view: "dashboard" });
      return;
    }
    return replay(readNavigationUrl(locationHref()), { fromPop: true });
  }

  function bind() {
    if (unbind) return unbind;
    const unsubscribe = appState.subscribeNavigationChange(record);
    browser.addEventListener("popstate", onPopState);
    unbind = () => {
      unsubscribe();
      browser.removeEventListener("popstate", onPopState);
      unbind = null;
    };
    return unbind;
  }

  return { bind, onAuthReady, onLogout };
}
