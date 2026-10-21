"""Regression coverage for direct Web audio without forced CORS."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / "fluxtuner/web/static/js/player.js"


def test_direct_audio_clears_cors_before_playback_and_retry() -> None:
    script = r"""
import assert from "node:assert/strict";
import { pathToFileURL } from "node:url";

const { createPlayerController } = await import(
  pathToFileURL(process.argv[1]).href
);

class FakeAudio {
  constructor() {
    this.attributes = new Map([["crossorigin", "anonymous"]]);
    this.src = "";
    this.currentSrc = "";
    this.paused = true;
    this.ended = false;
    this.readyState = 0;
    this.networkState = 0;
    this.error = null;
    this.listeners = new Map();
    this.playCalls = 0;
  }

  get crossOrigin() {
    return this.getAttribute("crossorigin");
  }

  set crossOrigin(value) {
    if (value === null) {
      this.removeAttribute("crossorigin");
    } else {
      this.setAttribute("crossorigin", value);
    }
  }

  getAttribute(name) {
    return this.attributes.get(name) ?? null;
  }

  hasAttribute(name) {
    return this.attributes.has(name);
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }

  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === "src") {
      this.src = "";
      this.currentSrc = "";
    }
  }

  addEventListener(name, callback) {
    const callbacks = this.listeners.get(name) ?? [];
    callbacks.push(callback);
    this.listeners.set(name, callbacks);
  }

  removeEventListener(name, callback) {
    const callbacks = this.listeners.get(name) ?? [];
    this.listeners.set(
      name,
      callbacks.filter((item) => item !== callback)
    );
  }

  dispatch(name) {
    for (const callback of [...(this.listeners.get(name) ?? [])]) {
      callback({ type: name });
    }
  }

  load() {
    this.currentSrc = this.src;
  }

  pause() {
    this.paused = true;
  }

  async play() {
    this.playCalls++;
    assert.equal(
      this.hasAttribute("crossorigin"),
      false,
      "CORS attribute must be absent before playback"
    );
    this.paused = false;
    this.currentSrc = this.src;
    queueMicrotask(() => this.dispatch("playing"));
  }
}

const audioNode = new FakeAudio();
const titleNode = { textContent: "" };

const controller = createPlayerController({
  audioNode,
  playerBar: { dataset: {} },
  titleNode,
  statusNode: { textContent: "" },
  toggleButton: { disabled: false, textContent: "" },
  stopButton: { disabled: false },
  openLink: {
    hidden: true,
    href: "",
    removeAttribute(name) {
      if (name === "href") this.href = "";
    },
  },
  stationUrl: (station) => station.url,
  logPlayerEvent() {},
  mediaSessionController: {
    clearMediaSessionMetadata() {},
    debugSnapshot() { return null; },
    reapplyCurrentMetadata() {},
    setMediaSessionMetadata() {},
    updateMediaSessionState() {},
  },
  recordHistory: async () => {},
  resetRecordedHistory() {},
  windowRef: { addEventListener() {}, setTimeout, clearTimeout },
  documentRef: {
    addEventListener() {},
    visibilityState: "visible",
  },
});

const station = {
  name: "Non-CORS radio",
  url: "https://radio.example/stream",
};

await controller.playStation(station);

assert.equal(controller.debugSnapshot().state, "playing");
assert.equal(audioNode.src, station.url);
assert.equal(audioNode.hasAttribute("crossorigin"), false);
assert.equal(audioNode.title, station.name);
assert.equal(audioNode.getAttribute("aria-label"), station.name);
assert.equal(audioNode.playCalls, 1);

audioNode.setAttribute("crossorigin", "anonymous");

await controller.startCurrentStationPlayback("Retrying stream...");

assert.equal(controller.debugSnapshot().state, "playing");
assert.equal(audioNode.src, station.url);
assert.equal(audioNode.hasAttribute("crossorigin"), false);
assert.equal(audioNode.playCalls, 2);

console.log("direct_audio_cors_regression=PASS");
"""

    result = subprocess.run(
        ["node", "--input-type=module", "-e", script, str(PLAYER)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "direct_audio_cors_regression=PASS" in result.stdout
