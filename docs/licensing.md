<!-- SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC -->

# FluxTuner licensing

FluxTuner has used a split licensing model since version 0.9.0, when the
Web/server and multi-user components were introduced. The existing local
application components remain MIT-licensed, while the identified Web/server
components are licensed under the FluxTuner Web Non-Commercial License.

## Summary

- FluxTuner local/core components are licensed under the MIT License.
- FluxTuner Web/server, multi-user, authentication, session, first-run setup,
  admin-user management, and hosted-service components are licensed under the
  FluxTuner Web Non-Commercial License.
- Commercial use of FluxTuner Web/server components requires a separate written
  commercial license.
- FluxTuner names, logos, icons, screenshots, website identity, and branding are
  reserved. See [`TRADEMARKS.md`](../TRADEMARKS.md).

## License files

- [`LICENSE`](../LICENSE): MIT License for the MIT-licensed FluxTuner components.
- [`LICENSE-WEB`](../LICENSE-WEB): FluxTuner Web Non-Commercial License.
- [`TRADEMARKS.md`](../TRADEMARKS.md): trademark and branding policy.

## Component scope

### MIT-licensed components

The MIT License applies to the local FluxTuner application components unless a
file says otherwise:

- terminal/TUI interface;
- GTK desktop interface;
- local CLI workflows;
- player backends;
- station search and compatibility helpers;
- local theme/runtime helpers;
- local cache/config/path helpers;
- non-web tests and documentation.

### FluxTuner Web non-commercial components

The FluxTuner Web Non-Commercial License applies to components marked with:

```text
SPDX-License-Identifier: LicenseRef-FluxTuner-Web-NC
```

This includes, but is not limited to:

- `fluxtuner/web/**`;
- web/server templates and static assets;
- web authentication and password hashing;
- server-side web sessions;
- CSRF protection for web mutations;
- first-run web setup;
- web admin-user management;
- web/server API routes;
- web/server deployment and container documentation;
- tests whose names start with `tests/test_web_`.

### Mixed storage boundary

Some core storage files are shared by local interfaces and FluxTuner Web. Their
base local-storage behavior remains MIT-licensed. Web/server-specific user,
profile-ownership, login-attempt, and session-storage behavior introduced for
FluxTuner Web is part of the FluxTuner Web/server feature set and is subject to
the FluxTuner Web Non-Commercial License when used to operate, host, sell, or
monetize web/server functionality.

This preserves the local FluxTuner application as MIT-licensed while preventing
the Web/server multi-user layer from being used as a commercial hosted service
without a separate commercial license.

## Commercial use

Commercial use of FluxTuner Web/server components is not permitted under
`LICENSE-WEB`.

Commercial use includes offering FluxTuner Web or a derivative as SaaS, managed
hosting, a paid hosted radio-library service, subscription access, paid access,
advertising-supported access, commercial support, resale, integration into a paid
product, or operation as part of commercial infrastructure.

For commercial use, obtain a separate written commercial license from the
FluxTuner maintainer or another authorized copyright holder.

## Branding

The software licenses do not grant trademark or branding rights. Forks and hosted
services must not imply that they are official FluxTuner services. Use your own
name and branding unless written permission has been granted.
