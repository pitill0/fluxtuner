"""#334: metadata HTTP errors must release response bodies without changing polling."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fluxtuner/web/static/js/metadata.js"


def test_metadata_http_error_releases_body_and_preserves_polling(tmp_path: Path) -> None:
    module = tmp_path / "metadata.mjs"
    module.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    script = r"""
const {createMetadataController} = await import(process.argv[1]);
const handlers=new Map(), timers=new Map();
let id=1, requests=0, cancels=0, log=[];
const windowRef={
  addEventListener(){},
  setTimeout(fn,delay){ const n=id++;timers.set(n,{fn,delay});return n; },
  clearTimeout(n){timers.delete(n);}
};
const documentRef={
  visibilityState:"visible",
  addEventListener(name,fn){handlers.set(name,fn);}
};
const responses=[];
function errorResponse({reject=false,noBody=false}={}){
  const response={ok:false,status:503};
  if(!noBody) response.body={async cancel(){
    cancels++;
    if(reject) throw Error("Already closed");
  }};
  return response;
}
function goodResponse(){
  return {ok:true,async json(){
    return {status:"fresh",metadata:{title:"Recovered Track"}};
  }};
}
const controller=createMetadataController({
  apiFetch:async()=>{requests++;const result=responses.shift();if(!result)throw Error("Missing response");return result;},
  titleNode:{textContent:""},
  stationNode:{textContent:"",hidden:false},copyButton:null,statusNode:null,
  windowRef,documentRef,navigatorRef:{},
  pollIntervalMs:15000,logPlayerEvent:(name)=>log.push(name)
});
async function settle(){
  for(let i=0;i<25;i++)await Promise.resolve();
  await new Promise(resolve=>setImmediate(resolve));
}
async function nextPoll(){
  const pair=[...timers.entries()].find(([,timer])=>timer.delay===15000);
  if(!pair) throw Error("Expected 15-second retry");
  timers.delete(pair[0]);pair[1].fn();
  await settle();
}
responses.push(errorResponse());
controller.setStation("https://radio.example/live","Station");
controller.updatePlaybackState("playing");
await settle();
const after503={requests,cancels,retryScheduled:[...timers.values()].some(x=>x.delay===15000)};
responses.push(errorResponse({reject:true}));
await nextPoll();
const afterRejectedCancellation={requests,cancels,retryScheduled:[...timers.values()].some(x=>x.delay===15000)};
responses.push(errorResponse({noBody:true}));
await nextPoll();
const afterMissingBody={requests,cancels,retryScheduled:[...timers.values()].some(x=>x.delay===15000)};
responses.push(goodResponse());
await nextPoll();
const afterRecovery={requests,cancels,metadataUpdated:log.includes("metadata-updated")};
documentRef.visibilityState="hidden";
handlers.get("visibilitychange")();
const hiddenTimers=[...timers.values()].filter(x=>x.delay===15000).length;
const beforeStop=requests;
controller.clear();
for(const [key,timer] of [...timers]){timers.delete(key);timer.fn();}
await settle();
console.log(JSON.stringify({after503,afterRejectedCancellation,afterMissingBody,afterRecovery,
  hiddenTimers,stopped:requests===beforeStop}));
"""
    result = subprocess.run(
        ["node", "--input-type=module", "--eval", script, str(module)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    assert json.loads(result.stdout) == {
        "after503": {"requests": 1, "cancels": 1, "retryScheduled": True},
        "afterRejectedCancellation": {"requests": 2, "cancels": 2, "retryScheduled": True},
        "afterMissingBody": {"requests": 3, "cancels": 2, "retryScheduled": True},
        "afterRecovery": {"requests": 4, "cancels": 2, "metadataUpdated": True},
        "hiddenTimers": 0,
        "stopped": True,
    }
