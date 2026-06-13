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
- Player backend selection is automatic and follows the same priority as the application:
  - `mpv` preferred when available
  - `ffplay` broad fallback
  - `mpg123` lightweight MP3/MPEG fallback
  - `ogg123` lightweight Ogg/Vorbis/Opus/FLAC-style fallback
- The local development manifest does not currently bundle player binaries explicitly.
  Use `flatpak run io.github.pitill0.Fluxtuner --list-players` to confirm which backends are available inside the sandbox.
- `appstream-compose: false` is currently enabled for local development builds.
- The local development manifest may fetch Python dependencies from PyPI during build.
  The Flathub manifest should use vendored or generated dependency modules such as `python3-requirements.json`.

## Sandbox permissions

The Flatpak manifest intentionally keeps sandbox permissions limited to the app's current runtime needs.

Current permissions:

- `--share=network`: required for Radio Browser API requests and internet radio streams.
- `--socket=pulseaudio`: required for audio playback.
- `--socket=wayland`: required for the GTK GUI on Wayland sessions.
- `--socket=fallback-x11`: allows X11 only when Wayland is unavailable.
- `--share=ipc`: kept for compatibility with graphical sessions and toolkit behavior.
- `--device=dri`: kept for GTK/GNOME rendering compatibility.

The manifest does not request broad filesystem access. FluxTuner should store its configuration, cache, history, favorites and playlists through Flatpak-managed application data paths.

Reviewed permissions and environment overrides:

- `--socket=x11` is not requested; `--socket=fallback-x11` plus `--socket=wayland` is preferred.
- `GSK_RENDERER=cairo` is configured by the application when needed instead of being forced by the Flatpak manifest.
- `NO_AT_BRIDGE` is not forced by the Flatpak manifest.
- `GTK_IM_MODULE` is not forced by the Flatpak manifest.

Future permission reviews should specifically test whether `--share=ipc` and `--device=dri` can be removed without breaking the GTK GUI across Wayland/X11 sessions.
