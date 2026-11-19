# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Recommendation dialog and session isolation contracts."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fluxtuner.web.app import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_recommendation_controls_are_published() -> None:
    client = TestClient(create_app())
    html = client.get("/").text
    module = client.get("/static/js/recommendations.js")
    app = client.get("/static/app.js").text
    assert module.status_code == 200
    assert html.count("data-recommendations-dialog") == 1
    assert html.count("data-recommendations-open") == 1
    assert "import { createRecommendationsController }" in app
    assert "recommendationController.syncSession" not in app  # session UI owns invalidation
    assert "data-share-station" in client.get("/static/js/station-renderer.js").text
    assert "data-share-playlist" in client.get("/static/js/playlist-renderer.js").text


def test_recommendation_controller_invalidates_stale_session(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required by the Web JavaScript test suite.")
    source = (ROOT / "fluxtuner/web/static/js/recommendations.js").read_text()
    source = source.replace(
        'import { stationUrl } from "./stations.js";',
        "const stationUrl = (station) => station.url;",
        1,
    )
    module_path = tmp_path / "recommendations.mjs"
    module_path.write_text(source)
    script = r"""
import assert from "node:assert/strict";
const { createRecommendationsController } = await import(process.argv[1]);
const nodes = new Map();
const documentStub = {
  createElement() { return element(); },
};
globalThis.document = documentStub;
function element() {
  return {
    textContent: "", value: "", disabled: false, hidden: false, dataset: {},
    children: [], events: {},
    addEventListener(type, fn) { this.events[type] = fn; },
    replaceChildren(...children) { this.children = children; },
    append(...children) { this.children.push(...children); },
    focus() {},
  };
}
for (const role of ["title", "close", "compose", "form", "recipient", "message",
                    "items", "received", "sent", "prev", "next", "cancel"]) {
  nodes.set(role, element());
}
const dialog = element();
dialog.open = false;
dialog.showModal = () => { dialog.open = true; };
dialog.close = () => { dialog.open = false; dialog.events.close?.(); };
dialog.querySelector = (selector) => {
  const match = selector.match(/data-recommendations-([a-z]+)/);
  return nodes.get(match?.[1]) || null;
};
const openButton = element();
let user = { id: 1 };
let session = "alice";
let complete;
let deferList = true;
const requests = [];
const controller = createRecommendationsController({
  dialog, openButton,
  getCurrentUser: () => user,
  getSessionKey: () => session,
  apiFetch: (url, options = {}) => {
    requests.push({ url, options });
    if (url.startsWith("/api/recommendations?")) {
      if (deferList) return new Promise((resolve) => { complete = resolve; });
      return Promise.resolve({ ok: true, json: async () => ({ recommendations: [] }) });
    }
    return Promise.resolve({ ok: true, json: async () => ({ id: 42 }) });
  },
});
controller.bind();
openButton.events.click();
assert.equal(dialog.open, true);
assert.equal(requests.length, 1);
user = { id: 2 };
session = "bob";
controller.syncSession();
assert.equal(dialog.open, false);
complete({ ok: true, json: async () => ({ recommendations: [{title:"Private Alice"}] }) });
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(nodes.get("items").children.length, 0);
deferList = false;
controller.shareStation({ name: "Radio One", url: "https://example.com/one" });
assert.equal(dialog.open, true);
nodes.get("recipient").value = "charlie";
await nodes.get("form").events.submit({ preventDefault() {} });
assert.equal(requests.at(-2).options.method, "POST");
assert.deepEqual(JSON.parse(requests.at(-2).options.body), {
  recipient_username: "charlie", kind: "station", station_key: "https://example.com/one",
});
controller.closeIfOpen();
assert.equal(dialog.open, false);
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(module_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
