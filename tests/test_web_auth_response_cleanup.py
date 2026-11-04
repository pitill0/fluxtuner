"""Regression: unsuccessful auth-state responses must release their bodies."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "fluxtuner/web/static/js/auth.js"


def test_auth_state_401_cleanup_preserves_anonymous_and_authenticated_flow(tmp_path: Path) -> None:
    module = tmp_path / "auth.mjs"
    module.write_text(SOURCE.read_text(encoding="utf-8"), encoding="utf-8")
    script = r"""
const {createAuthController}=await import(process.argv[1]);
const states=[], tokens=[], renders=[];
let cancels=0, ready=0, dashboard=0, resets=0;
const responses=[
  {ok:false,status:401,body:{async cancel(){cancels++;}}},
  {ok:false,status:401,body:{async cancel(){cancels++;throw Error('already closed');}}},
  {ok:false,status:401,body:null},
  {ok:true,async json(){return {user:{username:'alice'},csrf_token:'csrf'};}}
];
globalThis.fetch=async()=>responses.shift();
const controller=createAuthController({
  apiFetch:async()=>{},authMessageNode:null,loginForm:null,
  loadDashboard:async()=>{dashboard++;},
  onAuthReady:async()=>{ready++;},
  publicStatsController:null,
  renderAuthRequired:()=>{},
  resetRadioBrowserView:()=>{resets++;},
  setCsrfToken:(s)=>tokens.push(s),showRecoveryCodes:()=>{},
  setCurrentUser:(u)=>states.push(u?.username??null),
  stopPlayback:()=>{},updateAuthUi:()=>renders.push(true)
});
for(let i=0;i<4;i++)await controller.loadAuthState();
console.log(JSON.stringify({cancels,ready,dashboard,resets,states,tokens,renders:renders.length}));
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
        "cancels": 2,
        "ready": 4,
        "dashboard": 1,
        "resets": 1,
        "states": [None, None, None, "alice"],
        "tokens": ["", "", "", "csrf"],
        "renders": 4,
    }
