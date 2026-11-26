"""Independent audit regressions: first load, missing base and mobile relocation."""

import ast
import json
import re
import shutil
import subprocess
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "fluxtuner/web"


def test_audit_error_contract():
    source = (WEB / "static/js/api.js").read_text()
    mapped = dict(re.findall(r'\["([^"\n]+)", "((?:api|imports\.feedback)\.[^"]+)"\]', source))
    # Diagnostic failures are deliberately not part of the translated UI contract.
    technical = {
        "Metadata diagnostics are unavailable.",
        "Could not create recovery codes.",
        "Could not create setup session.",
    }
    details = set()
    for path in sorted(WEB.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
                and any(isinstance(t, ast.Name) and t.id.endswith("_DETAIL") for t in node.targets)
            ):
                details.add(node.value.value)
            if (
                isinstance(node, ast.keyword)
                and node.arg is not None
                and (node.arg == "detail" or node.arg.endswith("_detail"))
                and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                details.add(node.value.value)
    assert not details - set(mapped) - technical, sorted(details - set(mapped) - technical)
    for locale in ("en", "es", "ca", "fr", "de", "zh-CN", "zh-TW", "ko", "ja"):
        catalog = json.loads((WEB / f"static/locales/{locale}.json").read_text())
        assert set(mapped.values()) <= catalog.keys()
    ca = json.loads((WEB / "static/locales/ca.json").read_text())
    assert "coincidixen" in ca["account.password_mismatch"]
    assert "coincidix" in ca["admin.confirm_mismatch"]
    assert "Introduïx el token" in ca["setup.token_instruction"]
    for key, action in {
        "station.play": "Reproduïx",
        "station.share": "Compartix",
        "library.export_format_m3u": "Exporta",
        "station.add_favorite": "Afig",
        "playlists.create": "Crea",
        "recommendations.action.accept": "Accepta",
        "admin.action.approve": "Aprova",
        "subscriptions.action.remove": "Cancel·la",
    }.items():
        assert ca[key].split()[0] == action


def test_audit_engine_and_mobile_relocation(tmp_path):
    node = shutil.which("node")
    assert node is not None
    (tmp_path / "package.json").write_text('{"type":"module"}')
    shutil.copytree(WEB / "static/js", tmp_path / "js")
    shutil.copytree(WEB / "static/locales", tmp_path / "locales")
    script = r"""
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const base = new URL('js/', process.argv[1]);
const {createI18n, browserI18n} = await import(new URL('i18n.js', base));
const {createTemplateTranslator, initializeLanguageUi} = await import(new URL('i18n-ui.js', base));
const {createMediaSessionController} = await import(new URL('media-session.js', base));
const calls = [], pending = {};
const engine = createI18n({preferences:['es'], loader: l => {
  calls.push(l); return new Promise((resolve,reject) => {pending[l]={resolve,reject};});
}});
let offline = true;
const attempts = [];
const retry = createI18n({preferences:['es'], loader: async language => {
  attempts.push(language);
  if (offline) throw new Error('Offline');
  return {hello: language === 'es' ? 'Hola' : 'Hello'};
}});
const failed = retry.initialize();
assert.equal(retry.initialize(), failed);
await assert.rejects(failed);
assert.equal(retry.locale, 'en');
offline = false;
const recovered = retry.initialize();
assert.equal(retry.initialize(), recovered);
assert.equal(await recovered, true);
assert.equal(retry.locale, 'es');
assert.equal(retry.t('hello'), 'Hola');
assert.deepEqual(attempts, ['en','es','en','es']);
const starting = engine.initialize();
assert.equal(engine.initialize(), starting);
await new Promise(r=>setImmediate(r));
assert.deepEqual(calls,['en','es']);
const label={textContent:'Hello',children:[],getAttribute:()=> 'hello'};
const stale={textContent:'Original',children:[],getAttribute:()=> 'hello'};
const root={documentElement:{lang:'en'},querySelectorAll:s=>s==='[data-i18n]'?[label,stale]:[]};
const early=createTemplateTranslator(root,engine);
stale.textContent='User title';
pending.en.reject(Error('offline'));
pending.es.resolve({hello:'Hola',count:{one:'{count} usuario',other:'{count} usuarios'}});
await starting; early();
assert.equal(root.documentElement.lang,'es');
assert.equal(label.textContent,'Hola');
assert.equal(stale.textContent,'User title');
assert.equal(engine.t('count',{count:1234567}),new Intl.NumberFormat('es').format(1234567)+' usuarios');
assert.equal(createTemplateTranslator(root,engine),early);
const failing=engine.setLocale('en');
await new Promise(r=>setImmediate(r)); pending.en.reject(Error('offline'));
await assert.rejects(failing); assert.equal(engine.locale,'es');
// Actual move of the existing control, not duplicate selectors/listeners.
let onResize,onAuth,listenerCount=0;
const home={insertBefore(node,next){node.parentNode=this;assert.equal(next,anchor);}};
const anchor={}; const control={hidden:false,parentNode:home,nextSibling:anchor};
const menu={append(node){node.parentNode=this;}};
const user={hidden:true}; const narrow={matches:true,addEventListener(_,fn){onResize=fn;}};
const selector={value:'en',addEventListener(){listenerCount++;}};
const mobileRoot={documentElement:{lang:'en'},querySelectorAll:()=>[],querySelector(s){return ({
  '[data-language-control]':control,'[data-language-select]':selector,
  '[data-auth-user]':user,'[data-language-mobile-slot]':menu})[s];}};
const browser={navigator:{languages:['es']},matchMedia:()=>narrow,MutationObserver:class{
  constructor(fn){onAuth=fn;} observe(){}
}};
const requests=[];
globalThis.fetch=async url=>{requests.push(url.pathname);return {ok:true,json:async()=>JSON.parse(await readFile(url,'utf8'))};};
await browserI18n(browser).initialize();
const ui=initializeLanguageUi(mobileRoot,browser); await ui.ready;
assert.equal(requests.length,2); assert.equal(control.parentNode,home);
user.hidden=false;onAuth();assert.equal(control.parentNode,menu);
narrow.matches=false;onResize();assert.equal(control.parentNode,home);
narrow.matches=true;onResize();assert.equal(control.parentNode,menu);
user.hidden=true;onAuth();assert.equal(control.parentNode,home);assert.equal(listenerCount,1);
// Counts and exact server errors are presentation-only bindings.
const {createAdminController} = await import(new URL('admin.js', base));
const {createDynamicPresentation} = await import(new URL('i18n-presentation.js', base));
const messages={textContent:''}, setupMessage={textContent:''};
const presentation=createDynamicPresentation();
const messageRoot={querySelectorAll:()=>[messages,setupMessage]};
presentation.refresh(messageRoot,ui.i18n);
let response={ok:true,json:async()=>({count:1234567,users:[]})};
const admin=createAdminController({presentation,messageNode:messages,
 getCurrentUser:()=>({is_admin:true}),apiFetch:async()=>response});
await admin.loadUsers();
assert.equal(messages.textContent,new Intl.NumberFormat('es').format(1234567)+' usuarios web.');
await ui.i18n.setLocale('fr');presentation.refresh(messageRoot,ui.i18n);
assert.equal(messages.textContent,new Intl.NumberFormat('fr').format(1234567)+' utilisateurs web.');
response={ok:false,json:async()=>({detail:'Cannot remove the last active administrator.'})};
await admin.loadUsers();
assert.equal(messages.textContent,ui.i18n.t('api.last_admin'));
response={ok:false,json:async()=>({detail:'Unrecognized diagnostic'})};
await admin.loadUsers();
assert.equal(messages.textContent,'Error: Unrecognized diagnostic');
// Media Session translation only occurs when metadata is actually built.
globalThis.window={location:{href:'https://example.test/'}};
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{mediaSession:{metadata:null}}});
globalThis.MediaMetadata=class{constructor(data){Object.assign(this,data);}};
window.MediaMetadata=globalThis.MediaMetadata;
let translations=0;
const media=createMediaSessionController({getCurrentStation:()=>({}),logPlayerEvent:()=>{},
 translate:(key,fallback)=>{assert.equal(key,'station.unknown_station');translations++;return 'Emisora desconocida';}});
media.setMediaSessionMetadata({});
assert.equal(navigator.mediaSession.metadata.title,'Emisora desconocida');
assert.ok(translations>0);
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, tmp_path.as_uri() + "/"],
        check=True,
        timeout=30,
    )
