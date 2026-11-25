"""Health feedback changes language without replaying requests or translating raw JSON."""

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_health_pending_language_change(tmp_path):
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
const {createHealthController} = await import(new URL('js/health.js', base));
const i18n = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
const node = () => ({textContent:''});
const statusNode=node(), healthStateNode=node(), healthSummaryNode=node();
const root = {querySelectorAll:()=>[statusNode,healthStateNode,healthSummaryNode]};
let complete, calls=0;
const controller = createHealthController({presentation,statusNode,healthStateNode,healthSummaryNode,
  fetch:()=>{calls++;return new Promise(resolve=>{complete=resolve;});}});
await i18n.setLocale('en'); presentation.refresh(root,i18n);
const pending=controller.checkHealth();
assert.equal(statusNode.textContent,'Checking server...');
await i18n.setLocale('es'); presentation.refresh(root,i18n);
assert.equal(statusNode.textContent,'Comprobando servidor...');
assert.equal(calls,1);
const payload={status:'ok',version:'1.7.0',database:'sqlite'};
complete({ok:true,json:async()=>payload}); await pending;
assert.equal(healthStateNode.textContent,'OK');
assert.match(healthSummaryNode.textContent,/1\.7\.0.*sqlite.*comprobado ahora/);
assert.equal(statusNode.textContent,JSON.stringify(payload,null,2));
await i18n.setLocale('fr'); presentation.refresh(root,i18n);
assert.match(healthSummaryNode.textContent,/vérifié à l’instant/);
assert.equal(statusNode.textContent,JSON.stringify(payload,null,2));
assert.equal(calls,1);
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
