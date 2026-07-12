from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
STATIC_JS_ROOT = REPOSITORY_ROOT / "fluxtuner" / "web" / "static" / "js"


def _run_es_module(tmp_path: Path, module_name: str, script: str) -> dict[str, object]:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required by the Web JavaScript test suite.")

    source_path = STATIC_JS_ROOT / module_name
    module_path = tmp_path / source_path.with_suffix(".mjs").name
    module_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")

    completed = subprocess.run(
        [node, "--input-type=module", "--eval", script, str(module_path)],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    return json.loads(completed.stdout)


def test_player_runtime_delegates_after_single_attachment(tmp_path: Path) -> None:
    result = _run_es_module(
        tmp_path,
        "player-runtime.js",
        r"""
const { createPlayerRuntime } = await import(process.argv[1]);
const runtime = createPlayerRuntime();
const calls = [];

const controller = {
  debugSnapshot(details) {
    calls.push(["debugSnapshot", details]);
    return { attached: true, details };
  },
  getCurrentStation() {
    calls.push(["getCurrentStation"]);
    return { name: "Flux FM" };
  },
  pauseCurrentStationPlayback(message) {
    calls.push(["pause", message]);
    return "paused";
  },
  playStation(station) {
    calls.push(["play", station]);
    return "playing";
  },
  setPlayerState(...args) {
    calls.push(["state", ...args]);
    return "updated";
  },
  startCurrentStationPlayback(message) {
    calls.push(["start", message]);
    return "started";
  },
  stopPlayback(...args) {
    calls.push(["stop", ...args]);
    return "stopped";
  },
};

const attached = runtime.attach(controller);
console.log(JSON.stringify({
  attachedIdentity: attached === controller,
  snapshot: runtime.debugSnapshot({ source: "test" }),
  station: runtime.getCurrentStation(),
  pause: runtime.pauseCurrentStationPlayback("pause message"),
  play: runtime.playStation({ name: "Station" }),
  state: runtime.setPlayerState("playing", "Ready"),
  start: runtime.startCurrentStationPlayback("start message"),
  stop: runtime.stopPlayback("logout"),
  calls,
}));
""",
    )

    assert result["attachedIdentity"] is True
    assert result["snapshot"] == {"attached": True, "details": {"source": "test"}}
    assert result["station"] == {"name": "Flux FM"}
    assert result["pause"] == "paused"
    assert result["play"] == "playing"
    assert result["state"] == "updated"
    assert result["start"] == "started"
    assert result["stop"] == "stopped"
    assert result["calls"] == [
        ["debugSnapshot", {"source": "test"}],
        ["getCurrentStation"],
        ["pause", "pause message"],
        ["play", {"name": "Station"}],
        ["state", "playing", "Ready"],
        ["start", "start message"],
        ["stop", "logout"],
    ]


def test_player_runtime_rejects_invalid_or_repeated_attachment(tmp_path: Path) -> None:
    result = _run_es_module(
        tmp_path,
        "player-runtime.js",
        r"""
const { createPlayerRuntime } = await import(process.argv[1]);

function capture(action) {
  try {
    action();
    return null;
  } catch (error) {
    return { name: error.name, message: error.message };
  }
}

const invalidRuntime = createPlayerRuntime();
const invalid = capture(() => invalidRuntime.attach(null));

const repeatedRuntime = createPlayerRuntime();
repeatedRuntime.attach({});
const repeated = capture(() => repeatedRuntime.attach({}));

console.log(JSON.stringify({ invalid, repeated }));
""",
    )

    assert result["invalid"] == {
        "name": "TypeError",
        "message": "Player runtime requires a controller object.",
    }
    assert result["repeated"] == {
        "name": "Error",
        "message": "Player runtime controller is already attached.",
    }


def test_player_runtime_fails_fast_for_operations_before_attachment(tmp_path: Path) -> None:
    result = _run_es_module(
        tmp_path,
        "player-runtime.js",
        r"""
const { createPlayerRuntime } = await import(process.argv[1]);
const runtime = createPlayerRuntime();

function capture(action) {
  try {
    action();
    return null;
  } catch (error) {
    return { name: error.name, message: error.message };
  }
}

console.log(JSON.stringify({
  snapshot: runtime.debugSnapshot({ source: "early-debug" }),
  station: runtime.getCurrentStation(),
  playError: capture(() => runtime.playStation({ name: "Station" })),
  stopError: capture(() => runtime.stopPlayback()),
}));
""",
    )

    assert result["snapshot"] == {"details": {"source": "early-debug"}}
    assert result["station"] is None
    assert result["playError"] == {
        "name": "Error",
        "message": "Player runtime controller is not attached.",
    }
    assert result["stopError"] == {
        "name": "Error",
        "message": "Player runtime controller is not attached.",
    }


@pytest.mark.parametrize("setup_available", [False, True])
def test_application_bootstrap_executes_runtime_contract(
    tmp_path: Path,
    setup_available: bool,
) -> None:
    result = _run_es_module(
        tmp_path,
        "app-bootstrap.js",
        f"""
const {{ bootstrapApplication }} = await import(process.argv[1]);
const calls = [];

await bootstrapApplication({{
  loadSetupState: async () => calls.push("loadSetupState"),
  playerController: {{
    initialize: () => calls.push("playerController.initialize"),
  }},
  setupController: {{
    isSetupAvailable: () => {{
      calls.push("setupController.isSetupAvailable");
      return {str(setup_available).lower()};
    }},
  }},
  setupMediaSessionHandlers: () => calls.push("setupMediaSessionHandlers"),
  updateAuthUi: () => calls.push("updateAuthUi"),
  updateSetupUi: () => calls.push("updateSetupUi"),
}});

console.log(JSON.stringify({{ calls }}));
""",
    )

    expected = [
        "setupMediaSessionHandlers",
        "playerController.initialize",
        "updateSetupUi",
        "updateAuthUi",
        "loadSetupState",
        "setupController.isSetupAvailable",
    ]
    if setup_available:
        expected.extend(["updateSetupUi", "updateAuthUi"])

    assert result["calls"] == expected


def test_web_player_state_model_enforces_explicit_transitions(tmp_path: Path) -> None:
    result = _run_es_module(
        tmp_path,
        "player.js",
        r"""
const {
  PLAYER_STATES,
  PLAYER_STATE_TRANSITIONS,
  createPlayerStateModel,
} = await import(process.argv[1]);

function capture(action) {
  try {
    action();
    return null;
  } catch (error) {
    return { name: error.name, message: error.message };
  }
}

const model = createPlayerStateModel();
const transitions = [
  model.transition("loading"),
  model.transition("playing"),
  model.transition("paused"),
  model.transition("loading"),
  model.transition("error"),
  model.transition("idle"),
];

const invalidState = capture(() => model.transition("buffering"));
const invalidTransitionModel = createPlayerStateModel();
const invalidTransition = capture(() => invalidTransitionModel.transition("paused"));

console.log(JSON.stringify({
  states: PLAYER_STATES,
  transitionKeys: Object.keys(PLAYER_STATE_TRANSITIONS),
  transitions,
  finalState: model.current,
  invalidState,
  invalidTransition,
  invalidTransitionState: invalidTransitionModel.current,
}));
""",
    )

    assert result["states"] == ["idle", "loading", "playing", "paused", "error"]
    assert result["transitionKeys"] == ["idle", "loading", "playing", "paused", "error"]
    assert result["transitions"] == [
        {"previousState": "idle", "state": "loading"},
        {"previousState": "loading", "state": "playing"},
        {"previousState": "playing", "state": "paused"},
        {"previousState": "paused", "state": "loading"},
        {"previousState": "loading", "state": "error"},
        {"previousState": "error", "state": "idle"},
    ]
    assert result["finalState"] == "idle"
    assert result["invalidState"] == {
        "name": "TypeError",
        "message": "Unknown player state: buffering",
    }
    assert result["invalidTransition"] == {
        "name": "Error",
        "message": "Invalid player state transition: idle -> paused",
    }
    assert result["invalidTransitionState"] == "idle"


def test_web_player_controller_projects_internal_state_to_dom(tmp_path: Path) -> None:
    result = _run_es_module(
        tmp_path,
        "player.js",
        r"""
const { createPlayerController } = await import(process.argv[1]);

const playerBar = { dataset: {} };
const statusNode = { textContent: "" };
const mediaUpdates = [];

const controller = createPlayerController({
  audioNode: null,
  playerBar,
  titleNode: null,
  statusNode,
  toggleButton: null,
  stopButton: null,
  openLink: null,
  stationUrl: () => "",
  logPlayerEvent: () => {},
  mediaSessionController: {
    debugSnapshot() {
      return null;
    },
    updateMediaSessionState(state, reason) {
      mediaUpdates.push([state, reason]);
    },
  },
  recordHistory: async () => {},
  resetRecordedHistory: () => {},
  windowRef: {
    addEventListener() {},
    clearTimeout() {},
    setTimeout() {
      return 0;
    },
  },
  documentRef: {
    addEventListener() {},
    visibilityState: "visible",
  },
});

const initial = controller.debugSnapshot();
const loading = controller.setPlayerState("loading", "Loading stream...", "test-loading");
const loadingSnapshot = controller.debugSnapshot();
const error = controller.setPlayerState("error", "Failed.", "test-error");

console.log(JSON.stringify({
  initial,
  loading,
  loadingSnapshot,
  error,
  domState: playerBar.dataset.state,
  status: statusNode.textContent,
  mediaUpdates,
}));
""",
    )

    assert result["initial"]["state"] == "idle"
    assert result["loading"] == {"previousState": "idle", "state": "loading"}
    assert result["loadingSnapshot"]["state"] == "loading"
    assert result["error"] == {"previousState": "loading", "state": "error"}
    assert result["domState"] == "error"
    assert result["status"] == "Failed."
    assert result["mediaUpdates"] == [
        ["loading", "test-loading"],
        ["error", "test-error"],
    ]


def test_web_player_controller_confirms_current_playback_attempt(tmp_path: Path) -> None:
    result = _run_es_module(
        tmp_path,
        "player.js",
        r"""
const { createPlayerController } = await import(process.argv[1]);

class FakeEventTarget {
  constructor() { this.listeners = new Map(); }
  addEventListener(name, callback, options = {}) {
    const entries = this.listeners.get(name) || [];
    entries.push({ callback, once: Boolean(options?.once) });
    this.listeners.set(name, entries);
  }
  removeEventListener(name, callback) {
    const entries = this.listeners.get(name) || [];
    this.listeners.set(name, entries.filter((entry) => entry.callback !== callback));
  }
  dispatch(name) {
    const entries = [...(this.listeners.get(name) || [])];
    for (const entry of entries) {
      entry.callback({ type: name });
      if (entry.once) this.removeEventListener(name, entry.callback);
    }
  }
}

class FakeAudio extends FakeEventTarget {
  constructor() {
    super();
    this.attributes = new Map();
    this.paused = true;
    this.ended = false;
    this.readyState = 0;
    this.networkState = 0;
    this.currentSrc = "";
    this.src = "";
    this.crossOrigin = "";
    this.title = "";
    this.controls = false;
    this.preload = "";
    this.error = null;
  }
  getAttribute(name) { return this.attributes.get(name) || ""; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === "src") { this.src = ""; this.currentSrc = ""; }
  }
  load() { this.currentSrc = this.src; }
  pause() { this.paused = true; }
  async play() {
    this.paused = false;
    this.currentSrc = this.src;
    queueMicrotask(() => this.dispatch("playing"));
  }
}

const audioNode = new FakeAudio();
const playerBar = { dataset: {} };
const titleNode = { textContent: "" };
const statusNode = { textContent: "" };
const toggleButton = { disabled: false, textContent: "" };
const stopButton = { disabled: false };
const openLink = {
  hidden: true,
  href: "",
  removeAttribute(name) { if (name === "href") this.href = ""; },
};
const history = [];
const mediaUpdates = [];

const controller = createPlayerController({
  audioNode,
  playerBar,
  titleNode,
  statusNode,
  toggleButton,
  stopButton,
  openLink,
  stationUrl: (station) => station.url,
  logPlayerEvent: () => {},
  mediaSessionController: {
    clearMediaSessionMetadata() {},
    debugSnapshot() { return null; },
    reapplyCurrentMetadata() {},
    setMediaSessionMetadata() {},
    updateMediaSessionState(state, reason) { mediaUpdates.push([state, reason]); },
  },
  async recordHistory(station) { history.push(station.name); },
  resetRecordedHistory() {},
  windowRef: { addEventListener() {}, clearTimeout, setTimeout },
  documentRef: { addEventListener() {}, visibilityState: "visible" },
});

await controller.playStation({ name: "Flux FM", url: "https://radio.example/stream" });

console.log(JSON.stringify({
  state: playerBar.dataset.state,
  status: statusNode.textContent,
  title: titleNode.textContent,
  station: controller.getCurrentStation(),
  src: audioNode.src,
  paused: audioNode.paused,
  history,
  mediaUpdates,
  controls: {
    toggleDisabled: toggleButton.disabled,
    toggleText: toggleButton.textContent,
    stopDisabled: stopButton.disabled,
  },
}));
""",
    )

    assert result["state"] == "playing"
    assert result["status"] == "Playing in browser."
    assert result["title"] == "Flux FM"
    assert result["station"] == {"name": "Flux FM", "url": "https://radio.example/stream"}
    assert result["src"] == "https://radio.example/stream"
    assert result["paused"] is False
    assert result["history"] == ["Flux FM"]
    assert result["mediaUpdates"][-1] == ["playing", "playback-started"]
    assert result["controls"] == {
        "toggleDisabled": False,
        "toggleText": "Pause",
        "stopDisabled": False,
    }


def test_web_player_controller_replaces_or_stops_pending_attempts(tmp_path: Path) -> None:
    result = _run_es_module(
        tmp_path,
        "player.js",
        r"""
const { createPlayerController } = await import(process.argv[1]);

class FakeEventTarget {
  constructor() { this.listeners = new Map(); }
  addEventListener(name, callback, options = {}) {
    const entries = this.listeners.get(name) || [];
    entries.push({ callback, once: Boolean(options?.once) });
    this.listeners.set(name, entries);
  }
  removeEventListener(name, callback) {
    const entries = this.listeners.get(name) || [];
    this.listeners.set(name, entries.filter((entry) => entry.callback !== callback));
  }
  dispatch(name) {
    const entries = [...(this.listeners.get(name) || [])];
    for (const entry of entries) {
      entry.callback({ type: name });
      if (entry.once) this.removeEventListener(name, entry.callback);
    }
  }
}

class ControlledAudio extends FakeEventTarget {
  constructor() {
    super();
    this.attributes = new Map();
    this.paused = true;
    this.ended = false;
    this.readyState = 0;
    this.networkState = 0;
    this.currentSrc = "";
    this.src = "";
    this.crossOrigin = "";
    this.title = "";
    this.controls = false;
    this.preload = "";
    this.error = null;
    this.playResolvers = [];
  }
  getAttribute(name) { return this.attributes.get(name) || ""; }
  setAttribute(name, value) { this.attributes.set(name, String(value)); }
  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === "src") { this.src = ""; this.currentSrc = ""; }
  }
  load() { this.currentSrc = this.src; }
  pause() { this.paused = true; }
  play() {
    this.paused = false;
    this.currentSrc = this.src;
    return Promise.resolve();
  }
  resolveLatestPlay() {
    const resolve = this.playResolvers.at(-1);
    if (resolve) resolve();
  }
}

function createController(audioNode, history) {
  const playerBar = { dataset: {} };
  const titleNode = { textContent: "" };
  const statusNode = { textContent: "" };
  const toggleButton = { disabled: false, textContent: "" };
  const stopButton = { disabled: false };
  const openLink = {
    hidden: true,
    href: "",
    removeAttribute(name) { if (name === "href") this.href = ""; },
  };
  const controller = createPlayerController({
    audioNode,
    playerBar,
    titleNode,
    statusNode,
    toggleButton,
    stopButton,
    openLink,
    stationUrl: (station) => station.url,
    logPlayerEvent: () => {},
    mediaSessionController: {
      clearMediaSessionMetadata() {},
      debugSnapshot() { return null; },
      reapplyCurrentMetadata() {},
      setMediaSessionMetadata() {},
      updateMediaSessionState() {},
    },
    async recordHistory(station) { history.push(station.name); },
    resetRecordedHistory() {},
    windowRef: { addEventListener() {}, clearTimeout, setTimeout },
    documentRef: { addEventListener() {}, visibilityState: "visible" },
  });
  return { controller, playerBar, titleNode, statusNode, openLink };
}

const replacementAudio = new ControlledAudio();
const replacementHistory = [];
const replacement = createController(replacementAudio, replacementHistory);
const first = replacement.controller.playStation({ name: "Station A", url: "https://radio.example/a" });
await Promise.resolve();
const second = replacement.controller.playStation({ name: "Station B", url: "https://radio.example/b" });
await Promise.resolve();
replacementAudio.dispatch("playing");
await Promise.all([first, second]);

const stoppedAudio = new ControlledAudio();
const stoppedHistory = [];
const stopped = createController(stoppedAudio, stoppedHistory);
const pending = stopped.controller.playStation({ name: "Station C", url: "https://radio.example/c" });
await Promise.resolve();
stopped.controller.stopPlayback();
stoppedAudio.dispatch("playing");
await pending;

console.log(JSON.stringify({
  replacement: {
    state: replacement.playerBar.dataset.state,
    station: replacement.controller.getCurrentStation(),
    title: replacement.titleNode.textContent,
    src: replacementAudio.src,
    history: replacementHistory,
  },
  stopped: {
    state: stopped.playerBar.dataset.state,
    station: stopped.controller.getCurrentStation(),
    title: stopped.titleNode.textContent,
    status: stopped.statusNode.textContent,
    src: stoppedAudio.src,
    paused: stoppedAudio.paused,
    openHidden: stopped.openLink.hidden,
    history: stoppedHistory,
  },
}));
""",
    )

    assert result["replacement"] == {
        "state": "playing",
        "station": {"name": "Station B", "url": "https://radio.example/b"},
        "title": "Station B",
        "src": "https://radio.example/b",
        "history": ["Station B"],
    }
    assert result["stopped"] == {
        "state": "idle",
        "station": None,
        "title": "Nothing playing yet",
        "status": "Idle",
        "src": "",
        "paused": True,
        "openHidden": True,
        "history": [],
    }


def test_web_player_pause_invalidates_pending_attempt_and_ignores_late_playing(
    tmp_path: Path,
) -> None:
    result = _run_es_module(
        tmp_path,
        "player.js",
        r"""
const { createPlayerController } = await import(process.argv[1]);

class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(name, callback, options = {}) {
    const entries = this.listeners.get(name) || [];
    entries.push({ callback, once: Boolean(options?.once) });
    this.listeners.set(name, entries);
  }

  removeEventListener(name, callback) {
    const entries = this.listeners.get(name) || [];
    this.listeners.set(
      name,
      entries.filter((entry) => entry.callback !== callback),
    );
  }

  dispatch(name) {
    const entries = [...(this.listeners.get(name) || [])];
    for (const entry of entries) {
      entry.callback({ type: name });
      if (entry.once) {
        this.removeEventListener(name, entry.callback);
      }
    }
  }
}

const audioNode = new FakeEventTarget();
Object.assign(audioNode, {
  attributes: new Map(),
  paused: true,
  ended: false,
  readyState: 0,
  networkState: 0,
  currentSrc: "",
  src: "",
  crossOrigin: "",
  title: "",
  controls: false,
  preload: "",
  error: null,
  getAttribute(name) {
    return this.attributes.get(name) || "";
  },
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  },
  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === "src") {
      this.src = "";
      this.currentSrc = "";
    }
  },
  load() {
    this.currentSrc = this.src;
  },
  pause() {
    this.paused = true;
  },
  async play() {
    this.paused = false;
    this.currentSrc = this.src;
  },
});

const playerBar = { dataset: {} };
const titleNode = { textContent: "" };
const statusNode = { textContent: "" };
const history = [];
const events = [];

const controller = createPlayerController({
  audioNode,
  playerBar,
  titleNode,
  statusNode,
  toggleButton: {
    disabled: false,
    textContent: "",
    addEventListener() {},
  },
  stopButton: {
    disabled: false,
    addEventListener() {},
  },
  openLink: {
    hidden: true,
    href: "",
    removeAttribute(name) {
      if (name === "href") {
        this.href = "";
      }
    },
  },
  stationUrl: (station) => station.url,
  logPlayerEvent(eventName, details = {}) {
    events.push([eventName, details]);
  },
  mediaSessionController: {
    clearMediaSessionMetadata() {},
    debugSnapshot() {
      return null;
    },
    reapplyCurrentMetadata() {},
    setMediaSessionMetadata() {},
    updateMediaSessionState() {},
  },
  async recordHistory(station) {
    history.push(station.name);
  },
  resetRecordedHistory() {},
  windowRef: {
    addEventListener() {},
    clearTimeout,
    setTimeout,
  },
  documentRef: {
    addEventListener() {},
    visibilityState: "visible",
  },
});

controller.initialize();

const pending = controller.playStation({
  name: "Flux FM",
  url: "https://radio.example/stream",
});
await Promise.resolve();

const loadingSnapshot = controller.debugSnapshot();
controller.pauseCurrentStationPlayback("Paused from system controls.");
const pausedSnapshot = controller.debugSnapshot();

audioNode.dispatch("playing");
await pending;
audioNode.dispatch("playing");

const finalSnapshot = controller.debugSnapshot();

console.log(JSON.stringify({
  loadingSnapshot,
  pausedSnapshot,
  finalSnapshot,
  state: playerBar.dataset.state,
  status: statusNode.textContent,
  paused: audioNode.paused,
  history,
  playerStateEvents: events
    .filter(([name]) => name === "player-state")
    .map(([, details]) => details.state),
}));
""",
    )

    assert result["loadingSnapshot"]["state"] == "loading"
    assert result["loadingSnapshot"]["flags"]["startingPlayback"] is True
    assert result["loadingSnapshot"]["playbackRunId"] == 1

    assert result["pausedSnapshot"]["state"] == "paused"
    assert result["pausedSnapshot"]["flags"]["startingPlayback"] is False
    assert result["pausedSnapshot"]["playbackRunId"] == 2

    assert result["finalSnapshot"]["state"] == "paused"
    assert result["finalSnapshot"]["flags"]["startingPlayback"] is False
    assert result["finalSnapshot"]["playbackRunId"] == 2
    assert result["state"] == "paused"
    assert result["status"] == "Paused from system controls."
    assert result["paused"] is True
    assert result["history"] == []
    assert result["playerStateEvents"] == ["loading", "paused"]


def test_web_player_controller_exposes_lifecycle_state_changes(tmp_path: Path) -> None:
    result = _run_es_module(
        tmp_path,
        "player.js",
        r"""
const { createPlayerController } = await import(process.argv[1]);

class FakeEventTarget {
  constructor() {
    this.listeners = new Map();
  }

  addEventListener(name, callback) {
    const entries = this.listeners.get(name) || [];
    entries.push(callback);
    this.listeners.set(name, entries);
  }

  removeEventListener(name, callback) {
    const entries = this.listeners.get(name) || [];
    this.listeners.set(
      name,
      entries.filter((entry) => entry !== callback),
    );
  }

  dispatch(name) {
    for (const callback of [...(this.listeners.get(name) || [])]) {
      callback({ type: name });
    }
  }
}

const audioNode = new FakeEventTarget();
Object.assign(audioNode, {
  paused: true,
  ended: false,
  readyState: 0,
  networkState: 0,
  currentSrc: "",
  src: "",
  crossOrigin: "",
  title: "",
  controls: false,
  preload: "",
  error: null,
  attributes: new Map(),
  getAttribute(name) {
    return this.attributes.get(name) || "";
  },
  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  },
  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === "src") {
      this.src = "";
      this.currentSrc = "";
    }
  },
  load() {
    this.currentSrc = this.src;
  },
  pause() {
    this.paused = true;
  },
  async play() {
    this.paused = false;
    this.currentSrc = this.src;
    queueMicrotask(() => this.dispatch("playing"));
  },
});

const windowRef = new FakeEventTarget();
windowRef.setTimeout = setTimeout;
windowRef.clearTimeout = clearTimeout;

const documentRef = new FakeEventTarget();
documentRef.visibilityState = "visible";

const playerBar = { dataset: {} };
const titleNode = { textContent: "" };
const statusNode = { textContent: "" };
const events = [];
const mediaUpdates = [];

const controller = createPlayerController({
  audioNode,
  playerBar,
  titleNode,
  statusNode,
  toggleButton: {
    disabled: false,
    textContent: "",
    addEventListener() {},
  },
  stopButton: {
    disabled: false,
    addEventListener() {},
  },
  openLink: {
    hidden: true,
    href: "",
    removeAttribute(name) {
      if (name === "href") {
        this.href = "";
      }
    },
  },
  stationUrl: (station) => station.url,
  logPlayerEvent(eventName, details = {}) {
    events.push([eventName, details]);
  },
  mediaSessionController: {
    clearMediaSessionMetadata() {},
    debugSnapshot() {
      return null;
    },
    reapplyCurrentMetadata(reason) {
      mediaUpdates.push(["metadata", reason]);
    },
    setMediaSessionMetadata() {},
    updateMediaSessionState(state, reason) {
      mediaUpdates.push(["state", state, reason]);
    },
  },
  async recordHistory() {},
  resetRecordedHistory() {},
  windowRef,
  documentRef,
});

controller.initialize();
await controller.playStation({
  name: "Flux FM",
  url: "https://radio.example/stream",
});

windowRef.dispatch("offline");
const offline = {
  state: playerBar.dataset.state,
  status: statusNode.textContent,
};

windowRef.dispatch("online");
windowRef.dispatch("pagehide");
windowRef.dispatch("pageshow");

documentRef.visibilityState = "hidden";
documentRef.dispatch("visibilitychange");
documentRef.visibilityState = "visible";
documentRef.dispatch("visibilitychange");

console.log(JSON.stringify({
  offline,
  eventNames: events.map(([name]) => name),
  mediaUpdates,
}));
""",
    )

    assert result["offline"] == {
        "state": "error",
        "status": "Browser is offline. Playback may resume when network returns.",
    }

    for event_name in [
        "window-offline",
        "window-online",
        "window-pagehide",
        "window-pageshow",
        "document-visibilitychange",
    ]:
        assert event_name in result["eventNames"]

    assert result["eventNames"].count("document-visibilitychange") == 2
    assert ["metadata", "window-online"] in result["mediaUpdates"]
    assert ["metadata", "window-pagehide"] in result["mediaUpdates"]
    assert ["metadata", "window-pageshow"] in result["mediaUpdates"]
    assert ["metadata", "document-hidden"] in result["mediaUpdates"]
    assert ["metadata", "document-visible"] in result["mediaUpdates"]
    assert ["state", "error", "window-pagehide"] in result["mediaUpdates"]
    assert ["state", "error", "document-hidden"] in result["mediaUpdates"]
    assert ["state", "error", "document-visible"] in result["mediaUpdates"]


def test_web_media_session_handlers_delegate_player_intentions(tmp_path: Path) -> None:
    result = _run_es_module(
        tmp_path,
        "media-session.js",
        r"""
const handlers = new Map();
const calls = [];
const station = { name: "Flux FM", url: "https://radio.example/stream" };

globalThis.window = { location: { href: "https://fluxtuner.example/" } };
Object.defineProperty(globalThis, "navigator", {
  configurable: true,
  value: {
    mediaSession: {
      metadata: null,
      playbackState: "none",
      setActionHandler(name, callback) { handlers.set(name, callback); },
    },
  },
});
globalThis.MediaMetadata = class { constructor(payload) { Object.assign(this, payload); } };
window.MediaMetadata = globalThis.MediaMetadata;

const { createMediaSessionController } = await import(process.argv[1]);
const controller = createMediaSessionController({
  getCurrentStation: () => station,
  logPlayerEvent: (eventName, details = {}) => calls.push(["event", eventName, details]),
  pauseCurrentStationPlayback: (message) => calls.push(["pause", message ?? null]),
  startCurrentStationPlayback: (message) => calls.push(["start", message]),
  stopPlayback: () => calls.push(["stop"]),
});

controller.setupMediaSessionHandlers();
handlers.get("play")();
handlers.get("pause")();
handlers.get("stop")();

console.log(JSON.stringify({
  handlerNames: [...handlers.keys()],
  calls: calls.map((entry) => entry.slice(0, 2)),
  playbackState: navigator.mediaSession.playbackState,
  metadataTitle: navigator.mediaSession.metadata?.title || "",
}));
""",
    )

    assert result["handlerNames"] == ["play", "pause", "stop"]
    assert result["calls"] == [
        ["event", "media-session-play"],
        ["event", "media-session-metadata"],
        ["start", "Starting stream from system controls..."],
        ["event", "media-session-pause"],
        ["event", "media-session-metadata"],
        ["pause", None],
        ["event", "media-session-stop"],
        ["stop"],
    ]
    assert result["playbackState"] == "none"
    assert result["metadataTitle"] == "Flux FM"
