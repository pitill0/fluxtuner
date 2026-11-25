"""Catalog and native translation engine contracts."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

STATIC = Path(__file__).resolve().parents[1] / "fluxtuner/web/static"


def _unique(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, key
        result[key] = value
    return result


def test_catalogs_have_matching_keys_and_parameters():
    catalogs = {
        path.stem: json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique)
        for path in (STATIC / "locales").glob("*.json")
    }
    assert set(catalogs) == {"en", "es", "ca", "fr"}
    base = catalogs["en"]
    for catalog in catalogs.values():
        assert set(catalog) == set(base)
        for key, value in catalog.items():
            original = base[key]
            assert type(value) is type(original)
            variants = value if isinstance(value, dict) else {"other": value}
            originals = original if isinstance(original, dict) else {"other": original}
            assert "other" in variants
            for category, message in variants.items():
                assert isinstance(message, str) and message.strip()
                reference = originals.get(category, originals["other"])
                assert set(re.findall(r"\{(\w+)\}", message)) == set(
                    re.findall(r"\{(\w+)\}", reference)
                )


def test_native_engine(tmp_path):
    node = shutil.which("node")
    assert node is not None
    module = tmp_path / "i18n.mjs"
    shutil.copyfile(STATIC / "js/i18n.js", module)
    script = r"""
import assert from 'node:assert/strict';
const {createI18n, resolveLocale, loadCatalog} = await import(process.argv[1]);
assert.equal(resolveLocale(['invalid_locale', 'de-DE', 'ca-ES-valencia']), 'ca');
assert.equal(resolveLocale(['de-DE']), 'en');
const base = {hello: 'Hello {name}', count: {one: '{count} station', other: '{count} stations'}};
const saved = new Map();
const i = createI18n({preferences: ['es-ES'], storage: {getItem: k => saved.get(k), setItem: (k,v) => saved.set(k,v)},
  loader: async l => l === 'en' ? base : l === 'es' ? {hello: 'Hola {name}'} : Promise.reject()});
await i.initialize();
assert.equal(i.locale, 'es');
assert.equal(i.t('hello', {name: '<img>'}), 'Hola <img>');
assert.equal(i.t('count', {count: 2}), '2 stations');
assert.equal(i.t('missing'), 'missing');
await i.setLocale('es');
assert.equal(saved.get('fluxtuner.language'), 'es');
await i.setLocale('fr');
assert.equal(i.locale, 'en');
await assert.rejects(i.setLocale('../en'));
let release;
const j = createI18n({loader: l => l === 'en' ? base : new Promise(r => {release = r;})});
await j.initialize();
const slow = j.setLocale('fr');
await new Promise(r => setImmediate(r));
await j.setLocale('en');
release({hello: 'Bonjour'});
assert.equal(await slow, false);
assert.equal(j.locale, 'en');
await assert.rejects(loadCatalog('../en'));
let url, options;
await loadCatalog('ca', async (u, opts) => {url = u; options = opts; return {ok: true, json: async () => base};});
assert.equal(options.priority, 'high');
assert.equal(options.credentials, 'same-origin');
assert.equal(url.pathname.split('/').slice(-2).join('/'), 'locales/ca.json');
"""
    subprocess.run([node, "--input-type=module", "--eval", script, module.as_uri()], check=True)


def test_catalog_http_contract(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from fluxtuner import paths
    from fluxtuner.web.app import create_app

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    monkeypatch.setenv("FLUXTUNER_WEB_VERSIONED_STATIC", "1")
    client = TestClient(create_app())
    html = client.get("/")
    prefix = re.search(r"/static/build/[0-9a-f]{16}/", html.text)
    assert prefix is not None
    for locale in ("en", "es", "ca", "fr"):
        asset = f"locales/{locale}.json"
        versioned = client.get(prefix.group() + asset)
        legacy = client.get("/static/" + asset)
        assert versioned.status_code == legacy.status_code == 200
        assert versioned.json() == legacy.json()
        assert versioned.headers["cache-control"].endswith("immutable")
        assert legacy.headers["cache-control"] == "no-cache"
        assert versioned.headers["content-type"].startswith("application/json")
