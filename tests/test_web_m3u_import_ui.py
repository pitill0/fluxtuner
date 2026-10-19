from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "fluxtuner/web/static/js/station-imports.js"

SCRIPT = r"""
import assert from "node:assert/strict";
const { createStationImportController } = await import(process.argv[1]);
const scenario = process.argv[2];
function node(extra = {}) {
  return {
    value: "", hidden: false, disabled: false, textContent: "", listeners: {},
    addEventListener(type, callback) { this.listeners[type] = callback; },
    replaceChildren(...children) { this.children = children; },
    focus() { this.focused = true; },
    ...extra,
  };
}
const state = { user: { id: 1 }, session: "one" };
const data = new TextEncoder().encode("#EXTM3U\nhttps://radio.example/live").buffer;
const file = { name: "My stations.m3u8", size: data.byteLength, arrayBuffer: async () => data };
const elements = {
  openButton: node(), form: node({ reset() {} }),
  dialog: node({
    open: false, showModal() { this.open = true; }, close() { this.open = false; },
  }),
  fileInput: node({ files: [file] }),
  previewButton: node(), previewNode: node(), destinationNode: node(),
  selectNode: node({ ownerDocument: { createElement: () => node() } }),
  nameField: node(), nameInput: node(), messageNode: node(),
  submitButton: node(), cancelButton: node(),
};
const requests = [];
const saved = [];
let delay = false;
let fail = false;
let resolveRequest;
const preview = {
  entries: [{ name: "<img src=x onerror=alert(1)>", url: "https://radio.example/live", existing: true }],
  playlists: ["Morning"],
  issues: [{ line_number: 5, reason: "Unsupported URL" }],
  duplicates: 1,
};
const success = { name: "My stations", added_to_playlist: 1, existing_favorites: 1 };
const controller = createStationImportController({
  elements,
  getCurrentUser: () => state.user,
  getSessionKey: () => state.session,
  onSaved: async (payload) => { saved.push(payload); },
  apiFetch: async (endpoint, options) => {
    requests.push({ endpoint, options });
    if (delay) return await new Promise((resolve) => { resolveRequest = resolve; });
    return {
      ok: !fail,
      json: async () => fail ? { detail: "Rejected file" }
        : endpoint.endsWith("/preview") ? preview : success,
    };
  },
});
controller.bind();
controller.openDialog();
const event = { preventDefault() {} };
const response = { ok: true, json: async () => preview };

if (scenario === "preview-cancel") {
  await controller.preview();
  assert.equal(requests.length, 1);
  assert.equal(requests[0].endpoint, "/api/stations/import/preview");
  assert.equal(elements.previewNode.hidden, false);
  assert.match(elements.previewNode.textContent, /<img src=x onerror=alert\(1\)>/);
  assert.match(elements.previewNode.textContent, /already in favorites/);
  assert.match(elements.previewNode.textContent, /Line 5/);
  assert.equal(elements.submitButton.disabled, false);
  elements.cancelButton.listeners.click();
  assert.equal(elements.dialog.open, false);
  assert.equal(requests.length, 1);
  assert.equal(saved.length, 0);
} else if (scenario === "new-playlist" || scenario === "existing-playlist") {
  await controller.preview();
  if (scenario === "existing-playlist") elements.selectNode.value = "0";
  await controller.submit(event);
  const request = requests[1];
  const url = new URL(request.endpoint, "http://localhost");
  assert.equal(url.searchParams.get("playlist"), scenario === "new-playlist" ? "My stations" : "Morning");
  assert.equal(url.searchParams.get("existing"), String(scenario === "existing-playlist"));
  assert.equal(request.options.body, requests[0].options.body);
  assert.equal(request.options.headers["Content-Type"], "application/octet-stream");
  assert.equal(elements.dialog.open, false);
  assert.equal(saved.length, 1);
} else if (scenario === "oversized") {
  elements.fileInput.files = [{ ...file, size: 1024 * 1024 + 1 }];
  await controller.preview();
  assert.equal(requests.length, 0);
  assert.match(elements.messageNode.textContent, /exceeds 1 MiB/);
  assert.equal(elements.submitButton.disabled, true);
} else if (scenario === "file-change") {
  await controller.preview();
  controller.fileChanged();
  await controller.submit(event);
  assert.equal(requests.length, 1);
  assert.equal(elements.submitButton.disabled, true);
} else if (scenario === "preview-error") {
  fail = true;
  await controller.preview();
  assert.equal(elements.dialog.open, true);
  assert.equal(elements.messageNode.textContent, "Rejected file");
  assert.equal(elements.submitButton.disabled, true);
} else if (scenario === "import-error") {
  await controller.preview();
  fail = true;
  await controller.submit(event);
  assert.equal(elements.dialog.open, true);
  assert.equal(elements.messageNode.textContent, "Rejected file");
  assert.equal(elements.submitButton.disabled, false);
  assert.equal(saved.length, 0);
} else if (scenario === "double-submit") {
  await controller.preview();
  delay = true;
  const request = controller.submit(event);
  await controller.submit(event);
  assert.equal(requests.length, 2);
  assert.equal(elements.cancelButton.disabled, true);
  controller.closeIfOpen();
  assert.equal(elements.dialog.open, true);
  resolveRequest({ ok: true, json: async () => success });
  await request;
  assert.equal(saved.length, 1);
} else if (scenario === "stale-preview" || scenario === "session-change") {
  delay = true;
  const request = controller.preview();
  await Promise.resolve();
  await Promise.resolve();
  assert.equal(requests.length, 1);
  if (scenario === "stale-preview") {
    controller.closeIfOpen();
    controller.openDialog();
    elements.messageNode.textContent = "New dialog";
  } else {
    state.user = { id: 2 };
    state.session = "two";
    controller.syncSession();
  }
  resolveRequest(response);
  await request;
  assert.equal(saved.length, 0);
  assert.equal(elements.submitButton.disabled, true);
  if (scenario === "stale-preview") {
    assert.equal(elements.dialog.open, true);
    assert.equal(elements.messageNode.textContent, "New dialog");
  } else assert.equal(elements.dialog.open, false);
} else if (scenario === "session-during-file-read") {
  let resolveFile;
  elements.fileInput.files = [{
    ...file,
    arrayBuffer: () => new Promise((resolve) => { resolveFile = resolve; }),
  }];
  const request = controller.preview();
  state.session = "two";
  controller.syncSession();
  resolveFile(data);
  await request;
  assert.equal(requests.length, 0);
  assert.equal(elements.dialog.open, false);
} else if (scenario === "unauthenticated") {
  controller.closeIfOpen();
  state.user = null;
  controller.syncSession();
  controller.openDialog();
  assert.equal(elements.dialog.open, false);
  assert.equal(elements.openButton.disabled, true);
  assert.equal(requests.length, 0);
}
console.log(JSON.stringify({ passed: true }));
"""


@pytest.mark.parametrize(
    "scenario",
    [
        "preview-cancel",
        "new-playlist",
        "existing-playlist",
        "oversized",
        "file-change",
        "preview-error",
        "import-error",
        "double-submit",
        "stale-preview",
        "session-change",
        "session-during-file-read",
        "unauthenticated",
    ],
)
def test_station_import_controller(tmp_path, scenario):
    node = shutil.which("node")
    assert node, "Node.js is required for Web JavaScript tests"
    module = tmp_path / "station-imports.mjs"
    module.write_text(MODULE.read_text())
    result = subprocess.run(
        [node, "--input-type=module", "--eval", SCRIPT, str(module), scenario],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"passed": True}
