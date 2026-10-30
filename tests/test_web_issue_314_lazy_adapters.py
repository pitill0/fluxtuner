# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Executable lazy-adapter integration contracts for issue #314."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "fluxtuner/web/static/js"


@pytest.mark.parametrize(
    ("adapter_file", "module_file", "factory", "kind"),
    [
        (
            "station-imports-lazy.js",
            "station-imports.js",
            "createStationImportController",
            "imports",
        ),
        (
            "remote-subscriptions-lazy.js",
            "remote-subscriptions.js",
            "createRemoteSubscriptionController",
            "subscriptions",
        ),
        (
            "custom-stations-lazy.js",
            "custom-stations.js",
            "createCustomStationController",
            "custom",
        ),
    ],
)
def test_lazy_adapter_event_and_session_contract(
    tmp_path: Path,
    adapter_file: str,
    module_file: str,
    factory: str,
    kind: str,
) -> None:
    (tmp_path / "package.json").write_text('{"type":"module"}\n', encoding="utf-8")
    for filename in (adapter_file, "deferred-controller.js"):
        shutil.copyfile(ROOT / filename, tmp_path / filename)

    (tmp_path / module_file).write_text(
        f"""
export function {factory}(options) {{
  globalThis.stats.factories += 1;
  return {{
    bind({{ skipOpenButton = false }} = {{}}) {{
      globalThis.stats.binds += 1;
      globalThis.stats.skipOpenButton = skipOpenButton;
      if (!skipOpenButton) {{
        const button = options.elements?.openButton ?? options.openButton;
        button?.addEventListener("click", () => {{
          globalThis.stats.duplicateEvents += 1;
        }});
      }}
    }},
    syncSession() {{ globalThis.stats.syncs += 1; }},
    closeIfOpen() {{
      globalThis.stats.closes += 1;
      return false;
    }},
    updateVisibility(view) {{
      globalThis.stats.views.push(view);
    }},
    openDialog(event) {{
      globalThis.stats.opens += 1;
      globalThis.stats.openers.push(event?.currentTarget?.id ?? null);
    }},
  }};
}}
""",
        encoding="utf-8",
    )

    script = r"""
import assert from "node:assert/strict";

const { kind, modulePath } = JSON.parse(process.argv[1]);
const module = await import(modulePath);
const factoryName = {
  imports: "createLazyStationImportController",
  subscriptions: "createLazyRemoteSubscriptionController",
  custom: "createLazyCustomStationController",
}[kind];

globalThis.stats = {
  factories: 0,
  binds: 0,
  syncs: 0,
  closes: 0,
  opens: 0,
  duplicateEvents: 0,
  skipOpenButton: null,
  openers: [],
  views: [],
};

function button(id) {
  const listeners = new Map();
  return {
    id,
    disabled: false,
    addEventListener(type, callback) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(callback);
    },
    click() {
      for (const callback of listeners.get("click") || []) {
        callback({ currentTarget: this });
      }
    },
    listenerCount(type) {
      return (listeners.get(type) || []).length;
    },
  };
}

let user = { id: 1 };
let session = "session-1";
const openButton = button("primary");
const toolsNode = { hidden: true };
const messageNode = { textContent: "" };

const options = {
  getCurrentUser: () => user,
  getSessionKey: () => session,
  openButton,
  toolsNode,
  messageNode,
  elements: { openButton, messageNode },
};

const controller = module[factoryName](options);
controller.bind();
controller.bind();

assert.equal(openButton.listenerCount("click"), 1);
assert.equal(globalThis.stats.factories, 0);

if (kind === "custom") {
  controller.updateVisibility("favorites");
  assert.equal(toolsNode.hidden, false);
}

openButton.click();
await new Promise((resolve) => setImmediate(resolve));

assert.equal(globalThis.stats.factories, 1);
assert.equal(globalThis.stats.binds, 1);
assert.equal(globalThis.stats.opens, 1);
assert.equal(globalThis.stats.duplicateEvents, 0);
assert.equal(globalThis.stats.skipOpenButton, true);

// The full custom-station controller must inherit the current view
// immediately after deferred initialization.
if (kind === "custom") {
  assert.deepEqual(globalThis.stats.views, ["favorites"]);
}

openButton.click();
await new Promise((resolve) => setImmediate(resolve));

assert.equal(globalThis.stats.factories, 1);
assert.equal(globalThis.stats.opens, 2);
assert.equal(openButton.listenerCount("click"), 1);

session = "session-2";
controller.syncSession();
user = null;
controller.syncSession();
openButton.click();
await new Promise((resolve) => setImmediate(resolve));

assert.equal(globalThis.stats.opens, 2);

if (kind === "custom") {
  assert.equal(openButton.disabled, true);
  assert.equal(toolsNode.hidden, true);
  assert.deepEqual(globalThis.stats.openers, ["primary", "primary"]);
}
if (kind === "imports") {
  assert.equal(openButton.disabled, true);
}
assert.equal(typeof controller.closeIfOpen(), "boolean");

console.log(JSON.stringify({
  kind,
  factories: globalThis.stats.factories,
  binds: globalThis.stats.binds,
  opens: globalThis.stats.opens,
  duplicateEvents: globalThis.stats.duplicateEvents,
}));
"""

    completed = subprocess.run(
        [
            "node",
            "--input-type=module",
            "--eval",
            script,
            json.dumps(
                {
                    "kind": kind,
                    "modulePath": (tmp_path / adapter_file).as_uri(),
                }
            ),
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    )

    result = json.loads(completed.stdout)
    assert result == {
        "kind": kind,
        "factories": 1,
        "binds": 1,
        "opens": 2,
        "duplicateEvents": 0,
    }
