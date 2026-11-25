# Translating FluxTuner Web

FluxTuner Web currently supports English (`en`), Spanish (`es`), Valencian (`ca`) and French (`fr`). Native speakers and contributors are welcome to improve existing translations or propose additional languages. This guide covers the Web interface, not the GTK or terminal interfaces.

## Improve an existing translation

1. Fork the repository on GitHub and create a branch from `main`.
2. Open the corresponding UTF-8 JSON file in [`fluxtuner/web/static/locales/`](fluxtuner/web/static/locales/): `en.json`, `es.json`, `ca.json` or `fr.json`.
3. Edit message values, not their keys. Use `en.json` as the reference for meaning and context.
4. Validate the catalog and, if possible, check the affected screens in the browser (see below).
5. Open a focused pull request. State the language, what changed, any terminology choices and which checks you ran. Screenshots are welcome, but remove personal information first.

Small corrections are welcome. For a typo, GitHub's file editor is sufficient; if you cannot run the tests, say so in the PR. You can also open an issue describing the screen, current text and suggested translation.

## Catalog conventions

- Keep every key from the English catalog; do not rename keys, add duplicates or leave empty values. Keep JSON valid and save in UTF-8.
- Preserve all named placeholders exactly, including case: `{name}`, `{count}`, `{error}`, etc. You may move them to fit natural sentence order, but do not translate them or add new ones.
- Keep plural objects as objects, with an `other` form and the categories appropriate for the target language. The runtime selects forms with `Intl.PluralRules`; preserve the required placeholders in every form. For example:

  ```json
  {
    "stations.count": {
      "one": "{count} station",
      "other": "{count} stations"
    }
  }
  ```

  This is a fragment, not a replacement for the entire catalog. Test zero, one, two and representative larger counts.
- Use plain text, not HTML or JavaScript. Escape quotation marks, backslashes and line breaks as required by JSON, not as HTML entities. Renderers are responsible for safe output.
- Translate meaning, not word order. Keep terminology consistent across navigation, dialogs, errors and accessibility labels. For `ca`, use natural Valencian terminology and spelling. The existing `ca` catalog intentionally represents Valencian: browser preferences such as `ca-ES` and `ca-ES-valencia` both resolve to it. Please coordinate additional regional variants in an issue rather than replacing the current catalog. Use `token` consistently for authentication and setup tokens. Use the second-person singular imperative for action buttons (for example, `Exporta`, `Afig`, `Reproduïx` and `Compartix`), while retaining natural infinitives in explanatory prose.
- Preserve product names, protocol names, identifiers, confirmation tokens such as `DELETE`, URLs and technical units. Do not translate station names, playlist names, usernames or song metadata supplied at runtime.
- Preserve the meaning of security warnings, destructive confirmations and privacy notices. Do not make them less explicit.
- Do not hard-code regional number grouping or dates into messages; the application handles formatting where supported. Keep button text concise and check narrow screens and accessible labels.

## Propose a new language

Open an issue first to agree on the locale code, display name, terminology and review arrangements. The implementation currently uses a fixed supported-language list; adding a JSON file alone does not enable it.

A new-language PR should copy `en.json` to `<locale>.json`, translate its values, update `SUPPORTED_LOCALES` and locale resolution in `fluxtuner/web/static/js/i18n.js` as appropriate, add a native-language option with the appropriate `lang` attribute in `fluxtuner/web/templates/index.html`, and update the supported-locale expectations in the catalog, template, HTTP and runtime tests. Check static build and packaging coverage for the new catalog. If the language needs right-to-left layout or regional variants, coordinate that work explicitly rather than assuming existing layout or primary-language matching will suffice.

## Validate locally

From the repository root, use the development environment described in [CONTRIBUTING.md](CONTRIBUTING.md). Node.js is required for the JavaScript tests.

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest -q tests/test_web_i18n.py tests/test_web_i18n_template.py
```

The catalog test checks duplicate keys, key parity, nonempty messages, message types and placeholder parity. The remaining tests exercise the engine, template integration and catalog delivery. These checks cannot judge linguistic quality.

To inspect the Web interface using isolated local data:

```bash
DEV_DATA=$(mktemp -d /tmp/fluxtuner-translation.XXXXXXXX)
FLUXTUNER_DATA_DIR="$DEV_DATA" FLUXTUNER_WEB_SECURE_COOKIES=false \
  fluxtuner-web --host 127.0.0.1 --port 18080
```

Open `http://127.0.0.1:18080/`, complete setup using disposable test credentials, select the language, and inspect the affected screens. Check reload persistence, long labels, mobile-width layout, placeholders and plural forms. For changes affecting playback, verify that switching language does not interrupt audio. Stop the local server with Ctrl+C; the temporary data directory remains available for inspection. Never use production credentials or data for this test.

The independent Chromium checks can be run with `python -m pip install 'playwright>=1.50,<2'`, `python -m playwright install chromium`, and `python tests/web_i18n_browser.py`. They start a disposable loopback-only server. CI runs these separately from pytest. Physical device and screen-reader checks remain manual.

For changes to the engine or new locale support, also run the full project validation described in [CONTRIBUTING.md](CONTRIBUTING.md).

Thank you for helping make FluxTuner accessible to more listeners!
