from __future__ import annotations

import argparse
import random
from typing import Any

from rich.console import Console
from rich.table import Table

from fluxtuner.core.api import normalize_station, search_stations
from fluxtuner.core.favorites import add_favorite, load_favorites, remove_favorite
from fluxtuner.core.cache import clear_search_cache
from fluxtuner.core.player import PlayerError, ensure_mpv_available, play_stream
from fluxtuner.config import get_config_value, set_config_value
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
            station["name"],
            station["country"],
            station["codec"],
            str(station["bitrate"]),
            station["tags"][:80],
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


def play_station(station: dict[str, Any]) -> None:
    if not station.get("url"):
        console.print("[red]This station has no playable URL.[/red]")
        return

    console.print(f"\n[bold green]Playing:[/bold green] {station['name']}")
    play_stream(station["url"])


def search_flow() -> None:
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

    play_station(station)

    save = input("Save to favorites? [y/N]: ").strip().lower()
    if save == "y":
        add_favorite(station)
        console.print("[green]Saved to favorites.[/green]")


def favorites_flow() -> None:
    favorites = load_favorites()
    station = choose_station(favorites)
    if not station:
        return

    console.print("\n1. Play")
    console.print("2. Remove from favorites")
    choice = input("> ").strip()

    if choice == "1":
        play_station(station)
    elif choice == "2":
        remove_favorite(station["url"])
        console.print("[green]Removed from favorites.[/green]")


def random_favorite_flow() -> None:
    favorites = load_favorites()
    if not favorites:
        console.print("[yellow]No favorites yet.[/yellow]")
        return

    station = random.choice(favorites)
    console.print(f"[cyan]Random favorite:[/cyan] {station['name']}")
    play_station(station)


def run_cli() -> None:
    while True:
        console.print("\n[bold cyan]FluxTuner CLI[/bold cyan]")
        console.print("1. Search stations")
        console.print("2. Favorites")
        console.print("3. Random favorite")
        console.print("4. Exit")

        choice = input("> ").strip()

        if choice == "1":
            search_flow()
        elif choice == "2":
            favorites_flow()
        elif choice == "3":
            random_favorite_flow()
        elif choice == "4":
            break
        else:
            console.print("[yellow]Unknown option.[/yellow]")


def main() -> None:
    parser = argparse.ArgumentParser(description="FluxTuner internet radio player")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run the legacy numbered CLI instead of the Textual TUI.",
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
    args = parser.parse_args()

    if args.list_themes:
        console.print("Available themes:")
        for theme_name in list_themes():
            console.print(f"- {theme_name}")
        return

    if args.clear_cache:
        clear_search_cache()
        console.print("[green]Search cache cleared.[/green]")
        return

    configured_theme = str(get_config_value("theme", DEFAULT_THEME))
    selected_theme = args.theme or configured_theme

    if args.theme and not theme_exists(args.theme):
        console.print(f"[yellow]Theme '{args.theme}' was not found. Falling back to 'default'.[/yellow]")
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
        ensure_mpv_available()
    except PlayerError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc

    if args.cli:
        run_cli()
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

    run_tui(theme=selected_theme)


if __name__ == "__main__":
    main()
