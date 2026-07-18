# Release Workflow

This document describes the recommended FluxTuner release process.

FluxTuner is currently released as a Python package and may also include packaging artifacts such as Flatpak builds or validation notes.

## Release goals

A release should ensure that:

- The version number is correct.
- The changelog is updated.
- The package builds successfully.
- CI is green on `main`.
- Security checks pass.
- Release artifacts are reproducible from a clean checkout.
- The GitHub release notes match the shipped changes.

## Versioning

FluxTuner uses semantic versioning where practical:

```text
MAJOR.MINOR.PATCH
```

Examples:

```text
0.2.9
0.3.0
1.0.0
```

General guidance:

- Patch release: bug fixes, hardening, documentation, small internal improvements.
- Minor release: new user-facing features, larger internal improvements, new supported workflows.
- Major release: breaking changes or major architectural changes.

The current package version is defined in:

```text
pyproject.toml
```

Update:

```toml
[project]
version = "x.y.z"
```

## Changelog

Update `CHANGELOG.md` before tagging a release.

Move relevant entries from:

```md
## [Unreleased]
```

into a new version section:

```md
## [x.y.z] - YYYY-MM-DD
```

Recommended categories:

```md
### Added
### Changed
### Fixed
### Security
### Documentation
```

If a category has no entries, omit it from the release section.

After moving entries, reset `Unreleased` to:

```md
## [Unreleased]

### Added

- Nothing yet.

### Changed

- Nothing yet.

### Fixed

- Nothing yet.
```

## Pre-release checklist

Start from an up-to-date, clean `main` branch:

```bash
git switch main
git pull --ff-only
git status --short
```

Create a release branch:

```bash
git switch -c release/x.y.z
```

Update files:

```text
pyproject.toml
CHANGELOG.md
```

Then run the complete release-quality gate and build from a clean artifact
directory:

```bash
make gate
rm -rf build dist *.egg-info
python -m build
```

Check that both distribution artifacts exist, install the generated wheel and
smoke-test the installed commands:

```bash
test -n "$(ls dist/*.tar.gz)"
test -n "$(ls dist/*.whl)"
python -m pip install --force-reinstall dist/*.whl
fluxtuner --version
fluxtuner --help
fluxtuner --list-players
fluxtuner --list-themes
```

## Pull request

Open a release PR from:

```text
release/x.y.z
```

The PR should include:

- Version bump.
- Changelog update.
- Any release documentation updates.
- Validation checklist.

Suggested PR title:

```text
Prepare release x.y.z
```

Suggested PR body:

```md
## Summary

Prepares FluxTuner x.y.z.

Changes include:

- Bump package version to x.y.z.
- Update changelog for x.y.z.

## Validation

- [ ] `make gate`
- [ ] `rm -rf build dist *.egg-info`
- [ ] `python -m build`
- [ ] Wheel installed with `python -m pip install --force-reinstall dist/*.whl`
- [ ] Installed CLI smoke tests passed
```

Merge the PR only after CI is green.

## Tagging

After the release PR is merged and CI is green:

```bash
git switch main
git pull --ff-only
git tag -a vx.y.z -m "FluxTuner x.y.z"
git push origin vx.y.z
```

Example:

```bash
git tag -a v1.0.7 -m "FluxTuner 1.0.7"
git push origin v1.0.7
```

Pushing a version tag triggers the release artifact workflow.

## GitHub release

Create a GitHub release from the tag.

Recommended release title:

```text
FluxTuner x.y.z
```

Recommended release notes:

```md
## Highlights

- ...

## Added

- ...

## Changed

- ...

## Fixed

- ...

## Security

- ...

## Validation

- CI passed on `main`.
- Package artifacts were built from tag `vx.y.z`.
```

Attach generated artifacts from the release workflow if needed.

## Release artifact workflow

The release workflow runs on version tags:

```text
v*
```

It builds Python package artifacts:

```text
dist/*.tar.gz
dist/*.whl
```

The workflow verifies that the pushed tag matches the version declared in
`pyproject.toml`, installs and smoke-tests the generated wheel, uploads both
files as GitHub Actions artifacts and attaches them to the GitHub release.

This workflow does not publish to PyPI automatically. Publishing should remain
manual until credentials, trusted publishing and release ownership are
explicitly configured.

## Flatpak release notes

If the release includes Flatpak changes:

- Review Flatpak permissions.
- Build locally with Flatpak tooling.
- Update any Flatpak validation notes.
- Confirm runtime behavior manually.

Flatpak release automation should be handled separately from the Python package artifact workflow.

## Rollback guidance

If a release has a serious problem:

1. Stop promoting the affected release.
2. Open a fix branch.
3. Patch the issue.
4. Prepare a new patch release.
5. Document the issue in the changelog if relevant.

Avoid force-moving published tags unless the release was never announced and no user could reasonably have consumed it.

## Release gate

Before creating a release tag, run the canonical release-quality gate from a
clean working tree:

```bash
make gate
```

Build, install and smoke-test the release artifacts using the commands in the
pre-release checklist above. Do not create the tag until local validation and
the release pull request CI have both passed.

If `ruff format --check` reports changes, run:

```bash
python -m ruff format .
```

Then commit the formatting changes and restart the release gate before tagging.

