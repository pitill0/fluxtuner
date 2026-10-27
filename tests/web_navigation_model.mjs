/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const source = await readFile(
  join(
    process.env.WORK,
    "fluxtuner/web/static/js/navigation-model.js",
  ),
  "utf8",
);

const {
  NAVIGATION_DESTINATIONS,
  canNavigate,
  navigationPath,
  createNavigationModel,
} = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString("base64")}`
);

const listener = { is_admin: false };
const admin = { is_admin: true };

assert.equal(Object.keys(NAVIGATION_DESTINATIONS).length, 10);
assert.deepEqual(navigationPath("catalogs"), ["library", "catalogs"]);
assert.deepEqual(navigationPath("explore"), ["explore"]);
assert.deepEqual(navigationPath("unknown"), []);

assert.equal(canNavigate("favorites", null), false);
assert.equal(canNavigate("favorites", listener), true);
assert.equal(canNavigate("admin", listener), false);
assert.equal(canNavigate("admin", admin), true);
assert.equal(canNavigate("unknown", admin), false);

const navigation = createNavigationModel({ user: listener });

assert.equal(navigation.snapshot().destination, "explore");

assert.equal(navigation.navigate("catalogs"), true);
assert.deepEqual(
  navigation.snapshot().path,
  ["library", "catalogs"],
);

assert.equal(navigation.navigate("admin"), false);
assert.equal(navigation.snapshot().destination, "catalogs");

assert.equal(navigation.navigate("not-a-destination"), false);
assert.equal(navigation.snapshot().destination, "catalogs");

navigation.updateUser(admin);
assert.equal(navigation.navigate("admin"), true);
assert.equal(navigation.snapshot().destination, "admin");

navigation.updateUser(listener);
assert.equal(navigation.snapshot().destination, null);
assert.equal(navigation.navigate("favorites"), true);

const previousSnapshot = navigation.snapshot();

navigation.updateUser(null);

assert.equal(navigation.snapshot().destination, null);
assert.equal(navigation.snapshot().authenticated, false);
assert.deepEqual(navigation.snapshot().available, []);
assert.equal(previousSnapshot.destination, "favorites");

assert.equal(navigation.navigate("favorites"), false);

assert.equal(
  createNavigationModel().snapshot().destination,
  null,
);

console.log("PASS: destinations and hierarchy");
console.log("PASS: authorization");
console.log("PASS: navigation transitions");
console.log("PASS: session changes");
console.log("PASS: immutable snapshots");
console.log("BEHAVIOR_GATE=PASS");
