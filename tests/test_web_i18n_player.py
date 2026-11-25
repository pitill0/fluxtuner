"""Locale changes must never replay player operations or metadata polling."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_playback_metadata_and_feedback_survive_locale_switch(tmp_path):
    node = shutil.which("node")
    assert node is not None
    shutil.copytree(STATIC / "js", tmp_path / "js")
    shutil.copytree(STATIC / "locales", tmp_path / "locales")
    (tmp_path / "package.json").write_text('{"type":"module"}', encoding="utf-8")
    script = r"""
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {pathToFileURL} from 'node:url';
const base = pathToFileURL(process.argv[1] + '/');
const {createPlayerController} = await import(new URL('js/player.js', base));
const {createMetadataController} = await import(new URL('js/metadata.js', base));
const {createFavoriteController} = await import(new URL('js/favorites.js', base));
const {createPlaylistController} = await import(new URL('js/playlists.js', base));
const {createI18n} = await import(new URL('js/i18n.js', base));
const {createDynamicPresentation} = await import(new URL('js/i18n-presentation.js', base));
const i18n = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
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
    // The test completes playback explicitly after changing language.
  }
}

function element(text = '') {
  const target = new Target(), attrs = new Map();
  return Object.assign(target, {textContent:text,dataset:{},hidden:false,
    style:{removeProperty(){},setProperty(){}},scrollWidth:100,clientWidth:100,
    getAttribute:k=>attrs.get(k),setAttribute:(k,v)=>attrs.set(k,v),
    removeAttribute:k=>attrs.delete(k),querySelector:()=>null});
}
const audioNode = new Audio(), win = new Target(), doc = new Target();
doc.visibilityState = 'visible';
let serial = 0;
const timers = new Map();
win.setTimeout = (callback,delay)=>{const id=++serial;timers.set(id,{callback,delay});return id;};
win.clearTimeout = id=>timers.delete(id);
function runTimers(delay) {
  for (const [id, timer] of [...timers]) {
    if (timer.delay === delay && timers.delete(id)) timer.callback();
  }
}
const playerBar = element(), titleNode = element(), statusNode = element(),
  toggleButton = element(), stopButton = element(), openLink = element(),
  copyButton = element(), stationNode = element();
const root = {querySelectorAll:()=>[playerBar,titleNode,statusNode,toggleButton,
  stopButton,openLink,copyButton,stationNode]};
async function change(locale) {
  assert.equal(await i18n.setLocale(locale),true);
  presentation.refresh(root,i18n);
}
const noop = ()=>{};
let mediaCalls=0, historyCalls=0, metadataCalls=0, notifications=0, clipboard='', pending;
const metadataController = createMetadataController({presentation,titleNode,statusNode,
  copyButton,stationNode,windowRef:win,documentRef:doc,
  navigatorRef:{clipboard:{writeText:async value=>{clipboard=value;}}},
  apiFetch:()=>{metadataCalls++;return new Promise(resolve=>{pending=resolve;});},
  onMetadataChange:()=>notifications++});
const player = createPlayerController({presentation,audioNode,playerBar,titleNode,statusNode,
  toggleButton,stopButton,openLink,stationUrl:s=>s.url,logPlayerEvent:noop,
  mediaSessionController:{clearMediaSessionMetadata(){mediaCalls++;},
    reapplyCurrentMetadata(){mediaCalls++;},setMediaSessionMetadata(){mediaCalls++;},
    updateMediaSessionState(){mediaCalls++;}},
  metadataController,recordHistory:async()=>{historyCalls++;},resetRecordedHistory:noop,
  windowRef:win,documentRef:doc});
const stable = ()=>({snapshot:player.debugSnapshot(), loads:audioNode.loads, plays:audioNode.plays,
  mediaCalls,metadataCalls,notifications,historyCalls,timers:[...timers.keys()]});
const flush = async()=>{for(let i=0;i<12;i++) await Promise.resolve();};
await change('en');player.initialize();
const station={name:'<Radio> {track}',url:'https://radio.example/live'};
const start=player.playStation(station);await flush();
assert.equal(statusNode.textContent,'Loading stream...');
let before=stable();await change('es');
assert.equal(statusNode.textContent,'Cargando emisión...');
assert.equal(toggleButton.getAttribute('aria-label'),'Cargando emisión');
assert.equal(titleNode.textContent,'Esperando información de la canción…');
assert.deepEqual(stable(),before);
audioNode.dispatch('playing');await start;await flush();
assert.equal(playerBar.dataset.state,'playing');
assert.equal(statusNode.textContent,'Reproduciendo en el navegador.');
assert.equal(metadataCalls,1);assert.equal(historyCalls,1);
before=stable();await change('ca');
assert.equal(statusNode.textContent,'Reproduint en el navegador.');
assert.deepEqual(stable(),before);
const track='Idle — <Title> {name}';
pending({ok:true,json:async()=>({status:'fresh',metadata:{artist:'Idle',title:'<Title> {name}'}})});
await flush();
assert.equal(titleNode.textContent,track);assert.equal(stationNode.textContent,station.name);
assert.ok(copyButton.getAttribute('title').endsWith(track));
copyButton.dispatch('click');await flush();
assert.equal(clipboard,track);assert.equal(statusNode.textContent,'Cançó copiada al porta-retalls.');
before=stable();await change('fr');
assert.equal(statusNode.textContent,'Titre copié dans le presse-papiers.');
assert.equal(titleNode.textContent,track);assert.deepEqual(stable(),before);
runTimers(1800);assert.equal(statusNode.textContent,'Lecture dans le navigateur.');
// A newer transition invalidates the temporary feedback, including after a locale change.
copyButton.dispatch('click');await flush();player.pauseCurrentStationPlayback();
assert.equal(statusNode.textContent,'En pause.');before=stable();await change('es');
assert.equal(statusNode.textContent,'En pausa.');assert.deepEqual(stable(),before);
runTimers(1800);assert.equal(statusNode.textContent,'En pausa.');
player.stopPlayback();runTimers(0);
assert.equal(playerBar.dataset.state,'idle');assert.equal(titleNode.textContent,i18n.t('player.empty'));
let apiCalls=0;
const favorites=createFavoriteController({apiFetch:async()=>{apiCalls++;return {ok:true,json:async()=>({added:true})};},
  stationUrl:s=>s.url,setPlayerState:player.setPlayerState,isAuthenticated:()=>true});
await favorites.addFavorite(station);assert.equal(statusNode.textContent,'Guardada en favoritos.');
before=stable();await change('en');assert.equal(statusNode.textContent,'Saved to favorites.');
assert.deepEqual(stable(),before);assert.equal(apiCalls,1);
const name='Idle <playlist> {error}';
const playlists=createPlaylistController({presentation,setPlayerState:player.setPlayerState,
  apiFetch:async()=>{apiCalls++;return {ok:true,json:async()=>({created:true,name})};},loadPlaylists:async()=>{}});
await playlists.createPlaylist(name);assert.equal(statusNode.textContent,`Created playlist "${name}".`);
before=stable();await change('fr');assert.ok(statusNode.textContent.includes(name));
assert.deepEqual(stable(),before);assert.equal(apiCalls,2);
// Raw error content never becomes a translation key, even if equal to a known English message.
player.setPlayerState('error','Playing in browser.');await change('ca');
assert.equal(statusNode.textContent,'Playing in browser.');
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
