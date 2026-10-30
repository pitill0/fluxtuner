# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Lazy-controller concurrency and lifecycle contracts for issue #314."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_deferred_controller_lifecycle(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "fluxtuner/web/static/js/deferred-controller.js"
    module = tmp_path / "deferred-controller.mjs"
    module.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    script = r"""
import assert from "node:assert/strict";

const { createDeferredController } = await import(process.argv[1]);

let user = { id: 1 };
let session = "session-1";
let resolveModule;
let loadCount = 0;
let bindCount = 0;
let syncCount = 0;
let opens = 0;
let errors = [];

const original = {
  bind: ({ skipOpenButton } = {}) => {
    assert.equal(skipOpenButton, true);
    bindCount += 1;
  },
  syncSession: () => { syncCount += 1; },
  closeIfOpen: () => false,
  openDialog: () => { opens += 1; },
};

const deferred = createDeferredController({
  options: { getCurrentUser: () => user },
  loadModule: () => {
    loadCount += 1;
    return new Promise((resolve) => { resolveModule = resolve; });
  },
  createName: "factory",
  getIdentity: () => `${user?.id ?? ""}:${session}`,
  onError: (error) => errors.push(String(error)),
});

assert.equal(deferred.closeIfOpen(), false);
const first = deferred.invoke("openDialog");
const second = deferred.invoke("openDialog");
await Promise.resolve();

assert.equal(loadCount, 1);
assert.equal(deferred.closeIfOpen(), true);

resolveModule({ factory: () => original });
await Promise.all([first, second]);

assert.equal(opens, 0, "Cancelled openings must not execute");
assert.equal(bindCount, 1, "Controller must bind only once");
assert.ok(syncCount >= 1);

await deferred.invoke("openDialog");
assert.equal(opens, 1);
assert.equal(loadCount, 1);

session = "session-2";
deferred.syncSession();
await deferred.invoke("openDialog");
assert.equal(opens, 2);

user = null;
deferred.syncSession();
await deferred.invoke("openDialog");
assert.equal(opens, 2, "Signed-out user cannot open a dialog");

let attempts = 0;
user = { id: 2 };
const retry = createDeferredController({
  options: { getCurrentUser: () => user },
  loadModule: async () => {
    attempts += 1;
    if (attempts === 1) throw new Error("Temporary import failure");
    return { factory: () => original };
  },
  createName: "factory",
  getIdentity: () => `${user?.id ?? ""}:${session}`,
  onError: (error) => errors.push(String(error)),
});

await retry.invoke("openDialog");
assert.equal(attempts, 1);
assert.ok(errors.some((error) => error.includes("Temporary import failure")));

await retry.invoke("openDialog");
assert.equal(attempts, 2);
assert.equal(opens, 3);

console.log(JSON.stringify({
  loadCount, bindCount, opens, attempts,
  pendingCancellation: true,
  sessionInvalidation: true,
  errorRecovery: true,
}));
"""

    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script, str(module)],
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    result = json.loads(completed.stdout)
    assert result == {
        "loadCount": 1,
        "bindCount": 2,
        "opens": 3,
        "attempts": 2,
        "pendingCancellation": True,
        "sessionInvalidation": True,
        "errorRecovery": True,
    }
