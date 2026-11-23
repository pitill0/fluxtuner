# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Browser-independent recommendation acceptance feedback contracts."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_acceptance_feedback_and_navigation(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js required for Web JavaScript tests.")

    source = (ROOT / "fluxtuner/web/static/js/recommendations.js").read_text(encoding="utf-8")

    original = 'import { stationUrl } from "./stations.js";'
    assert source.count(original) == 1
    source = source.replace(
        original,
        "const stationUrl = (station) => station.url;",
        1,
    )

    module = tmp_path / "recommendations.mjs"
    module.write_text(source, encoding="utf-8")

    script = r"""
import assert from "node:assert/strict";

const { createRecommendationsController } =
  await import(process.argv[1]);

function element() {
  return {
    textContent: "",
    value: "",
    disabled: false,
    hidden: false,
    dataset: {},
    children: [],
    events: {},
    className: "",
    addEventListener(name, handler) {
      this.events[name] = handler;
    },
    replaceChildren(...children) {
      this.children = children;
    },
    append(...children) {
      this.children.push(...children);
    },
    focus() {},
    closest(selector) {
      return selector === "[data-recommendation-action]"
        ? this : null;
    },
  };
}

globalThis.document = {
  createElement: () => element(),
};

const tick = () => new Promise(resolve => setImmediate(resolve));

async function settle() {
  for (let i = 0; i < 8; i++) await tick();
}

function fixture({
  kind = "station",
  outcome = { status: "accepted", added_favorites: 1 },
  fail = false,
  deferred = false,
} = {}) {
  const roles = new Map();
  for (const role of [
    "title", "close", "compose", "form", "recipient",
    "message", "items", "received", "sent", "prev", "next",
    "cancel", "destination", "view",
  ]) {
    roles.set(role, element());
  }

  const dialog = element();
  dialog.open = false;
  dialog.showModal = () => { dialog.open = true; };
  dialog.close = () => {
    dialog.open = false;
    dialog.events.close?.();
  };
  dialog.querySelector = selector => {
    const match = selector.match(
      /data-recommendations-([a-z]+)/
    );
    return roles.get(match?.[1]) || null;
  };

  let user = { id: 1 };
  let session = "session-one";
  let complete;
  const requests = [];
  const destinations = [];

  const apiFetch = (url, options = {}) => {
    requests.push({ url, options });
    if (url.startsWith("/api/recommendations?")) {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          recommendations: [{
            id: 42,
            kind,
            status: "pending",
            title: "Shared content",
            counterpart_username: "sender",
          }],
        }),
      });
    }
    if (fail) return Promise.resolve({ ok: false, status: 409 });
    if (deferred) {
      return new Promise(resolve => { complete = resolve; });
    }
    return Promise.resolve({
      ok: true,
      json: async () => outcome,
    });
  };

  const controller = createRecommendationsController({
    apiFetch,
    dialog,
    openButton: element(),
    getCurrentUser: () => user,
    getSessionKey: () => session,
    onOpenAccepted: destination => destinations.push(destination),
  });
  controller.bind();
  controller.show();

  const action = async (name = "accept") => {
    await settle();
    const card = roles.get("items").children[0];
    assert.ok(card, "Recommendation card missing");
    const actions = card.children[2];
    const button = actions.children[
      name === "accept" ? 0 : 1
    ];
    roles.get("items").events.click({ target: button });
    return button;
  };

  return {
    roles,
    dialog,
    controller,
    requests,
    destinations,
    action,
    async completePending(value = outcome) {
      assert.ok(complete);
      complete({
        ok: true,
        json: async () => value,
      });
      await settle();
    },
    switchUser() {
      user = { id: 2 };
      session = "session-two";
      controller.syncSession();
    },
  };
}

{
  const fx = fixture();
  await fx.action();
  await settle();

  assert.match(
    fx.roles.get("message").textContent,
    /Station added to Favorites/
  );
  assert.equal(fx.roles.get("destination").hidden, false);
  assert.equal(fx.roles.get("view").textContent, "View Favorites");

  fx.roles.get("view").events.click();
  assert.deepEqual(fx.destinations, [{ kind: "station" }]);
  assert.equal(fx.dialog.open, false);
}

{
  const fx = fixture({
    outcome: {
      status: "accepted",
      added_favorites: 0,
      existing_favorites: 1,
    },
  });
  await fx.action();
  await settle();

  assert.match(
    fx.roles.get("message").textContent,
    /already in Favorites/
  );
  assert.equal(fx.roles.get("destination").hidden, false);
}

{
  const fx = fixture({
    kind: "playlist",
    outcome: {
      status: "accepted",
      playlist_name: "Morning / Jazz",
      added_to_playlist: 3,
    },
  });
  await fx.action();
  await settle();

  assert.match(
    fx.roles.get("message").textContent,
    /Playlist added to your library/
  );
  assert.equal(fx.roles.get("view").textContent, "View Playlist");
  fx.roles.get("view").events.click();
  assert.deepEqual(fx.destinations, [{
    kind: "playlist",
    playlistName: "Morning / Jazz",
  }]);
}

{
  const fx = fixture();
  await fx.action("reject");
  await settle();

  assert.equal(
    fx.roles.get("message").textContent,
    "Recommendation rejected."
  );
  assert.equal(fx.roles.get("destination").hidden, true);
  assert.deepEqual(fx.destinations, []);
}

{
  const fx = fixture({ fail: true });
  await fx.action();
  await settle();

  assert.match(
    fx.roles.get("message").textContent,
    /Could not resolve recommendation/
  );
  assert.equal(fx.roles.get("destination").hidden, true);
  assert.deepEqual(fx.destinations, []);
}

{
  const fx = fixture({ deferred: true });
  await fx.action();
  await settle();

  fx.switchUser();
  await fx.completePending();

  assert.equal(fx.dialog.open, false);
  assert.equal(fx.roles.get("message").textContent, "");
  assert.equal(fx.roles.get("destination").hidden, true);
  assert.deepEqual(fx.destinations, []);
}

console.log("PASS: station, duplicate, playlist, rejection, error, session isolation");
"""

    result = subprocess.run(
        [node, "--input-type=module", "--eval", script, str(module)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS: station, duplicate, playlist" in result.stdout


def test_feedback_controls_are_served() -> None:
    from fastapi.testclient import TestClient

    from fluxtuner.web.app import create_app

    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert "data-recommendations-destination hidden" in response.text
    assert "data-recommendations-view" in response.text

    app = client.get("/static/app.js").text
    assert "onOpenAccepted:" in app
    assert "navigateToPrivateView(loadFavorites)" in app
    assert "loadPlaylistStations(playlistName)" in app
