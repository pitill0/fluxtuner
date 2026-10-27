/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

async function load(name) {
  const source = await readFile(join(process.env.WORK,
    "fluxtuner/web/static/js", name), "utf8");
  return import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
}
const { createAppState } = await load("app-state.js");
const { readNavigationUrl, navigationUrl, createBrowserNavigationController } =
  await load("browser-navigation.js");

assert.deepEqual(readNavigationUrl("http://host/?view=playlist&playlist=Jazz"),
  { view: "playlist", name: "Jazz", invalid: false });
assert.deepEqual(readNavigationUrl("http://host/?view=unknown"),
  { view: "dashboard", invalid: true });
assert.deepEqual(readNavigationUrl("http://host/?view=playlist"),
  { view: "playlists", invalid: true });
assert.equal(navigationUrl("http://host/?debug=1&view=history#x", "favorites"),
  "/?debug=1&view=favorites#x");
console.log("PASS: URL parser, playlist and foreign query preservation");

function fakeBrowser(href) {
  const listeners = new Map();
  const entries = [href];
  let index = 0;
  const location = { get href() { return entries[index]; } };
  const resolve = (path) => new URL(path, entries[index]).href;
  return {
    location,
    entries,
    history: {
      pushState(_state, _title, path) {
        entries.splice(index + 1); entries.push(resolve(path)); index++;
      },
      replaceState(_state, _title, path) { entries[index] = resolve(path); },
      back() { if (index > 0) { index--; listeners.get("popstate")?.(); } },
      forward() { if (index < entries.length - 1) { index++; listeners.get("popstate")?.(); } },
    },
    addEventListener(name, callback) { listeners.set(name, callback); },
    removeEventListener(name) { listeners.delete(name); },
  };
}
const tick = async () => { await Promise.resolve(); await Promise.resolve(); };
function setup(href, user = { is_admin: false }) {
  const state = createAppState();
  state.setCurrentUser(user);
  const browser = fakeBrowser(href);
  const calls = [];
  const update = (view, name) => {
    calls.push([view, name]);
    state.setCurrentSection(["dashboard", "account", "admin"].includes(view) ? view : "explore");
    if (view === "explore") state.setCurrentView("search");
    else if (!["dashboard", "account", "admin"].includes(view)) {
      state.setCurrentPlaylistName(name || "");
      state.setCurrentView(view);
    }
  };
  const navigation = Object.fromEntries(
    ["dashboard", "explore", "favorites", "playlists", "history", "account", "admin", "playlist"]
      .map((view) => [view, async (name) => update(view, name)]),
  );
  const controller = createBrowserNavigationController({ appState: state, browser, navigation });
  controller.bind();
  return { state, browser, calls, controller, update };
}
{
  const h = setup("http://host/?debug=1&view=favorites");
  await h.controller.onAuthReady();
  assert.equal(h.state.getCurrentDestination(), "favorites");
  assert.equal(h.browser.entries.length, 1);
  h.update("history"); await tick();
  assert.equal(h.browser.entries.length, 2);
  assert.match(h.browser.location.href, /view=history/);
  h.browser.history.back(); await tick();
  assert.equal(h.state.getCurrentDestination(), "favorites");
  assert.equal(h.browser.entries.length, 2);
  h.browser.history.forward(); await tick();
  assert.equal(h.state.getCurrentDestination(), "history");
  console.log("PASS: deep link, push, Back/Forward without duplicate entries");
}
{
  const h = setup("http://host/?view=admin", { is_admin: false });
  await h.controller.onAuthReady();
  assert.equal(h.state.getCurrentDestination(), "dashboard");
  assert.equal(h.browser.location.href, "http://host/");
  h.update("favorites"); await tick();
  h.state.setCurrentUser(null);
  h.controller.onLogout(); await tick();
  assert.doesNotMatch(h.browser.location.href, /view=favorites/);
  h.browser.history.back(); await tick();
  assert.doesNotMatch(h.browser.location.href, /view=/);
  console.log("PASS: unauthorized Admin and logout / back guard");
}
{
  const h = setup("http://host/?view=playlist&playlist=Jazz");
  await h.controller.onAuthReady();
  assert.equal(h.state.getCurrentPlaylistName(), "Jazz");
  h.update("playlist", "Rock"); await tick();
  assert.match(h.browser.location.href, /playlist=Rock/);
  h.update("playlist", "Rock"); await tick();
  assert.equal(h.browser.entries.length, 2);
  console.log("PASS: playlist identity and duplicate entry suppression");
}
console.log("BEHAVIOR_GATE=PASS");
