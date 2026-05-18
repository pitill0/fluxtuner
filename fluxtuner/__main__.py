from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from fluxtuner import __version__
from fluxtuner.config import get_config_value, set_config_value
from fluxtuner.core.api import normalize_station, search_stations
from fluxtuner.core.cache import clear_search_cache
from fluxtuner.core.favorites import add_favorite, load_favorites, remove_favorite, save_favorites
from fluxtuner.core.manual_playlists import load_playlists, save_playlists
from fluxtuner.core.stations import (
    station_bitrate,
    station_codec,
    station_country,
    station_name,
    station_tags_text,
    station_url,
)
from fluxtuner.players import (
    PLAYER_BACKENDS,
    available_players,
    create_player,
    selected_player_name,
)
from fluxtuner.themes import DEFAULT_THEME, list_themes, theme_exists

console = Console()


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
    stream_url = station_url(station)
    if not stream_url:
        console.print("[red]This station has no playable URL.[/red]")
        return player

    try:
        active_player = player or create_player(player_name)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Could not start player:[/red] {exc}")
        return player

    console.print(f"\n[bold green]Playing:[/bold green] {station['name']}")
    active_player.play(stream_url)
    return active_player


def search_flow(player_name: str | None = None, player: Any | None = None) -> Any | None:
    query = input("Search station by name: ").strip()
    if not query:
        return

    try:
        stations = [normalize_station(item) for item in search_stations(name=query, limit=25)]
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Search failed:[/red] {exc}")
        return

    station = choose_station(stations)
    if not station:
        return

    player = play_station(station, player_name, player)

    save = input("Save to favorites? [y/N]: ").strip().lower()
    if save == "y":
        add_favorite(station)
        console.print("[green]Saved to favorites.[/green]")
    return player


def favorites_flow(player_name: str | None = None, player: Any | None = None) -> Any | None:
    favorites = load_favorites()
    station = choose_station(favorites)
    if not station:
        return

    console.print("\n1. Play")
    console.print("2. Remove from favorites")
    choice = input("> ").strip()

    if choice == "1":
        return play_station(station, player_name, player)
    elif choice == "2":
        remove_favorite(station["url"])
        console.print("[green]Removed from favorites.[/green]")
    return player


def random_favorite_flow(player_name: str | None = None, player: Any | None = None) -> Any | None:
    favorites = load_favorites()
    if not favorites:
        console.print("[yellow]No favorites yet.[/yellow]")
        return

    station = random.choice(favorites)
    console.print(f"[cyan]Random favorite:[/cyan] {station['name']}")
    return play_station(station, player_name, player)


def export_json_list(
    path_value: str,
    items: list[dict[str, Any]],
    label: str,
) -> None:
    export_path = Path(path_value).expanduser()
    export_path.write_text(
        json.dumps(items, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    console.print(f"[green]{label} exported to:[/green] {export_path}")


def import_json_list(
    path_value: str,
    label: str,
) -> list[dict[str, Any]]:
    import_path = Path(path_value).expanduser()

    try:
        data = json.loads(import_path.read_text(encoding="utf-8"))
    except OSError as exc:
        console.print(f"[red]Could not read {label} file:[/red] {exc}")
        raise SystemExit(1) from exc
    except json.JSONDecodeError as exc:
        console.print(f"[red]Invalid {label} JSON:[/red] {exc}")
        raise SystemExit(1) from exc

    if not isinstance(data, list):
        console.print(f"[red]{label.capitalize()} import must be a JSON list.[/red]")
        raise SystemExit(1)

    return data


def run_cli(player_name: str | None = None) -> None:
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
                player = search_flow(player_name, player)
            elif choice == "2":
                player = favorites_flow(player_name, player)
            elif choice == "3":
                player = random_favorite_flow(player_name, player)
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
        "--cli",
        action="store_true",
        help="Run the legacy numbered CLI instead of the default Textual TUI.",
    )

    parser.add_argument(
        "--gui",
        action="store_true",
        help="Run the experimental GTK GUI instead of the default Textual TUI.",
    )
    parser.add_argument(
        "--player",
        default="auto",
        metavar="BACKEND",
        help="Player backend to use: auto, mpv or ffplay.",
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

    args = parser.parse_args()

    if args.list_players:
        console.print("[bold]Supported player backends:[/bold]")

        available = available_players()
        selected = selected_player_name(None) if available else None

        for backend in PLAYER_BACKENDS:
            status = "[green]available[/green]" if backend in available else "[red]missing[/red]"
            default = " [bold cyan](auto)[/bold cyan]" if backend == selected else ""
            console.print(f" - {backend}: {status}{default}")

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
        export_json_list(args.export_favs, load_favorites(), "Favorites")
        return

    if args.import_favs:
        data = import_json_list(args.import_favs, "favorites")
        save_favorites(data)
        console.print(f"[green]Imported {len(data)} favorite(s).[/green]")
        return

    if args.export_playlists:
        export_json_list(args.export_playlists, load_playlists(), "Persistent playlists")
        return

    if args.import_playlists:
        data = import_json_list(args.import_playlists, "playlists")
        save_playlists(data)
        console.print(f"[green]Imported {len(data)} persistent playlist(s).[/green]")
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
        raise SystemExit(2) from exc

    if args.cli:
        run_cli(selected_player)
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
