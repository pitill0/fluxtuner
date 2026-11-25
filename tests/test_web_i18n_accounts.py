"""Account presentation must not replay authentication or admin mutations."""

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_account_and_admin_language_change(tmp_path):
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
const {createAuthController} = await import(new URL('js/auth.js', base));
const {createSetupController} = await import(new URL('js/setup.js', base));
const {createAdminController} = await import(new URL('js/admin.js', base));
const i18n = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
const authMessageNode = {textContent:'',hidden:false};
const messageNode = {textContent:''};
const feedback = {textContent:''};
const root = {querySelectorAll:()=>[authMessageNode,messageNode,feedback]};
const noop = ()=>{};
let calls=0, complete, sent;
globalThis.FormData = class {get(key){return {username:'test-user',password:'secret'}[key];}};
globalThis.fetch = (url, options)=>{calls++; sent=JSON.parse(options.body);
  return new Promise(resolve=>{complete=resolve;});};
const auth = createAuthController({presentation,authMessageNode,loginForm:{reset:noop},
  setCurrentUser:noop,setCsrfToken:noop,updateAuthUi:noop});
await i18n.setLocale('en'); presentation.refresh(root,i18n);
const pending=auth.login({preventDefault:noop});
assert.equal(authMessageNode.textContent,'Signing in...');
await i18n.setLocale('es'); presentation.refresh(root,i18n);
assert.equal(authMessageNode.textContent,'Iniciando sesión...');
assert.deepEqual(sent,{username:'test-user',password:'secret'});
assert.equal(calls,1);
complete({ok:false,status:401,json:async()=>({detail:'Invalid username or password.'})});
await pending;
await i18n.setLocale('ca'); presentation.refresh(root,i18n);
assert.equal(authMessageNode.textContent,'Usuari o contrasenya incorrectes.');
const unknown=auth.login({preventDefault:noop});
complete({ok:false,status:401,json:async()=>({detail:'Invalid username or password. (diagnostic)'})});
await unknown;
assert.equal(authMessageNode.textContent,'Invalid username or password. (diagnostic)');
let promptText;
globalThis.window={prompt:(text)=>{promptText=text;return 'wrong';}};
const admin=createAdminController({presentation,messageNode,getCurrentUser:()=>({username:'admin',is_admin:true}),
  apiFetch:()=>{calls++;throw Error('Unexpected mutation');}});
const button={closest:()=>({querySelector:()=>feedback})};
await admin.mutateUser('test-user','delete',button);
assert.ok(promptText.includes('DELETE test-user'));
assert.ok(messageNode.textContent.includes('DELETE test-user'));
assert.equal(feedback.textContent,messageNode.textContent);
await i18n.setLocale('fr'); presentation.refresh(root,i18n);
assert.ok(messageNode.textContent.includes('Saisissez exactement'));
assert.equal(feedback.textContent,messageNode.textContent);
assert.equal(calls,2);
const setupMessageNode={textContent:''};
const setupRoot={querySelectorAll:()=>[setupMessageNode]};
let setupBody;
globalThis.FormData=class {get(key){return {username:'first',password:'pw',confirm_password:'pw',setup_token:'literal-token'}[key];}};
globalThis.fetch=async (url,options)=>{
  if (url==='/api/setup/status') return {ok:true,json:async()=>({available:true,requires_setup_token:true})};
  setupBody=JSON.parse(options.body);
  return {ok:false,status:400,json:async()=>({detail:'test rejection'})};
};
const setup=createSetupController({presentation,setupMessageNode,setupForm:{reset:noop},
  getCurrentUser:()=>null,setPlayerVisible:noop,setAppContentVisible:noop,
  setCurrentUser:noop,setCsrfToken:noop,updateAuthUi:noop});
await setup.loadSetupState();
assert.ok(setupMessageNode.textContent.includes('jeton'));
await i18n.setLocale('es'); presentation.refresh(setupRoot,i18n);
assert.ok(setupMessageNode.textContent.includes('token de verificación'));
await setup.createFirstAdmin({preventDefault:noop});
assert.deepEqual(setupBody,{username:'first',password:'pw',setup_token:'literal-token'});
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
