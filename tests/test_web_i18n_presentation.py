"""Exercise live translation of controller-owned presentation state."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def test_dynamic_presentation_switches_without_replaying_controllers(tmp_path):
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
const {createLanguageController} = await import(new URL('js/i18n-ui.js', base));
const {createThemeController} = await import(new URL('js/theme.js', base));
const {createSidebarToggle} = await import(new URL('js/sidebar-toggle.js', base));
const {createMobileDrawer} = await import(new URL('js/mobile-drawer.js', base));
const i18n = createI18n({loader: async locale => JSON.parse(await readFile(
  new URL(`locales/${locale}.json`, base), 'utf8'))});
const presentation = createDynamicPresentation();
function element(text = '', attrs = {}) {
  return {textContent: text, children: [], dataset: {}, hidden: false,
    getAttribute: k => attrs[k], setAttribute: (k,v) => {attrs[k] = v;},
    querySelector: () => null, addEventListener() {}, focus() {focusCalls++;}};
}
let focusCalls = 0;
const themeLabel = element('Theme', {'data-i18n':'theme.label'});
const themeButton = element('', {'aria-label':'Switch theme',
  'data-i18n-aria-label':'theme.switch'});
const menuTitle = element('Navigation', {'data-i18n':'nav.title'});
const sidebar = element('', {'aria-label':'Collapse sidebar',
  'data-i18n-aria-label':'nav.collapse'});
const shell = element(), menu = element(), back = element();
const group = element(), groupButton = element(), groupContent = element();
const external = element('');
const removed = element('');
const nodes = [themeLabel, themeButton, menuTitle, sidebar, external];
const root = {documentElement:{lang:'en', dataset:{},style:{}},
  querySelectorAll: selector => selector === '*' ? nodes : nodes.filter(n =>
    n.getAttribute(selector.slice(1,-1)) !== undefined),
  querySelector: selector => ({'[data-app-menu]':menu,
    '[data-mobile-drawer-back]':back, '[data-mobile-drawer-title]':menuTitle,
    '[data-nav-group="library"]':group, '[data-nav-group-toggle="library"]':groupButton,
    '[data-nav-group-content="library"]':groupContent})[selector] ?? null};
const selector = element();
const controller = createLanguageController({root,selector,i18n,presentation});
const theme = createThemeController({documentRef:root,toggleButton:themeButton,
  labelNode:themeLabel,presentation});
const side = createSidebarToggle({shell,button:sidebar,presentation});
const drawer = createMobileDrawer({root,windowNode:{matchMedia:()=>({matches:true})},presentation});
theme.applyTheme('light'); side.toggle(); drawer.enter('library');
presentation.present(external,'nav.title','Navigation');
presentation.present(removed,'nav.title','Navigation');
await controller.change('es');
assert.equal(themeLabel.textContent,'Oscuro');
assert.equal(themeButton.getAttribute('aria-label'),'Cambiar al tema oscuro');
assert.equal(sidebar.getAttribute('title'),'Expandir barra lateral');
assert.equal(menuTitle.textContent,'Mi biblioteca');
assert.equal(shell.dataset.sidebarCollapsed,'true');
assert.equal(root.documentElement.dataset.theme,'light');
assert.equal(menu.dataset.mobileLevel,'group');
assert.equal(groupContent.hidden,false);
assert.equal(focusCalls,1);
assert.equal(removed.textContent,'Navigation');
external.textContent = 'External title';
await controller.change('ca');
assert.equal(menuTitle.textContent,'La meua biblioteca');
assert.equal(external.textContent,'External title');
external.textContent = 'Navegación';
await controller.change('fr');
assert.equal(external.textContent,'Navegación');
assert.equal(themeLabel.textContent,'Sombre');
assert.equal(menuTitle.textContent,'Ma bibliothèque');
assert.equal(focusCalls,1);
side.toggle(); theme.applyTheme('dark'); drawer.back();
assert.equal(sidebar.getAttribute('aria-label'),'Réduire la barre latérale');
assert.equal(themeLabel.textContent,'Clair');
assert.equal(menuTitle.textContent,'Navigation');
presentation.present(external,'nav.title','Navigation');
presentation.clear(external);
await controller.change('en');
assert.equal(external.textContent,'Navigation');
assert.equal(themeLabel.textContent,'Light');
assert.equal(root.documentElement.lang,'en');
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, str(tmp_path)],
        check=True,
        timeout=30,
    )
