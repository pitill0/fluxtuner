# SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
"""Executable metadata recovery regression for #314."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_metadata_failure_recovery_and_station_switch(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "fluxtuner/web/static/js/metadata.js"
    module = tmp_path / "metadata.mjs"
    module.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    script = r"""
const { createMetadataController } = await import(process.argv[1]);

const timers = new Map();
let nextTimer = 1;
const windowRef = {
  addEventListener() {},
  setTimeout(callback, delay) {
    const id = nextTimer++;
    timers.set(id, { callback, delay });
    return id;
  },
  clearTimeout(id) { timers.delete(id); },
};

const documentRef = {
  visibilityState: "visible",
  addEventListener() {},
};

const titleNode = { textContent: "" };
const stationNode = { textContent: "", hidden: true };
const calls = [];
const responses = [];
const pending = [];
let holdNext = false;

const apiFetch = (url) => {
  calls.push(url);
  if (holdNext) {
    holdNext = false;
    return new Promise((resolve) => pending.push(resolve));
  }
  const item = responses.shift();
  if (item instanceof Error) return Promise.reject(item);
  return Promise.resolve(item);
};

const controller = createMetadataController({
  apiFetch,
  titleNode,
  stationNode,
  copyButton: null,
  statusNode: null,
  windowRef,
  documentRef,
  navigatorRef: {},
  pollIntervalMs: 15000,
});

async function settle() {
  for (let i = 0; i < 15; i++) await Promise.resolve();
  await new Promise((resolve) => setImmediate(resolve));
}

async function pollAgain() {
  const timer = [...timers.entries()].find(([, item]) => item.delay === 15000);
  if (!timer) throw new Error("Missing scheduled 15-second retry");
  timers.delete(timer[0]);
  timer[1].callback();
  await settle();
}

responses.push({ ok: false, status: 503 });
controller.setStation("https://example.org/a", "Station A");
controller.updatePlaybackState("playing");
await settle();
const afterHttpError = titleNode.textContent;
const retryScheduled = [...timers.values()].some((item) => item.delay === 15000);

responses.push({
  ok: true,
  async json() {
    return { status: "fresh", metadata: { title: "Track A" } };
  },
});
await pollAgain();
const afterRecovery = titleNode.textContent;

responses.push(new Error("Network unavailable"));
await pollAgain();
const afterNetworkError = titleNode.textContent;

holdNext = true;
await pollAgain();
controller.setStation("https://example.org/b", "Station B");
controller.updatePlaybackState("playing");
pending.shift()({
  ok: true,
  async json() {
    return { status: "fresh", metadata: { title: "Stale Track A" } };
  },
});
responses.push({
  ok: true,
  async json() {
    return { status: "fresh", metadata: { title: "Track B" } };
  },
});
await settle();
const afterStationSwitch = titleNode.textContent;

controller.clear();
const callsBeforeStop = calls.length;
for (const [id, item] of [...timers]) {
  timers.delete(id);
  item.callback();
}
await settle();

console.log(JSON.stringify({
  afterHttpError,
  retryScheduled,
  afterRecovery,
  afterNetworkError,
  afterStationSwitch,
  stopped: calls.length === callsBeforeStop,
}));
"""

    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script, str(module)],
        check=True,
        capture_output=True,
        text=True,
        timeout=20,
    )
    result = json.loads(completed.stdout)

    assert result == {
        "afterHttpError": "Retrying track info…",
        "retryScheduled": True,
        "afterRecovery": "Track A",
        "afterNetworkError": "Track A",
        "afterStationSwitch": "Track B",
        "stopped": True,
    }
