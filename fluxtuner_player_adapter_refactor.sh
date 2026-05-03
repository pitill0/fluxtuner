#!/usr/bin/env bash
set -euo pipefail

# FluxTuner player adapter refactor
# Run from the repository root, ideally on branch dev/gui-foundation.

if [ ! -d "fluxtuner" ] || [ ! -f "fluxtuner/__main__.py" ]; then
  echo "ERROR: run this script from the FluxTuner repository root." >&2
  exit 1
fi

mkdir -p fluxtuner/players

if [ ! -f fluxtuner/players/__init__.py ]; then
  touch fluxtuner/players/__init__.py
fi

cat > fluxtuner/players/base.py <<'PY'
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class PlayerError(RuntimeError):
    """Raised when a player backend cannot be used."""


class PlayerAdapter(ABC):
    """Common interface implemented by all playback backends."""

    @abstractmethod
    def play(self, url: str) -> None:
        """Start playback for a stream URL."""

    @abstractmethod
    def stop(self) -> None:
        """Stop playback."""

    @abstractmethod
    def is_playing(self) -> bool:
        """Return True when the backend has an active playback process/session."""

    @abstractmethod
    def toggle_pause(self) -> None:
        """Toggle pause/resume."""

    @abstractmethod
    def toggle_mute(self) -> None:
        """Toggle mute/unmute."""

    @abstractmethod
    def volume_up(self) -> None:
        """Increase playback volume."""

    @abstractmethod
    def volume_down(self) -> None:
        """Decrease playback volume."""

    @abstractmethod
    def set_volume(self, volume: int | float) -> None:
        """Set playback volume to an absolute value."""

    @abstractmethod
    def set_mute(self, muted: bool) -> None:
        """Set mute to an absolute value."""

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Return a compact playback state snapshot."""
PY

# Move current mpv implementation into the players package if it has not been moved yet.
if [ -f fluxtuner/core/player.py ] && [ ! -f fluxtuner/players/mpv.py ]; then
  git mv fluxtuner/core/player.py fluxtuner/players/mpv.py
fi

if [ ! -f fluxtuner/players/mpv.py ]; then
  echo "ERROR: fluxtuner/players/mpv.py was not found." >&2
  exit 1
fi

python3 - <<'PY'
from pathlib import Path

mpv_path = Path("fluxtuner/players/mpv.py")
text = mpv_path.read_text()

# PlayerError now lives in base.py.
text = text.replace('class PlayerError(RuntimeError):\n    """Raised when the external audio player cannot be used."""\n\n\n', '')

if 'from fluxtuner.players.base import PlayerAdapter, PlayerError' not in text:
    marker = 'from typing import Any\n'
    if marker in text:
        text = text.replace(marker, marker + '\nfrom fluxtuner.players.base import PlayerAdapter, PlayerError\n', 1)
    else:
        text = 'from fluxtuner.players.base import PlayerAdapter, PlayerError\n' + text

text = text.replace('class MpvController:', 'class MpvController(PlayerAdapter):')

mpv_path.write_text(text)

init_path = Path("fluxtuner/players/__init__.py")
init_path.write_text('''from __future__ import annotations\n\nfrom fluxtuner.players.base import PlayerAdapter, PlayerError\nfrom fluxtuner.players.mpv import MpvController\n\n\ndef create_player(name: str = "mpv") -> PlayerAdapter:\n    """Create a playback backend by name."""\n    normalized = name.lower().strip()\n\n    if normalized == "mpv":\n        return MpvController()\n\n    raise PlayerError(f"Unsupported player backend: {name}")\n\n\ndef available_players() -> list[str]:\n    """Return supported player backend names."""\n    return ["mpv"]\n''')

# Update TUI imports and constructor.
tui_path = Path("fluxtuner/tui.py")
if tui_path.exists():
    tui = tui_path.read_text()
    tui = tui.replace(
        'from fluxtuner.core.player import MpvController, PlayerError, ensure_mpv_available',
        'from fluxtuner.players import create_player\nfrom fluxtuner.players.mpv import PlayerError, ensure_mpv_available',
    )
    tui = tui.replace(
        'def __init__(self, theme: str | None = None) -> None:',
        'def __init__(self, theme: str | None = None, player_name: str = "mpv") -> None:',
    )
    tui = tui.replace('self.player = MpvController()', 'self.player = create_player(player_name)')
    tui = tui.replace(
        'def run_tui(theme: str | None = None) -> None:\n    FluxTunerTUI(theme=theme).run()',
        'def run_tui(theme: str | None = None, player_name: str = "mpv") -> None:\n    FluxTunerTUI(theme=theme, player_name=player_name).run()',
    )
    tui_path.write_text(tui)

# Update __main__.py imports, args and TUI call.
main_path = Path("fluxtuner/__main__.py")
main = main_path.read_text()
main = main.replace(
    'from fluxtuner.core.player import PlayerError, ensure_mpv_available, play_stream',
    'from fluxtuner.players import available_players\nfrom fluxtuner.players.mpv import PlayerError, ensure_mpv_available, play_stream',
)

if '"--player"' not in main:
    needle = '''    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the legacy numbered CLI instead of the Textual TUI.",
    )
'''
    replacement = needle + '''    parser.add_argument(
        "--player",
        default="mpv",
        choices=available_players(),
        help="Player backend to use.",
    )
'''
    if needle not in main:
        raise SystemExit("Could not find --cli parser block in fluxtuner/__main__.py")
    main = main.replace(needle, replacement, 1)

main = main.replace('run_tui(theme=selected_theme)', 'run_tui(theme=selected_theme, player_name=args.player)')
main_path.write_text(main)

# Update pyproject package data if themes are still top-level. Do not change package list yet.
PY

echo "Player adapter refactor applied. Review with: git diff"
echo "Then test: python -m fluxtuner --player mpv && python -m fluxtuner --version"
