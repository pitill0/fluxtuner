# Security Policy

## Supported versions

FluxTuner is a local desktop/terminal internet radio application.

At this stage, security fixes are expected to target the latest released version and the current `main` branch. Older versions may not receive dedicated security patches unless the issue is severe and easy to backport.

## Reporting a vulnerability

Please report security issues privately instead of opening a public GitHub issue.

You can report a vulnerability by contacting the project maintainer through the contact methods listed in the repository profile or project documentation.

When reporting a vulnerability, please include:

- A clear description of the issue.
- Steps to reproduce it.
- The affected version or commit.
- Any relevant logs, screenshots, or proof of concept.
- The expected impact.
- Whether the issue is already public.

Please avoid sharing sensitive personal data, private stream URLs, tokens, local file paths, or system-specific secrets unless they are strictly necessary to explain the issue.

## Security scope

The following areas are considered in scope:

- Unsafe handling of external player execution.
- Unsafe stream URL validation.
- Unsafe file import/export handling.
- Unsafe parsing of stream metadata.
- Insecure handling of local configuration, favorites, playlists, history, cache, or usage data.
- Vulnerable dependencies.
- Build, packaging, or release workflow issues that could affect distributed artifacts.
- Flatpak or packaging permissions that are broader than necessary.
- Logs that expose sensitive local paths, stream URLs, or unnecessary user data.

The following areas are usually out of scope unless they expose a concrete security risk:

- General UI bugs.
- Cosmetic issues.
- Feature requests.
- Unsupported operating systems or manually modified installations.
- Problems caused by malicious local users with full access to the same system account.
- Third-party radio streams behaving incorrectly unless FluxTuner handles them unsafely.

## Local data and privacy

FluxTuner stores local user data such as configuration, favorites, playlists, playback history, search cache, and usage statistics.

Security-sensitive handling expectations:

- Local data files should not be corrupted by interrupted writes.
- Imported files should be validated before being persisted.
- Logs should not expose unnecessary local paths, stream URLs, station names, or imported data contents.
- Debug logs should be opt-in through explicit configuration such as `--verbose` or `FLUXTUNER_DEBUG`.
- The application should fail safely when local data files are unreadable or invalid.

## External streams

FluxTuner plays internet radio streams provided by external services or user data.

Security-sensitive handling expectations:

- Stream URLs should be validated before being passed to external player backends.
- Unsupported or unsafe URL schemes should be rejected.
- Stream metadata should be read with explicit limits.
- Malformed stream responses should not crash the application.
- External stream data should not be trusted as safe input.

## External player backends

FluxTuner may launch external player backends such as `mpv` or `ffplay`.

Security-sensitive handling expectations:

- Player executables should be resolved safely.
- Subprocess commands should use argument lists instead of shell strings.
- `shell=True` should not be used for player execution.
- Stream URLs should be validated before being passed to subprocess calls.
- Player failures should be handled without exposing unnecessary user data.

## Dependency security

The project uses automated dependency auditing in CI.

Security-sensitive handling expectations:

- Known vulnerable dependencies should be updated when practical.
- Dependency audit failures should be reviewed before release.
- New dependencies should be justified and kept minimal.

## Responsible disclosure

Please allow reasonable time for investigation and remediation before publicly disclosing a vulnerability.

The maintainer will try to:

- Acknowledge the report.
- Reproduce and assess the issue.
- Prioritize fixes based on severity and impact.
- Credit reporters when appropriate and requested.

## Security hardening already in place

FluxTuner includes several hardening measures:

- CI checks across supported Python versions.
- Package build validation.
- Dependency auditing.
- Static security analysis with Bandit.
- Atomic JSON writes for local user data.
- Validation of imported favorites and playlists.
- Validation of stream URLs before player execution.
- Explicit limits for ICY stream metadata reads.
- Defensive handling of Radio Browser API failures.
- Opt-in debug logging for diagnostics without polluting the user interface.
