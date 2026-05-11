# FluxTuner Flatpak

Local Flatpak packaging and testing setup for FluxTuner.

## Requirements

### Ubuntu / Xubuntu

```bash
sudo apt install flatpak flatpak-builder \
    xdg-desktop-portal \
    xdg-desktop-portal-gtk \
    gvfs gvfs-fuse \
    fuse3 dbus-user-session
```

### Fedora

```bash
sudo dnf install flatpak flatpak-builder
```

## Install runtimes

```bash
flatpak install flathub org.gnome.Platform//50 org.gnome.Sdk//50
```

## Build locally

From the repository root:

```bash
flatpak-builder --user --install --force-clean \
    build-dir flatpak/io.github.pitill0.Fluxtuner.yml
```

## Run

### GUI

```bash
flatpak run io.github.pitill0.Fluxtuner --gui
```

### TUI

```bash
flatpak run io.github.pitill0.Fluxtuner
```

### List available players

```bash
flatpak run io.github.pitill0.Fluxtuner --list-players
```

## Generate a local `.flatpak` bundle

```bash
flatpak-builder --repo=repo \
    build-dir flatpak/io.github.pitill0.Fluxtuner.yml \
    --force-clean

flatpak build-bundle repo \
    fluxtuner.flatpak \
    io.github.pitill0.Fluxtuner
```

## Install local bundle

```bash
flatpak install --user ./fluxtuner.flatpak
```

## Notes

- GUI and TUI validated on Xubuntu/XFCE (X11).
- GUI and TUI launchers are included.
- Player backend selection is automatic:
  - mpv preferred if available
  - ffplay fallback
- `appstream-compose: false` is currently enabled for local development builds.
- Python dependencies are currently fetched from PyPI during build.
  Flathub submission will require dependency vendoring or proper module definitions.
