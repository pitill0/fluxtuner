# Contributing to FluxTuner

Thanks for considering a contribution.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
fluxtuner
```

For the legacy CLI:

```bash
fluxtuner --cli
```

## Before opening a pull request

Please check that:

- The TUI starts with `fluxtuner`.
- `fluxtuner --help` shows the expected commands.
- Theme files still load with `fluxtuner --list-themes`.
- New user-facing text is in English.

## Project direction

FluxTuner aims to remain:

- terminal-first
- keyboard-friendly
- lightweight
- themeable
- respectful of user control during playback
