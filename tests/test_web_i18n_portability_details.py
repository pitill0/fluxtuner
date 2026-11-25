"""Portability presentation preserves names and does not replay requests."""

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_share_title_language_change(tmp_path):
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
const {createRecommendationsController} = await import(new URL('js/recommendations.js', base));
const engine = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
const nodes = new Map();
for (const role of ['title','compose','recipient','message','destination','items']) {
  nodes.set(role,{textContent:'',value:'',hidden:false,focus(){},replaceChildren(){}});
}
const dialog = {open:false,showModal(){this.open=true;},
  querySelector(selector){return nodes.get(selector.match(/data-recommendations-([a-z]+)/)[1]);}};
const root = {querySelectorAll:()=>[...nodes.values()]};
let calls = 0;
const controller = createRecommendationsController({presentation,dialog,
  getCurrentUser:()=>({id:1}),getSessionKey:()=> 'session',apiFetch:()=>{calls++;}});
await engine.setLocale('en'); presentation.refresh(root,engine);
controller.sharePlaylist('<img> Radio');
assert.equal(nodes.get('title').textContent,'Share playlist: <img> Radio');
nodes.get('recipient').value='alice';
await engine.setLocale('ca'); presentation.refresh(root,engine);
assert.equal(nodes.get('title').textContent,'Compartix llista de reproducció: <img> Radio');
assert.equal(nodes.get('recipient').value,'alice');
assert.equal(dialog.open,true);
assert.equal(calls,0);
await engine.setLocale('fr'); presentation.refresh(root,engine);
assert.equal(nodes.get('title').textContent,'Partager la liste de lecture : <img> Radio');
assert.equal(calls,0);
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
