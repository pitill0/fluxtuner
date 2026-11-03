"""#330: external audio resume must reconcile playback intent without restarting a live stream."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / "fluxtuner/web/static/js/player.js"


def test_external_audio_resume_reconciles_intent_without_restarting(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.fail("Node.js is required for Web player regression tests")
    module = tmp_path / "player.mjs"
    module.write_text(PLAYER.read_text(encoding="utf-8"), encoding="utf-8")
    script = r"""
const { createPlayerController } = await import(process.argv[1]);
class Target {
  constructor() { this.listeners = new Map(); }
  addEventListener(name, cb, options = {}) {
    const list = this.listeners.get(name) || [];
    list.push({cb,once:Boolean(options?.once)}); this.listeners.set(name,list);
  }
  removeEventListener(name, cb) {
    this.listeners.set(name, (this.listeners.get(name)||[]).filter(e=>e.cb!==cb));
  }
  dispatch(name) {
    for (const e of [...(this.listeners.get(name)||[])]) {
      e.cb({type:name}); if(e.once) this.removeEventListener(name,e.cb);
    }
  }
}
class Audio extends Target {
  constructor() {
    super(); this.attributes=new Map(); this.paused=true; this.ended=false;
    this.readyState=0; this.networkState=0; this.currentSrc=""; this.src="";
    this.crossOrigin=""; this.title=""; this.controls=false; this.preload="";
    this.error=null; this.loads=0; this.plays=0;
  }
  getAttribute(n) { return this.attributes.get(n)||""; }
  setAttribute(n,v) { this.attributes.set(n,String(v)); }
  removeAttribute(n) {
    this.attributes.delete(n); if(n==="src") { this.src=""; this.currentSrc=""; }
  }
  load() { this.loads++; this.currentSrc=this.src; }
  pause() { this.paused=true; }
  async play() {
    this.plays++; this.paused=false; this.currentSrc=this.src;
    queueMicrotask(()=>this.dispatch("playing"));
  }
}
const audioNode=new Audio(), win=new Target(), doc=new Target();
doc.visibilityState="visible";
win.setTimeout=setTimeout; win.clearTimeout=clearTimeout;
const state={dataset:{}}, history=[];
const c=createPlayerController({
  audioNode, playerBar:state, titleNode:{textContent:""},
  statusNode:{textContent:""},
  toggleButton:{disabled:false,textContent:"",addEventListener(){}},
  stopButton:{disabled:false,addEventListener(){}},
  openLink:{hidden:true,href:"",removeAttribute(){}},
  stationUrl:s=>s.url, logPlayerEvent(){},
  mediaSessionController:{
    clearMediaSessionMetadata(){},debugSnapshot(){return null;},
    reapplyCurrentMetadata(){},setMediaSessionMetadata(){},updateMediaSessionState(){}
  },
  recordHistory:async s=>history.push(s.name),resetRecordedHistory(){},
  windowRef:win,documentRef:doc,
});
c.initialize();
await c.playStation({name:"Test",url:"https://radio.example/live"});
const initial={loads:audioNode.loads,plays:audioNode.plays,history:history.length};
// The platform pauses the HTMLAudioElement without invoking our explicit Pause.
audioNode.paused=true; audioNode.dispatch("pause");
const externalPause=c.debugSnapshot();
const retainedSource=Boolean(audioNode.src || audioNode.currentSrc);
// The platform resumes the retained source without a FluxTuner start request.
audioNode.paused=false; audioNode.dispatch("play"); audioNode.dispatch("playing");
const externalResume=c.debugSnapshot();
const noRestartOnExternalResume=audioNode.loads===initial.loads && audioNode.plays===initial.plays;
await c.togglePlayback();
const toggled=c.debugSnapshot();
const noRestartOnToggle=audioNode.plays===initial.plays;
const explicitPauseReleased=!audioNode.src && !audioNode.currentSrc && audioNode.paused;
// A stale play event after explicit source teardown must not resurrect playback.
audioNode.paused=false; audioNode.dispatch("play"); audioNode.dispatch("playing");
const afterLate=c.debugSnapshot();
const lateNoRestart=audioNode.plays===initial.plays;
c.stopPlayback();
audioNode.paused=false; audioNode.dispatch("play"); audioNode.dispatch("playing");
const afterStop=c.debugSnapshot();
console.log(JSON.stringify({
  externalPauseIntent:externalPause.playbackIntent,
  retainedSource,externalResumeIntent:externalResume.playbackIntent,
  externalResumeState:externalResume.state,noRestartOnExternalResume,
  toggleIntent:toggled.playbackIntent,toggleState:toggled.state,
  noRestartOnToggle,explicitPauseReleased,
  afterLateIntent:afterLate.playbackIntent,afterLateState:afterLate.state,lateNoRestart,
  afterStopIntent:afterStop.playbackIntent,afterStopState:afterStop.state,
  historyUnchanged:history.length===initial.history,
}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script, str(module)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    actual = json.loads(result.stdout)
    assert actual == {
        "externalPauseIntent": "paused",
        "retainedSource": True,
        "externalResumeIntent": "playing",
        "externalResumeState": "playing",
        "noRestartOnExternalResume": True,
        "toggleIntent": "paused",
        "toggleState": "paused",
        "noRestartOnToggle": True,
        "explicitPauseReleased": True,
        "afterLateIntent": "paused",
        "afterLateState": "paused",
        "lateNoRestart": True,
        "afterStopIntent": "stopped",
        "afterStopState": "idle",
        "historyUnchanged": True,
    }
