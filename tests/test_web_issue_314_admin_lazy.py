# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Session-safe lazy administrative controller contracts for #314."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_lazy_admin_loads_once_and_invalidates_stale_actions(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "fluxtuner/web/static/js/admin-lazy.js"
    module = tmp_path / "admin-lazy.mjs"
    module.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    script = r"""
const { createLazyAdminController } = await import(process.argv[1]);

let currentUser = { id: 1, is_admin: true };
let resolveImport;
let imports = 0;
let calls = [];
let resets = 0;

const messageNode = { textContent: "old message" };
const usersNode = { innerHTML: "old users" };

const original = {
  createUser: async () => calls.push("create"),
  loadUsers: async () => calls.push("load"),
  loadUsersIfNeeded: async () => calls.push("loadIfNeeded"),
  mutateUser: async () => calls.push("mutate"),
  reset: () => { resets += 1; },
  setUserPassword: async () => calls.push("password"),
};

const adapter = createLazyAdminController(
  {
    getCurrentUser: () => currentUser,
    messageNode,
    usersNode,
  },
  {
    loadModule: () => {
      imports += 1;
      return new Promise((resolve) => {
        resolveImport = resolve;
      });
    },
  },
);

const first = adapter.loadUsers();
const second = adapter.loadUsersIfNeeded();

await Promise.resolve();
const sharedImport = imports === 1;

currentUser = null;
adapter.reset();

const resetWasSynchronous =
  messageNode.textContent === "" &&
  usersNode.innerHTML.includes("Admin users will appear here.");

resolveImport({ createAdminController: () => original });
await Promise.all([first, second]);

const staleActionsBlocked = calls.length === 0;

currentUser = { id: 2, is_admin: true };
await adapter.loadUsers();

let prevented = false;
await adapter.createUser({
  preventDefault() { prevented = true; },
});

const freshActions = [...calls];

adapter.reset();
const resetDelegated = resets === 1;

let failures = 0;
let retryCurrentUser = { id: 3, is_admin: true };
const errorMessage = { textContent: "" };

const retryAdapter = createLazyAdminController(
  {
    getCurrentUser: () => retryCurrentUser,
    messageNode: errorMessage,
  },
  {
    loadModule: async () => {
      failures += 1;
      if (failures === 1) throw new Error("Module unavailable");
      return { createAdminController: () => original };
    },
  },
);

await retryAdapter.loadUsers();
const errorDisplayed = errorMessage.textContent.includes("Module unavailable");

await retryAdapter.loadUsers();
const retriedSuccessfully = failures === 2;

console.log(JSON.stringify({
  sharedImport,
  resetWasSynchronous,
  staleActionsBlocked,
  imports,
  freshActions,
  prevented,
  resetDelegated,
  errorDisplayed,
  retriedSuccessfully,
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
        "sharedImport": True,
        "resetWasSynchronous": True,
        "staleActionsBlocked": True,
        "imports": 1,
        "freshActions": ["load", "create"],
        "prevented": True,
        "resetDelegated": True,
        "errorDisplayed": True,
        "retriedSuccessfully": True,
    }
