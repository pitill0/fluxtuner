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

### CRUX Linux

On CRUX, disable `rofiles-fuse` when running `flatpak-builder`:

```bash
flatpak-builder \
    --disable-rofiles-fuse \
    --user \
    --install \
    --force-clean \
    build-dir \
    flatpak/io.github.pitill0.Fluxtuner.yml
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
- Local stream recording is available in the TUI and GTK GUI when `ffmpeg` is
  available inside the sandbox. The GNOME runtime currently exposes `ffmpeg`,
  but this should still be verified when changing runtime versions.
- Python dependencies are installed from the checked-in
  `python3-requirements.json` module using pinned source URLs and checksums.
  Flatpak builds should not resolve application dependencies from the network
  through `pip`.
- AppStream metadata is installed and validated as part of the Flatpak build.

## Sandbox permissions

The Flatpak manifest intentionally keeps sandbox permissions limited to the app's current runtime needs.

Current permissions:

- `--share=network`: required for Radio Browser API requests and internet radio streams.
- `--socket=pulseaudio`: required for audio playback.
- `--socket=wayland`: required for the GTK GUI on Wayland sessions.
- `--socket=fallback-x11`: allows X11 only when Wayland is unavailable.

`--share=ipc` was removed after successful validation on CRUX Xorg, CRUX
Wayland and Ubuntu Xorg. See `docs/validation/permission-share-ipc.md`.

`--device=dri` was removed after successful rendering and smoke validation on
CRUX Xorg, CRUX Wayland and Ubuntu Xorg. See
`docs/validation/permission-device-dri.md`.

The manifest does not request broad filesystem access. FluxTuner should store its configuration, cache, SQLite library database and local recordings through Flatpak-managed application data paths. The library database contains favorites, playback history, manual playlists and recording metadata. Recorded media files are stored under the app-specific Flatpak data directory in `fluxtuner/recordings/`.

Reviewed permissions and environment overrides:

- `--socket=x11` is not requested; `--socket=fallback-x11` plus `--socket=wayland` is preferred.
- `GSK_RENDERER=cairo` is configured by the application when needed instead of being forced by the Flatpak manifest.
- `NO_AT_BRIDGE` is not forced by the Flatpak manifest.
- `GTK_IM_MODULE` is not forced by the Flatpak manifest.

Permission reductions are validated independently across CRUX Xorg, CRUX Wayland and Ubuntu Xorg before acceptance.
