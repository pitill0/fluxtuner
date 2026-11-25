"""Language changes preserve library navigation and pending requests."""

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_library_headers_and_pending_request(tmp_path):
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
const {createUiShellController} = await import(new URL('js/ui-shell.js', base));
const {createUnifiedLibraryController} = await import(new URL('js/unified-library.js', base));
const engine = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
const kicker = {textContent:''}, title = {textContent:''}, count = {textContent:''};
const results = {children:[], ownerDocument:{createElement:()=>({textContent:''})},
  replaceChildren(){this.children=[];}, append(n){this.children.push(n);}};
const root = {querySelectorAll:()=>[kicker,title,count,...results.children]};
const shell = createUiShellController({presentation,resultsKickerNode:kicker,resultsTitleNode:title});
let view, resolve, calls=0, rendered;
const user = {id:1};
const controller = createUnifiedLibraryController({presentation,
  apiFetch:()=>{calls++; return new Promise(r=>{resolve=r;});},
  getCurrentUser:()=>user,getCurrentView:()=>view,isLibraryVisible:()=>true,
  setLibraryView:v=>{view=v;},setResultsHeader:shell.setResultsHeader,
  resultsNode:results,resultCountNode:count,renderResults:p=>{rendered=p;},
  renderSearchError:e=>{throw e;}});
await engine.setLocale('en'); presentation.refresh(root,engine);
const pending=controller.loadMyStations();
assert.equal(title.textContent,'My stations');
await engine.setLocale('ca'); presentation.refresh(root,engine);
assert.equal(title.textContent,engine.t('nav.stations'));
assert.equal(count.textContent,'Carregant les meues emissores...');
assert.equal(results.children[0].textContent,count.textContent);
assert.equal(calls,1);
resolve({ok:true,json:async()=>({stations:[{name:'<img> Radio'}]})});
await pending;
assert.equal(rendered.stations[0].name,'<img> Radio');
shell.setResultsHeader('Playlist','My stations','playlists.single');
await engine.setLocale('fr'); presentation.refresh(root,engine);
assert.equal(title.textContent,'My stations');
assert.equal(kicker.textContent,engine.t('playlists.single'));
assert.equal(calls,1);
const preview = {textContent:''};
results.children.push(preview);
presentation.presentParts(preview,[{key:'imports.preview.existing',
  fallback:'<img> — already in favorites\nhttps://example.test/?a=1&b=2',
  params:{name:'<img>',url:'https://example.test/?a=1&b=2'}},
  {key:'subscriptions.preview.added',fallback:'Added: 3',params:{count:3}}],'\n');
assert.equal(preview.textContent,'<img> — déjà dans les favoris\nhttps://example.test/?a=1&b=2\nAjoutées : 3');
await engine.setLocale('es'); presentation.refresh(root,engine);
assert.equal(preview.textContent,'<img> — ya en favoritos\nhttps://example.test/?a=1&b=2\nAñadidas: 3');
presentation.clear(preview); preview.textContent='';
await engine.setLocale('en'); presentation.refresh(root,engine);
assert.equal(preview.textContent,'');
assert.equal(calls,1);
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
