"""#311: optional browser AudioSession category is feature-gated and best effort."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / "fluxtuner/web/static/js/player.js"


def test_audio_session_preference_is_feature_gated(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for Web player regression tests")
    module = tmp_path / "player.mjs"
    module.write_text(PLAYER.read_text(encoding="utf-8"), encoding="utf-8")
    script = r"""
const { configureBrowserAudioSession } = await import(process.argv[1]);
const unsupported = configureBrowserAudioSession({});
const audio = { type: 'auto' };
const configured = configureBrowserAudioSession({audioSession: audio});
const already = configureBrowserAudioSession({audioSession: audio});
const rejected = configureBrowserAudioSession({audioSession: {
  set type(value) { throw new Error('not supported'); }, get type() { return 'auto'; }
}});
const ignored = configureBrowserAudioSession({audioSession: {
  set type(value) {}, get type() { return 'auto'; }
}});
console.log(JSON.stringify({unsupported, configured, already, rejected, ignored, final:audio.type}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script, str(module)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout) == {
        "unsupported": "unsupported",
        "configured": "configured",
        "already": "configured",
        "rejected": "error",
        "ignored": "ignored",
        "final": "playback",
    }


def test_audio_session_category_is_configured_before_playback() -> None:
    source = PLAYER.read_text(encoding="utf-8")
    attempt = source.split("async function attemptCurrentStationPlayback", 1)[1].split(
        "async function startCurrentStationPlayback", 1
    )[0]
    assert attempt.index("configureBrowserAudioSession()") < attempt.index("await audioNode.play()")
    pause = source.split("function pauseCurrentStationPlayback", 1)[1].split(
        "async function playStation", 1
    )[0]
    assert "clearAudioSource();" in pause
    assert "configureBrowserAudioSession" not in pause
