# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Offline browser-controller contracts for remote subscriptions."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "fluxtuner/web/static/js/remote-subscriptions.js"

SCRIPT = r"""
import assert from "node:assert/strict";

const { createRemoteSubscriptionController } = await import(process.argv[2]);
const scenario = process.argv[3];

function node(extra = {}) {
  return {
    value: "",
    hidden: false,
    disabled: false,
    textContent: "",
    listeners: {},
    children: [],
    addEventListener(type, callback) {
      this.listeners[type] = callback;
    },
    replaceChildren(...children) {
      this.children = children;
    },
    append(...children) {
      this.children.push(...children);
    },
    ...extra,
  };
}

const documentRef = { createElement: () => node() };
const elements = {
  openButton: node(),
  dialog: node({
    open: false,
    showModal() { this.open = true; },
    close() { this.open = false; },
  }),
  form: node(),
  urlInput: node(),
  listNode: node({ ownerDocument: documentRef }),
  previewNode: node(),
  messageNode: node(),
  confirmButton: node(),
  closeButton: node(),
};

const state = { user: { id: 7 }, csrf: "session-a" };
const requests = [];
let items = [];
let pendingResponse;
let defer = false;
let deleteApproved = true;

const payload = {
  revision: 1,
  receipt: "private-receipt",
  added: [{ name: "<img onerror=alert(1)>", url: "https://stream.example/new" }],
  removed: [{ name: "Old", url: "https://stream.example/old" }],
  changed: [],
  unchanged: 0,
};

function response(value) {
  return { ok: true, json: async () => value };
}

const controller = createRemoteSubscriptionController({
  elements,
  getCurrentUser: () => state.user,
  getSessionKey: () => state.csrf,
  confirmDelete: () => deleteApproved,
  apiFetch: async (url, options) => {
    requests.push({ url, options });
    if (defer) return new Promise((resolve) => { pendingResponse = resolve; });
    if (url.endsWith("/preview")) {
      return response(
        scenario === "not-modified"
          ? { status: "not_modified", revision: 1, not_modified: true }
          : payload
      );
    }
    if (url.includes("/confirm?")) return response({ status: "ok", revision: 2 });
    if (options.method === "DELETE") {
      items = [];
      return response({ status: "ok" });
    }
    if (options.method === "POST") {
      items = [{ source_id: 15, revision: 1 }];
      return response({ status: "ok", source_id: 15 });
    }
    return response({ subscriptions: items });
  },
});
controller.bind();

if (scenario === "lifecycle") {
  await controller.openDialog();
  assert.equal(elements.dialog.open, true);
  assert.equal(requests[0].options.method, "GET");

  elements.urlInput.value = "https://catalog.example/list.m3u";
  await elements.form.listeners.submit({ preventDefault() {} });
  const add = requests.find((request) => request.options.method === "POST");
  assert.equal(JSON.parse(add.options.body).url, elements.urlInput.value || "https://catalog.example/list.m3u");
  assert.equal(items.length, 1);

  await controller.preview(15);
  assert.equal(elements.confirmButton.hidden, false);
  assert.match(elements.previewNode.textContent, /<img onerror=alert\(1\)>/);
  assert.equal(elements.previewNode.children.length, 0);

  await controller.confirm();
  const confirm = requests.find((request) => request.url.includes("/confirm?"));
  assert.equal(confirm.options.headers["X-FluxTuner-Refresh-Receipt"], "private-receipt");
  assert.equal(confirm.options.body, undefined);
  assert.equal(elements.confirmButton.hidden, true);

  deleteApproved = false;
  await controller.remove(15);
  assert.equal(requests.filter((request) => request.options.method === "DELETE").length, 0);

  deleteApproved = true;
  await controller.remove(15);
  assert.equal(requests.filter((request) => request.options.method === "DELETE").length, 1);
  assert.equal(items.length, 0);
} else if (scenario === "stale-session") {
  await controller.openDialog();
  defer = true;
  const preview = controller.preview(15);
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(typeof pendingResponse, "function");
  state.csrf = "session-b";
  controller.syncSession();
  assert.equal(elements.dialog.open, false);
  pendingResponse(response(payload));
  await preview;
  assert.equal(elements.confirmButton.hidden, true);
  assert.equal(elements.previewNode.hidden, true);
} else if (scenario === "not-modified") {
  await controller.openDialog();
  await controller.preview(15);
  assert.equal(elements.confirmButton.hidden, true);
  assert.equal(elements.previewNode.hidden, true);
  assert.match(elements.messageNode.textContent, /already up to date/);
  assert.equal(
    requests.filter((request) => request.url.includes("/confirm?")).length,
    0,
  );
} else if (scenario === "closed-dialog") {
  await controller.openDialog();
  defer = true;
  const preview = controller.preview(15);
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(controller.closeIfOpen(), false);
  // While an operation is in flight, closing is deliberately blocked.
  assert.equal(elements.dialog.open, true);
  pendingResponse(response(payload));
  await preview;
  assert.equal(controller.closeIfOpen(), true);
  assert.equal(elements.dialog.open, false);
  assert.equal(elements.confirmButton.hidden, true);
} else {
  throw new Error(`Unknown scenario: ${scenario}`);
}
"""


@pytest.mark.parametrize(
    "scenario",
    ["lifecycle", "stale-session", "closed-dialog", "not-modified"],
)
def test_remote_subscription_controller(tmp_path: Path, scenario: str) -> None:
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")

    module = tmp_path / "remote-subscriptions.mjs"
    module.write_text(MODULE.read_text(encoding="utf-8"), encoding="utf-8")
    script = tmp_path / "contract.mjs"
    script.write_text(SCRIPT, encoding="utf-8")

    result = subprocess.run(
        [node, str(script), str(module), scenario],
        text=True,
        capture_output=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, f"Scenario {scenario} failed\n{result.stdout}\n{result.stderr}"
