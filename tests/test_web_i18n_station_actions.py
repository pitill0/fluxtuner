"""Station presentation and translated confirmations preserve action data."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_station_labels_and_confirmation_without_replaying_actions(tmp_path):
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
const {createI18n} = await import(new URL('js/i18n.js', base));
const {createDynamicPresentation} = await import(new URL('js/i18n-presentation.js', base));
const {createStationRenderer} = await import(new URL('js/station-renderer.js', base));
const {createPlaylistController} = await import(new URL('js/playlists.js', base));
const {createStationPublicationController} = await import(new URL('js/station-publication.js', base));
const i18n = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
const label = {textContent:'Play', dataset:{stationI18n:'station.play'}};
const count = {textContent:'2 plays', dataset:{stationPlayCount:'2'}};
const name = {textContent:'Play'};
const root = {querySelectorAll:()=>[label,count,name]};
globalThis.document = {querySelectorAll:s=>s==='[data-station-i18n]'?[label]:
  s==='[data-station-play-count]'?[count]:[]};
const renderer = createStationRenderer({presentation,renderState:()=>({currentUser:1,currentView:'favorites'})});
const html = renderer.renderStation({name:'<img>Play',url:'https://radio.example/live',station_id:1});
assert.match(html,/&lt;img&gt;Play/);
assert.match(html,/data-station-i18n="station.play"/);
renderer.bindResultActions();
await i18n.setLocale('es'); presentation.refresh(root,i18n);
assert.equal(label.textContent,'Reproducir');
assert.equal(count.textContent,'2 reproducciones');
assert.equal(name.textContent,'Play');
renderer.bindResultActions();
await i18n.setLocale('en'); presentation.refresh(root,i18n);
assert.equal(label.textContent,'Play');
assert.equal(count.textContent,'2 plays');
await i18n.setLocale('fr'); presentation.refresh(root,i18n);
let calls=0, warning='';
globalThis.window={confirm:message=>{warning=message;return false;}};
const apiFetch=()=>{calls++;throw Error('unexpected request');};
const playlists=createPlaylistController({presentation,apiFetch});
await playlists.deletePlaylist('<My list>');
assert.match(warning,/Supprimer la liste/);
assert.match(warning,/<My list>/);
const publication=createStationPublicationController({presentation,apiFetch,
  getCurrentUser:()=>({id:1}),getSessionKey:()=> 'session'});
await publication.toggle({station_id:1,publication_eligible:true},{disabled:false});
assert.match(warning,/Rendre cette station publique/);
assert.match(warning,/copies déjà enregistrées/);
assert.equal(calls,0);
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
