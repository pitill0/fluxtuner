"""A translated pending subscription message is cleared without replaying requests."""

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_subscription_pending_language_change(tmp_path):
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
const {createRemoteSubscriptionController} = await import(new URL('js/remote-subscriptions.js', base));
const i18n = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
const node = () => ({textContent:'',replaceChildren(){},append(){},hidden:false});
const elements = {dialog:{open:false,showModal(){this.open=true;}},
  messageNode:node(), previewNode:node(), confirmButton:node(),
  listNode:{...node(),ownerDocument:{createElement:node}}};
const root = {querySelectorAll:()=>[elements.messageNode]};
let complete, calls=0;
const controller = createRemoteSubscriptionController({elements,presentation,
  getCurrentUser:()=>({id:1}),getSessionKey:()=> 'session',
  apiFetch:()=>{calls++;return new Promise(resolve=>{complete=resolve;});}});
await i18n.setLocale('en'); presentation.refresh(root,i18n);
const pending = controller.openDialog();
assert.equal(elements.messageNode.textContent,'Working…');
await i18n.setLocale('es'); presentation.refresh(root,i18n);
assert.equal(elements.messageNode.textContent,'Procesando…');
assert.equal(calls,1);
complete({ok:true,json:async()=>({subscriptions:[]})});
await pending;
assert.equal(elements.messageNode.textContent,'');
await i18n.setLocale('fr'); presentation.refresh(root,i18n);
assert.equal(elements.messageNode.textContent,'');
assert.equal(calls,1);
assert.equal(elements.dialog.open,true);
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
