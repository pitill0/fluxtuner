"""Static translation coverage and non-destructive language switching."""

from __future__ import annotations

import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "fluxtuner/web"


class TemplateParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.keys = set()
        self.selector_hidden = False
        self.options = []
        self.in_selector = False

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        for name, value in attributes.items():
            if name == "data-i18n" or name.startswith("data-i18n-"):
                self.keys.add(value)
        if "data-language-control" in attributes:
            self.selector_hidden = "hidden" in attributes
        if tag == "select" and "data-language-select" in attributes:
            self.in_selector = True
        if tag == "option" and self.in_selector:
            self.options.append((attributes["value"], attributes["lang"]))

    def handle_endtag(self, tag):
        if tag == "select":
            self.in_selector = False


def test_template_catalog_contract():
    parser = TemplateParser()
    parser.feed((WEB / "templates/index.html").read_text(encoding="utf-8"))
    assert not parser.selector_hidden
    assert parser.options == [
        (lang, lang) for lang in ("en", "es", "ca", "fr", "de", "zh-CN", "zh-TW", "ko", "ja")
    ]
    assert len(parser.keys) >= 180
    for locale in ("en", "es", "ca", "fr", "de", "zh-CN", "zh-TW", "ko", "ja"):
        catalog = json.loads((WEB / f"static/locales/{locale}.json").read_text(encoding="utf-8"))
        assert all(isinstance(catalog[key], str) for key in parser.keys)


def test_language_switch_preserves_dynamic_content(tmp_path):
    node = shutil.which("node")
    assert node is not None
    (tmp_path / "package.json").write_text('{"type":"module"}', encoding="utf-8")
    for name in ("i18n.js", "i18n-ui.js"):
        shutil.copyfile(WEB / "static/js" / name, tmp_path / name)
    script = r"""
import assert from 'node:assert/strict';
const {createI18n} = await import(new URL('./i18n.js', process.argv[1]));
const {createLanguageController, initializeLanguageUi} = await import(process.argv[1]);
const catalogs = {en: {hello: 'Hello', label: 'Play'}, es: {hello: 'Hola', label: 'Reproducir'}};
const i18n = createI18n({loader: async l => catalogs[l], preferences: ['es']});
function element(text, attrs) {
  return {textContent: text, children: [], getAttribute: k => attrs[k],
    setAttribute: (k,v) => {attrs[k] = v;}};
}
const title = element('Hello', {'data-i18n': 'hello'});
const status = element('Hello', {'data-i18n': 'hello'});
const button = element('', {'data-i18n-aria-label': 'label', 'aria-label': 'Play'});
const root = {documentElement: {lang: 'en'}, querySelectorAll: s =>
  s === '[data-i18n]' ? [title,status] : s === '[data-i18n-aria-label]' ? [button] : []};
const selector = {value: 'en', addEventListener: () => {}};
status.textContent = 'External track title';
const controller = createLanguageController({root, selector, i18n});
await controller.initialize();
assert.equal(root.documentElement.lang, 'es');
assert.equal(title.textContent, 'Hola');
assert.equal(status.textContent, 'External track title');
assert.equal(button.getAttribute('aria-label'), 'Reproducir');
await controller.change('en');
assert.equal(root.documentElement.lang, 'en');
assert.equal(title.textContent, 'Hello');
assert.equal(status.textContent, 'External track title');
assert.equal(button.getAttribute('aria-label'), 'Play');
assert.equal(initializeLanguageUi({querySelector: () => ({hidden:true})}, {}), undefined);
"""
    subprocess.run(
        [node, "--input-type=module", "--eval", script, (tmp_path / "i18n-ui.js").as_uri()],
        check=True,
    )


def test_active_language_ui_real_catalogs(tmp_path):
    node = shutil.which("node")
    assert node is not None
    (tmp_path / "package.json").write_text('{"type":"module"}', encoding="utf-8")
    for name in ("i18n.js", "i18n-ui.js", "i18n-presentation.js"):
        shutil.copyfile(WEB / "static/js" / name, tmp_path / name)
    script = r"""
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
const {initializeLanguageUi} = await import(process.argv[1]);
const {createDynamicPresentation} = await import(new URL('./i18n-presentation.js', process.argv[1]));
const catalogs = Object.fromEntries(['en','es','ca','fr','de','zh-CN','zh-TW','ko','ja'].map(locale => [locale,
  JSON.parse(readFileSync(join(process.argv[2], `${locale}.json`), 'utf8'))]));
const storage = new Map();
const requests = [];
let unavailable;
globalThis.fetch = async url => {
  const locale = url.pathname.split('/').at(-1).replace('.json', '');
  requests.push(locale);
  return {ok: locale !== unavailable, json: async () => catalogs[locale]};
};
function start(languages) {
  const label = {textContent: catalogs.en['brand.subtitle'], children: [],
    getAttribute: () => 'brand.subtitle'};
  const dynamic = {textContent: ''};
  const selector = {value: 'en', addEventListener: () => {}};
  const control = {hidden: false};
  const root = {documentElement: {lang: 'en'},
    querySelector: s => s === '[data-language-control]' ? control : selector,
    querySelectorAll: s => s === '[data-i18n]' ? [label] : s === '*' ? [label,dynamic] : []};
  const browser = {navigator: {languages}, localStorage: {
    getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v)}};
  const presentation = createDynamicPresentation();
  presentation.present(dynamic, 'settings.language', 'Language');
  const ui = initializeLanguageUi(root, browser, presentation);
  return {ui, root, label, dynamic, selector};
}
const a = start(['it-IT','ca-ES-valencia']);
await a.ui.ready;
assert.equal(a.root.documentElement.lang, 'ca');
for (const locale of ['ca','en','es','fr','de','zh-CN','zh-TW','ko','ja','ca']) {
  await a.ui.controller.change(locale);
  assert.equal(a.root.documentElement.lang, locale);
  assert.equal(a.selector.value, locale);
  assert.equal(a.label.textContent, catalogs[locale]['brand.subtitle']);
  assert.equal(a.dynamic.textContent, catalogs[locale]['settings.language']);
}
assert.deepEqual(requests, ['en','ca','es','fr','de','zh-CN','zh-TW','ko','ja']);
assert.equal(storage.get('fluxtuner.language'), 'ca');
const b = start(['fr']);
await b.ui.ready;
assert.equal(b.root.documentElement.lang, 'ca');
unavailable = 'fr';
await b.ui.controller.change('fr');
assert.equal(b.root.documentElement.lang, 'en');
assert.equal(b.selector.value, 'en');
assert.equal(storage.get('fluxtuner.language'), 'ca');
"""
    subprocess.run(
        [
            node,
            "--input-type=module",
            "--eval",
            script,
            (tmp_path / "i18n-ui.js").as_uri(),
            str(WEB / "static/locales"),
        ],
        check=True,
    )
