"""Live localization of search results and library loading states."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_library_messages_switch_without_replaying_requests(tmp_path):
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
const {createSearchController} = await import(new URL('js/search.js', base));
const {createLibraryViewsController} = await import(new URL('js/library-views.js', base));
const {createPlaylistRenderer} = await import(new URL('js/playlist-renderer.js', base));
const i18n = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
const count = {textContent:''};
const notice = {textContent:''};
const partial = {textContent:''};
const name = {textContent:'Favorites'};
const root = {querySelectorAll:()=>[count,notice,partial,name]};
const results = {innerHTML:'',querySelector:s=>s==='[data-search-partial]'?partial:notice};
let renders=0;
const search = createSearchController({resultsNode:results,resultCountNode:count,
  subscribeViewChange(){},renderStation:s=>s.name,bindResultActions(){renders++;},presentation});
async function change(locale) {await i18n.setLocale(locale); presentation.refresh(root,i18n);}
search.renderResults({stations:[{name:'Favorites'}],count:1,status:'partial'});
await change('es');
assert.equal(count.textContent,'1 resultado');
assert.match(partial.textContent,/Algunas fuentes/);
assert.equal(name.textContent,'Favorites');
assert.equal(renders,1);
await change('ca');
assert.equal(count.textContent,'1 resultat');
search.renderResults({stations:[],count:0});
assert.equal(count.textContent,'0 resultats');
assert.equal(notice.textContent,'No s’han trobat emissores.');
await change('fr');
assert.equal(notice.textContent,'Aucune station trouvée.');
let calls=0, resolve;
const library=createLibraryViewsController({resultsNode:results,resultCountNode:count,
  apiFetch:()=>{calls++;return new Promise(r=>{resolve=r;});},setLibraryView(){},
  setResultsHeader(){},getCurrentView:()=> 'favorites',getCurrentUser:()=>1,
  isLibraryVisible:()=>true,renderResults:search.renderResults,presentation});
const pending=library.loadFavorites();
assert.match(count.textContent,/Chargement/);
await change('es');
assert.equal(count.textContent,'Cargando favoritos…');
assert.equal(calls,1);
resolve({ok:true,json:async()=>({stations:[{name:'Favorites'}],count:1})});
await pending;
assert.equal(count.textContent,'1 resultado');
assert.equal(calls,1);
const input={textContent:'',getAttribute:k=>input[k],setAttribute:(k,v)=>{input[k]=v;},value:'My list'};
const button={textContent:'Create playlist'};
const playlistResults={innerHTML:'',querySelectorAll:s=>s==='[data-create-playlist-form] input'?[input]:s==='[data-create-playlist-form] button'?[button]:[]};
globalThis.document={querySelectorAll:()=>[]};
const playlist=createPlaylistRenderer({resultsNode:playlistResults,resultCountNode:count,presentation});
playlist.renderPlaylists({playlists:[],count:0});
assert.equal(button.textContent,'Crear lista de reproducción');
assert.equal(input.value,'My list');
await i18n.setLocale('en');
presentation.refresh({querySelectorAll:()=>[count,input,button]},i18n);
assert.equal(button.textContent,'Create playlist');
assert.equal(count.textContent,'0 playlists');
assert.equal(input.value,'My list');
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
