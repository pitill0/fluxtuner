from __future__ import annotations

import random
from typing import Any

from rich.console import Console
from rich.table import Table

from fluxtuner.core.api import search_stations
from fluxtuner.core.favorites import add_favorite, load_favorites, remove_favorite
from fluxtuner.core.player import PlayerError, ensure_mpv_available, play_stream

console = Console()


def normalize_station(station: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": station.get("name") or "Unknown station",
        "url": station.get("url_resolved") or station.get("url") or "",
        "country": station.get("country") or "Unknown",
        "tags": station.get("tags") or "",
        "codec": station.get("codec") or "",
        "bitrate": station.get("bitrate") or 0,
    }


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
    except Exception as exc:
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


def main() -> None:
    try:
        ensure_mpv_available()
    except PlayerError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc

    while True:
        console.print("\n[bold cyan]FluxTuner[/bold cyan]")
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


if __name__ == "__main__":
    main()
