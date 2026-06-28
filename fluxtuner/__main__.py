from __future__ import annotations

import argparse
import json
import platform
import secrets
import sys
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from fluxtuner import __version__
from fluxtuner.config import get_config_value, set_config_value
from fluxtuner.core.api import normalize_station, search_stations
from fluxtuner.core.cache import clear_search_cache
from fluxtuner.core.compatibility import (
    filter_supported_stations,
    station_is_supported,
    unsupported_station_message,
)
from fluxtuner.core.favorites import add_favorite, load_favorites, remove_favorite, save_favorites
from fluxtuner.core.importers import validate_imported_favorites, validate_imported_playlists
from fluxtuner.core.manual_playlists import load_playlists, save_playlists
from fluxtuner.core.profiles import (
    clear_active_profile_name,
    get_active_profile_name,
    load_profiles,
    resolve_effective_profile_name,
    set_active_profile_name,
)
from fluxtuner.core.stations import (
    station_bitrate,
    station_codec,
    station_country,
    station_name,
    station_tags_text,
    station_url,
)
from fluxtuner.logging_config import configure_logging, get_logger
from fluxtuner.paths import CACHE_DIR, CONFIG_DIR, DATA_DIR
from fluxtuner.players import (
    PLAYER_BACKENDS,
    available_players,
    create_player,
    selected_player_name,
)
from fluxtuner.themes import DEFAULT_THEME, list_themes, theme_exists

console = Console()
logger = get_logger(__name__)


_PLAYER_INSTALL_HINTS = {
    "mpv": "install mpv",
    "ffplay": "install FFmpeg / ffplay",
    "mpg123": "install mpg123",
    "ogg123": "install vorbis-tools / ogg123",
}


def player_install_hint(backend_name: str) -> str:
    """Return a compact install hint for a known backend."""
    return _PLAYER_INSTALL_HINTS.get(backend_name, f"install {backend_name}")


def player_install_help() -> str:
    """Return a compact install help message for missing playback backends."""
    hints = ", ".join(player_install_hint(name) for name in PLAYER_BACKENDS)
    return f"No playback backend is available. Install one of: {hints}."


def path_diagnostic_status(target: Path) -> str:
    """Return a compact status for a diagnostic filesystem path."""
    if target.exists():
        return "present"
    if target.parent.exists():
        return "missing"
    return "parent missing"


def print_player_backend_status() -> None:
    """Print player backend availability and capability details."""
    available = available_players()
    selected = selected_player_name(None) if available else None

    for backend in PLAYER_BACKENDS:
        status = "[green]available[/green]" if backend in available else "[red]missing[/red]"
        default = " [bold cyan](auto)[/bold cyan]" if backend == selected else ""
        summary = player_capabilities_summary(backend)
        install_hint = ""
        if backend not in available:
            install_hint = f" · {player_install_hint(backend)}"
        console.print(f" - {backend}: {status}{default} · {summary}{install_hint}")


def print_profiles() -> None:
    """Print known FluxTuner profiles."""
    profiles = load_profiles()

    table = Table(title="FluxTuner profiles")
    table.add_column("Name")
    table.add_column("Display name")
    table.add_column("Created")
    table.add_column("Updated")

    for profile in profiles:
        table.add_row(
            str(profile["name"]),
            str(profile["display_name"]),
            str(profile["created_at"]),
            str(profile["updated_at"]),
        )

    console.print(table)


def run_doctor() -> None:
    """Print a compact runtime diagnostic report."""
    console.print("[bold]FluxTuner doctor[/bold]")
    console.print(f"Version: {__version__}")
    console.print(f"Python: {sys.version.split()[0]}")
    console.print(f"Platform: {platform.platform()}")

    console.print("\n[bold]Storage paths[/bold]")
    for label, target in (
        ("Config", CONFIG_DIR),
        ("Data", DATA_DIR),
        ("Cache", CACHE_DIR),
    ):
        console.print(f" - {label}: {target} ({path_diagnostic_status(target)})")

    console.print("\n[bold]Player backends[/bold]")
    print_player_backend_status()

    if not available_players():
        console.print(f"\n[yellow]{player_install_help()}[/yellow]")


def backend_capabilities(player_name: str | None):
    backend_name = player_name or selected_player_name(player_name)
    return PLAYER_BACKENDS[backend_name].capabilities()


def compatible_stations_for_player(
    stations: list[dict[str, Any]],
    player_name: str | None,
) -> list[dict[str, Any]]:
    return filter_supported_stations(stations, backend_capabilities(player_name))


def station_supported_by_player(
    station: dict[str, Any],
    player_name: str | None,
    player: Any | None = None,
) -> bool:
    if player is not None and hasattr(player, "capabilities"):
        return station_is_supported(station, player.capabilities())

    if player_name is None:
        return True

    return station_is_supported(station, backend_capabilities(player_name))


def player_capabilities_summary(backend_name: str) -> str:
    """Return a compact human-readable summary for a player backend."""
    capabilities = PLAYER_BACKENDS[backend_name].capabilities()

    backend_type = "general-purpose" if capabilities.general_purpose else "specialized"
    details: list[str] = [backend_type]

    if capabilities.supported_codecs:
        codecs = ", ".join(sorted(capabilities.supported_codecs))
        details.append(f"codecs: {codecs}")

    controls = []
    if capabilities.supports_pause:
        controls.append("pause")
    if capabilities.supports_volume:
        controls.append("volume")
    if capabilities.supports_mute:
        controls.append("mute")

    if controls:
        details.append("controls: " + ", ".join(controls))

    return "; ".join(details)


def print_station_table(stations: list[dict[str, Any]]) -> None:
    table = Table(title="FluxTuner stations")
    table.add_column("#", justify="right")
    table.add_column("Name", overflow="fold")
    table.add_column("Country")
    table.add_column("Codec")
    table.add_column("Bitrate", justify="right")
    table.add_column("Tags", overflow="fold")

    for idx, station in enumerate(stations):
        table.add_row(
            str(idx),
            station_name(station),
            station_country(station),
            station_codec(station),
            str(station_bitrate(station)),
            station_tags_text(station, fallback="")[:80],
        )

    console.print(table)


def choose_station(stations: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not stations:
        console.print("[yellow]No stations available.[/yellow]")
        return None

    print_station_table(stations)
    choice = input("\nSelect station index: ").strip()

    if not choice.isdigit():
        return None

    index = int(choice)
    if index < 0 or index >= len(stations):
        console.print("[red]Invalid index.[/red]")
        return None

    return stations[index]


def play_station(
    station: dict[str, Any],
    player_name: str | None = None,
    player: Any | None = None,
) -> Any | None:
    if not station_supported_by_player(station, player_name, player):
        backend_name = player_name or selected_player_name(player_name)
        console.print(f"[yellow]{unsupported_station_message(station, backend_name)}[/yellow]")
        return player

    stream_url = station_url(station)
    if not stream_url:
        logger.debug("Playback skipped because selected station has no playable URL")
        console.print("[red]This station has no playable URL.[/red]")
        return player

    try:
        active_player = player or create_player(player_name)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not create player backend", exc_info=True)
        console.print(f"[red]Could not start player:[/red] {exc}")
        return player

    logger.debug("Starting playback through selected player backend")
    console.print(f"\n[bold green]Playing:[/bold green] {station['name']}")
    active_player.play(stream_url)
    return active_player


def search_flow(
    player_name: str | None = None,
    player: Any | None = None,
    *,
    profile_name: str | None = None,
) -> Any | None:
    query = input("Search station by name: ").strip()
    if not query:
        return player

    try:
        stations = [normalize_station(item) for item in search_stations(name=query, limit=25)]
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Search failed:[/red] {exc}")
        return player

    compatible_stations = compatible_stations_for_player(stations, player_name)
    unsupported_count = len(stations) - len(compatible_stations)
    if unsupported_count:
        console.print(
            f"[yellow]Filtered {unsupported_count} unsupported station(s) "
            f"for backend {player_name}.[/yellow]"
        )

    station = choose_station(compatible_stations)
    if not station:
        return player

    player = play_station(station, player_name, player)

    save = input("Save to favorites? [y/N]: ").strip().lower()
    if save == "y":
        add_favorite(station, profile_name=profile_name)
        console.print("[green]Saved to favorites.[/green]")
    return player


def favorites_flow(
    player_name: str | None = None,
    player: Any | None = None,
    *,
    profile_name: str | None = None,
) -> Any | None:
    favorites = compatible_stations_for_player(
        load_favorites(profile_name=profile_name),
        player_name,
    )
    if not favorites:
        console.print(f"[yellow]No compatible favorites for backend {player_name}.[/yellow]")
        return player

    station = choose_station(favorites)
    if not station:
        return player

    console.print("\n1. Play")
    console.print("2. Remove from favorites")
    choice = input("> ").strip()

    if choice == "1":
        return play_station(station, player_name, player)
    elif choice == "2":
        remove_favorite(station["url"], profile_name=profile_name)
        console.print("[green]Removed from favorites.[/green]")
    return player


def random_favorite_flow(
    player_name: str | None = None,
    player: Any | None = None,
    *,
    profile_name: str | None = None,
) -> Any | None:
    favorites = compatible_stations_for_player(
        load_favorites(profile_name=profile_name),
        player_name,
    )
    if not favorites:
        console.print(f"[yellow]No compatible favorites for backend {player_name}.[/yellow]")
        return player

    station = secrets.choice(favorites)
    console.print(f"[cyan]Random favorite:[/cyan] {station['name']}")
    return play_station(station, player_name, player)


def export_json_list(
    path_value: str,
    items: list[dict[str, Any]],
    label: str,
) -> None:
    export_path = Path(path_value).expanduser()
    logger.debug("Exporting %s item(s) for %s", len(items), label)

    try:
        export_path.write_text(
            json.dumps(items, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("Export failed for %s", label, exc_info=True)
        console.print(f"[red]Could not export {label.lower()}:[/red] {exc}")
        raise SystemExit(1) from exc

    logger.debug("Export completed for %s", label)
    console.print(f"[green]{label} exported to:[/green] {export_path}")


def import_json_list(
    path_value: str,
    label: str,
) -> list[dict[str, Any]]:
    import_path = Path(path_value).expanduser()
    logger.debug("Importing %s JSON list", label)

    try:
        data = json.loads(import_path.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.debug("Import read failed for %s", label, exc_info=True)
        console.print(f"[red]Could not read {label} file:[/red] {exc}")
        raise SystemExit(1) from exc
    except json.JSONDecodeError as exc:
        logger.debug("Import JSON parsing failed for %s", label, exc_info=True)
        console.print(f"[red]Invalid {label} JSON:[/red] {exc}")
        raise SystemExit(1) from exc

    if not isinstance(data, list):
        logger.debug("Import rejected for %s because JSON root is not a list", label)
        console.print(f"[red]{label.capitalize()} import must be a JSON list.[/red]")
        raise SystemExit(1)

    logger.debug("Imported %s raw item(s) for %s", len(data), label)
    return data


def run_cli(
    player_name: str | None = None,
    *,
    profile_name: str | None = None,
) -> None:
    """Run the legacy numbered CLI with an already resolved player backend."""
    player: Any | None = None

    try:
        while True:
            console.print("\n[bold cyan]FluxTuner CLI[/bold cyan]")
            console.print("1. Search stations")
            console.print("2. Favorites")
            console.print("3. Random favorite")
            console.print("4. Exit")

            choice = input("> ").strip()

            if choice == "1":
                player = search_flow(
                    player_name,
                    player,
                    profile_name=profile_name,
                )
            elif choice == "2":
                player = favorites_flow(
                    player_name,
                    player,
                    profile_name=profile_name,
                )
            elif choice == "3":
                player = random_favorite_flow(
                    player_name,
                    player,
                    profile_name=profile_name,
                )
            elif choice == "4":
                break
            else:
                console.print("[yellow]Unknown option.[/yellow]")
    finally:
        if player is not None:
            player.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description="FluxTuner internet radio player")
    parser.add_argument(
        "--version",
        action="version",
        version=f"FluxTuner {__version__}",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the legacy numbered CLI instead of the default Textual TUI.",
    )

    parser.add_argument(
        "--gui",
        action="store_true",
        help="Run the GTK desktop GUI instead of the default Textual TUI.",
    )
    parser.add_argument(
        "--player",
        default="auto",
        metavar="BACKEND",
        help="Player backend to use: auto, mpv, ffplay, mpg123 or ogg123.",
    )
    parser.add_argument(
        "--profile",
        default=None,
        metavar="NAME",
        help=(
            "Profile name to use for profile-aware commands. "
            "Overrides the persisted active profile."
        ),
    )
    parser.add_argument(
        "--set-active-profile",
        action="store_true",
        help="Persist --profile NAME as the active profile and exit.",
    )
    parser.add_argument(
        "--show-active-profile",
        action="store_true",
        help="Show the persisted active profile and exit.",
    )
    parser.add_argument(
        "--clear-active-profile",
        action="store_true",
        help="Clear the persisted active profile and exit.",
    )
    parser.add_argument(
        "--theme",
        default=None,
        help="Theme to use for this run. Use --list-themes to see available themes.",
    )
    parser.add_argument(
        "--save-theme",
        nargs="?",
        const=True,
        default=False,
        metavar="THEME",
        help=(
            "Persist a theme as the default. Use either '--theme THEME --save-theme' "
            "or '--save-theme THEME'."
        ),
    )
    parser.add_argument(
        "--list-themes",
        action="store_true",
        help="List available themes and exit.",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear cached Radio Browser search results and exit.",
    )
    parser.add_argument(
        "--export-favs",
        metavar="PATH",
        help="Export favorites to a JSON file and exit.",
    )
    parser.add_argument(
        "--import-favs",
        metavar="PATH",
        help="Import favorites from a JSON file and exit.",
    )
    parser.add_argument(
        "--export-playlists",
        metavar="PATH",
        help="Export persistent playlists to a JSON file and exit.",
    )
    parser.add_argument(
        "--import-playlists",
        metavar="PATH",
        help="Import persistent playlists from a JSON file and exit.",
    )
    parser.add_argument(
        "--list-players",
        action="store_true",
        help="List supported and available player backends, then exit.",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="List known FluxTuner profiles and exit.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Print runtime diagnostics for paths and player backends, then exit.",
    )
    parser.add_argument(
        "command",
        nargs="*",
        help=argparse.SUPPRESS,
    )

    args = parser.parse_args()
    configure_logging(verbose=args.verbose)

    if args.command:
        from fluxtuner.web.admin_cli import handle_web_user_command

        if handle_web_user_command(args.command, console=console):
            return
        parser.error("unknown command: " + " ".join(args.command))

    effective_profile_name = resolve_effective_profile_name(args.profile)

    if args.set_active_profile:
        if not args.profile:
            console.print("[red]--set-active-profile requires --profile NAME.[/red]")
            raise SystemExit(1)

        persisted_profile_name = set_active_profile_name(args.profile)
        console.print(f"[green]Active profile set to {persisted_profile_name!r}.[/green]")
        return

    if args.show_active_profile:
        current_profile_name = get_active_profile_name()
        if current_profile_name is None:
            console.print("[yellow]No active profile configured.[/yellow]")
        else:
            console.print(f"Active profile: {current_profile_name}")
        return

    if args.clear_active_profile:
        clear_active_profile_name()
        console.print("[green]Active profile cleared.[/green]")
        return

    if args.list_players:
        console.print("[bold]Supported player backends:[/bold]")
        print_player_backend_status()
        return

    if args.list_profiles:
        print_profiles()
        return

    if args.doctor:
        run_doctor()
        return

    if args.list_themes:
        console.print("Available themes:")
        for theme_name in list_themes():
            console.print(f"- {theme_name}")
        return

    if args.clear_cache:
        clear_search_cache()
        console.print("[green]Search cache cleared.[/green]")
        return

    if args.export_favs:
        export_json_list(
            args.export_favs,
            load_favorites(profile_name=effective_profile_name),
            "Favorites",
        )
        return

    if args.import_favs:
        data = import_json_list(args.import_favs, "favorites")
        result = validate_imported_favorites(data)

        logger.debug(
            "Validated favorites import: accepted=%s skipped=%s",
            len(result.items),
            result.skipped,
        )
        if not result.items:
            console.print("[red]No valid favorites found in import file.[/red]")
            raise SystemExit(1)

        save_favorites(result.items, profile_name=effective_profile_name)

        message = f"[green]Imported {len(result.items)} favorite(s).[/green]"
        if result.skipped:
            message += f" [yellow]Skipped {result.skipped} invalid item(s).[/yellow]"
        console.print(message)
        return

    if args.export_playlists:
        export_json_list(
            args.export_playlists,
            load_playlists(profile_name=effective_profile_name),
            "Persistent playlists",
        )
        return

    if args.import_playlists:
        data = import_json_list(args.import_playlists, "playlists")
        result = validate_imported_playlists(data)
        logger.debug(
            "Validated playlists import: accepted=%s skipped=%s",
            len(result.items),
            result.skipped,
        )

        if not result.items:
            console.print("[red]No valid playlists found in import file.[/red]")
            raise SystemExit(1)

        save_playlists(result.items, profile_name=effective_profile_name)

        message = f"[green]Imported {len(result.items)} persistent playlist(s).[/green]"
        if result.skipped:
            message += f" [yellow]Skipped {result.skipped} invalid item(s).[/yellow]"
        console.print(message)
        return

    configured_theme = str(get_config_value("theme", DEFAULT_THEME))
    selected_theme = args.theme or configured_theme

    if args.theme and not theme_exists(args.theme):
        console.print(
            f"[yellow]Theme '{args.theme}' was not found. Falling back to 'default'.[/yellow]"
        )
        selected_theme = DEFAULT_THEME

    if args.save_theme:
        theme_to_save = args.theme if args.save_theme is True else str(args.save_theme)
        if not theme_to_save:
            console.print("[red]--save-theme requires a theme name or --theme THEME_NAME.[/red]")
            raise SystemExit(2)
        if not theme_exists(theme_to_save):
            console.print(f"[red]Cannot save unknown theme: {theme_to_save}[/red]")
            raise SystemExit(2)
        set_config_value("theme", theme_to_save)
        selected_theme = theme_to_save
        console.print(f"[green]Saved default theme:[/green] {theme_to_save}")

    try:
        selected_player = selected_player_name(args.player)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Player error:[/red] {exc}")
        console.print(f"[yellow]{player_install_help()}[/yellow]")
        raise SystemExit(2) from exc

    if args.cli:
        run_cli(selected_player, profile_name=effective_profile_name)
        return

    if args.gui:
        try:
            from fluxtuner.gui.app import run_gui
        except ImportError as exc:
            console.print(
                "[red]GTK GUI dependencies are not available.[/red]\n"
                "Install FluxTuner with GUI support or run the TUI without --gui."
            )
            raise SystemExit(1) from exc

        run_gui(player_name=selected_player)
        return

    try:
        from fluxtuner.tui import run_tui
    except ImportError as exc:
        console.print(
            "[red]Textual is required to run the TUI.[/red]\n"
            "Install dependencies with: [bold]pip install -r requirements.txt[/bold]\n"
            "Or run the legacy CLI with: [bold]python -m fluxtuner --cli[/bold]"
        )
        raise SystemExit(1) from exc

    run_tui(theme=selected_theme, player_name=selected_player)


if __name__ == "__main__":
    main()
