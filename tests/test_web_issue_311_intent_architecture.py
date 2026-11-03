"""#311: intent remains independent from audio teardown and lifecycle events."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAYER = ROOT / "fluxtuner/web/static/js/player.js"


def test_intent_survives_teardown_and_lifecycle_and_explicit_resume(tmp_path: Path) -> None:
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
const initial=c.debugSnapshot();
c.pauseCurrentStationPlayback();
const pause=c.debugSnapshot();
const pausedLoads=audioNode.loads, pausedPlays=audioNode.plays;
// iOS may dispatch these asynchronously after source removal.
audioNode.dispatch("playing"); audioNode.dispatch("waiting"); audioNode.dispatch("error");
doc.visibilityState="hidden";doc.dispatch("visibilitychange");
win.dispatch("online");
await new Promise(resolve=>setTimeout(resolve,1));
const afterLate=c.debugSnapshot();
const noAutoResume=pausedPlays===audioNode.plays;
const released=audioNode.src==="" && audioNode.paused;
const metadataKept=Boolean(c.getCurrentStation());
await c.startCurrentStationPlayback("Resume");
const resumed=c.debugSnapshot();
c.stopPlayback();
const stopped=c.debugSnapshot();
console.log(JSON.stringify({initial:initial.playbackIntent,pause:pause.playbackIntent,
  afterLate:afterLate.playbackIntent,afterLateState:afterLate.state,
  resumed:resumed.playbackIntent,resumedState:resumed.state,
  stopped:stopped.playbackIntent,stoppedState:stopped.state,
  noAutoResume,released,metadataKept,pausedLoads,history}));
"""
    result = subprocess.run(
        [node, "--input-type=module", "--eval", script, str(module)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    actual = json.loads(result.stdout)
    assert actual["initial"] == "playing"
    assert actual["pause"] == "paused"
    assert actual["afterLate"] == "paused"
    assert actual["afterLateState"] == "paused"
    assert actual["noAutoResume"] is True
    assert actual["released"] is True
    assert actual["metadataKept"] is True
    assert actual["resumed"] == "playing"
    assert actual["resumedState"] == "playing"
    assert actual["stopped"] == "stopped"
    assert actual["stoppedState"] == "idle"
