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
