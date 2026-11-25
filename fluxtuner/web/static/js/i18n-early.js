/* SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC */
import { browserI18n } from "./i18n.js";
import { createTemplateTranslator } from "./i18n-ui.js";

const i18n = browserI18n(window);
const translate = createTemplateTranslator(document, i18n);
void i18n.initialize().then((current) => {
  if (current) translate();
}).catch(() => {});
