from __future__ import annotations

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "fluxtuner/web/static/js/custom-stations.js"

SCRIPT = r"""
import assert from "node:assert/strict";
const { createCustomStationController } = await import(process.argv[1]);
const scenario = process.argv[2];

function element(extra = {}) {
  return {
    hidden: true, disabled: false, textContent: "", listeners: {},
    addEventListener(type, callback) { this.listeners[type] = callback; },
    focus() { this.focused = true; },
    ...extra,
  };
}
const name = element({ value: "  Personal radio  " });
const url = element({ value: "  https://radio.example/live  " });
const submitButton = element();
const form = element({
  elements: { namedItem(key) { return key === "name" ? name : url; } },
  querySelector() { return submitButton; },
  reset() { name.value = ""; url.value = ""; },
});
const dialog = element({
  open: false,
  showModal() { this.open = true; },
  close() { this.open = false; },
});
const toolsNode = element();
const openButton = element();
const cancelButton = element();
const messageNode = element();
const state = { user: { id: 1 }, session: "session-1" };
const requests = [];
const saved = [];
let resolveRequest;
let delayed = false;
let failed = false;
const controller = createCustomStationController({
  dialog, form, messageNode, openButton, cancelButtons: [cancelButton], toolsNode,
  getCurrentUser: () => state.user,
  getSessionKey: () => state.session,
  onSaved: async (added) => { saved.push(added); },
  apiFetch: async (endpoint, options) => {
    requests.push({ endpoint, options });
    if (delayed) {
      return await new Promise((resolve) => { resolveRequest = resolve; });
    }
    return {
      ok: !failed, status: failed ? 400 : 200,
      json: async () => failed
        ? { detail: "Stream URL is malformed." }
        : { added: true },
    };
  },
});
controller.bind();
const event = { preventDefault() {} };

if (scenario === "success") {
  controller.openDialog();
  await controller.submit(event);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].endpoint, "/api/stations/custom");
  assert.equal(requests[0].options.method, "POST");
  assert.deepEqual(JSON.parse(requests[0].options.body), {
    name: "Personal radio", url: "https://radio.example/live",
  });
  assert.deepEqual(saved, [true]);
  assert.equal(dialog.open, false);
} else if (scenario === "cancel") {
  controller.openDialog();
  cancelButton.listeners.click();
  assert.equal(dialog.open, false);
  assert.equal(requests.length, 0);
  assert.equal(openButton.focused, true);
} else if (scenario === "error") {
  failed = true;
  controller.openDialog();
  await controller.submit(event);
  assert.equal(dialog.open, true);
  assert.equal(name.value, "  Personal radio  ");
  assert.equal(url.value, "  https://radio.example/live  ");
  assert.equal(messageNode.textContent, "Stream URL is malformed.");
  assert.equal(submitButton.disabled, false);
  assert.deepEqual(saved, []);
} else if (scenario === "double-submit") {
  delayed = true;
  controller.openDialog();
  const first = controller.submit(event);
  await controller.submit(event);
  assert.equal(requests.length, 1);
  resolveRequest({ ok: true, json: async () => ({ added: false }) });
  await first;
  assert.deepEqual(saved, [false]);
} else if (scenario === "session-change") {
  delayed = true;
  controller.openDialog();
  const request = controller.submit(event);
  state.user = { id: 2 };
  state.session = "session-2";
  controller.syncSession();
  resolveRequest({ ok: true, json: async () => ({ added: true }) });
  await request;
  assert.equal(dialog.open, false);
  assert.deepEqual(saved, []);
} else if (scenario === "stale-response") {
  delayed = true;
  controller.openDialog();
  const request = controller.submit(event);
  controller.closeDialog();
  controller.openDialog();
  name.value = "New form";
  resolveRequest({ ok: true, json: async () => ({ added: true }) });
  await request;
  assert.equal(dialog.open, true);
  assert.equal(name.value, "New form");
  assert.deepEqual(saved, []);
} else if (scenario === "visibility") {
  controller.updateVisibility("search");
  assert.equal(toolsNode.hidden, true);
  controller.updateVisibility("favorites");
  assert.equal(toolsNode.hidden, false);
  state.user = null;
  controller.syncSession();
  assert.equal(toolsNode.hidden, true);
  controller.openDialog();
  assert.equal(dialog.open, false);
}
console.log(JSON.stringify({ passed: true }));
"""


@pytest.mark.parametrize(
    "scenario",
    [
        "success",
        "cancel",
        "error",
        "double-submit",
        "session-change",
        "stale-response",
        "visibility",
    ],
)
def test_custom_station_controller(tmp_path, scenario):
    node = shutil.which("node")
    assert node, "Node.js is required for Web JavaScript tests"
    module = tmp_path / "custom-stations.mjs"
    module.write_text(MODULE.read_text())
    result = subprocess.run(
        [node, "--input-type=module", "--eval", SCRIPT, str(module), scenario],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"passed": True}


def test_custom_station_form_uses_native_dialog_and_bounded_fields():
    class Elements(HTMLParser):
        def __init__(self):
            super().__init__()
            self.items = []

        def handle_starttag(self, tag, attrs):
            self.items.append((tag, dict(attrs)))

    parser = Elements()
    parser.feed((ROOT / "fluxtuner/web/templates/index.html").read_text())
    dialogs = [
        attrs
        for tag, attrs in parser.items
        if tag == "dialog" and "data-custom-station-dialog" in attrs
    ]
    assert len(dialogs) == 1
    assert dialogs[0].get("aria-labelledby")
    assert any(tag == "form" and "data-custom-station-form" in attrs for tag, attrs in parser.items)
    for field, limit in [("custom_station_name", "200"), ("custom_station_url", "2048")]:
        matches = [
            attrs for tag, attrs in parser.items if tag == "input" and attrs.get("id") == field
        ]
        assert len(matches) == 1
        assert matches[0].get("maxlength") == limit
        assert "required" in matches[0]
