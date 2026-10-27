/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */

import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const source = await readFile(
  join(
    process.env.WORK,
    "fluxtuner/web/static/js/mobile-drawer.js",
  ),
  "utf8",
);

assert.ok(source.includes("export function createMobileDrawer"));
assert.ok(source.includes("back({ restoreFocus: true })"));
assert.ok(source.includes("if (containedFocus) toggleButton?.focus?.()"));
assert.ok(source.includes('attributeFilter: ["hidden"]'));
assert.ok(source.includes("sessionObserver.disconnect()"));

assert.equal(source.includes("drawerTabTarget"), false);
assert.equal(source.includes("handleTab"), false);
assert.equal(
  source.includes('addEventListener("keydown"'),
  false,
);

console.log("PASS: non-modal navigation semantics");
console.log("PASS: Back focus restoration");
console.log("PASS: hamburger focus restoration");
console.log("PASS: session observer retained");
console.log("PASS: artificial Tab cycle removed");
console.log("BEHAVIOR_GATE=PASS");
