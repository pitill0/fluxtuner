/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const source = await readFile(
  join(process.env.WORK, "fluxtuner/web/static/js/app-state.js"),
  "utf8",
);

const { createAppState } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`,
);

const state = createAppState();

assert.equal(state.getCurrentSection(), "explore");
assert.equal(state.getCurrentView(), "search");
assert.equal(state.getCurrentDestination(), "explore");
console.log("PASS: initial destination");

for (const [view, expected] of [
  ["favorites", "favorites"],
  ["playlists", "playlists"],
  ["playlist", "playlists"],
  ["history", "history"],
  ["search", "explore"],
]) {
  state.setCurrentView(view);
  assert.equal(state.getCurrentDestination(), expected);
}
console.log("PASS: library destination derivation");

state.setCurrentView("playlist");
state.setCurrentPlaylistName("Jazz");
assert.equal(state.setCurrentSection("account"), true);
assert.equal(state.getCurrentDestination(), "account");
assert.equal(state.getCurrentView(), "playlist");
assert.equal(state.getCurrentPlaylistName(), "Jazz");

assert.equal(state.setCurrentSection("admin"), true);
assert.equal(state.getCurrentDestination(), "admin");

assert.equal(state.setCurrentSection("dashboard"), true);
assert.equal(state.getCurrentDestination(), "dashboard");
console.log("PASS: primary sections retain library context");

assert.equal(state.setCurrentSection("unknown"), false);
assert.equal(state.getCurrentDestination(), "dashboard");
console.log("PASS: unknown sections rejected");

assert.equal(state.setCurrentSection("explore"), true);
assert.equal(state.getCurrentDestination(), "playlists");
assert.equal(state.getCurrentPlaylistName(), "Jazz");
console.log("PASS: returning to library context");

let notifications = 0;
const unsubscribe = state.subscribeViewChange(() => {
  notifications += 1;
});

state.setCurrentView("favorites");
assert.equal(notifications, 1);
unsubscribe();
state.setCurrentView("history");
assert.equal(notifications, 1);
console.log("PASS: existing view subscription preserved");

state.setCurrentUser({ is_admin: false });
assert.equal(state.isAuthenticated(), true);
state.setCurrentUser(null);
assert.equal(state.isAuthenticated(), false);
console.log("PASS: existing authentication interface preserved");

console.log("BEHAVIOR_GATE=PASS");
