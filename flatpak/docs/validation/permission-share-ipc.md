# Flatpak `--share=ipc` validation

## Purpose

Determine whether FluxTuner can remove `--share=ipc` without breaking the GTK
GUI or playback across the supported display environments.

This validation changes only one permission. `--device=dri` and every other
current `finish-args` entry remain unchanged.

## Candidate change

Remove:

```yaml
- --share=ipc
```

Retain:

```yaml
- --share=network
- --socket=fallback-x11
- --socket=wayland
- --socket=pulseaudio
- --device=dri
```

## Build

From the repository root:

```bash
flatpak-builder --user --install --force-clean \
    build-dir flatpak/io.github.pitill0.Fluxtuner.yml
```

Confirm the installed permission set:

```bash
flatpak info --show-permissions io.github.pitill0.Fluxtuner
```

The output must not contain `shared=ipc`.

## Required smoke sequence

Run the GUI:

```bash
flatpak run io.github.pitill0.Fluxtuner --gui
```

For each environment:

1. launch from a terminal;
2. launch from the desktop file;
3. search for stations;
4. scroll and resize the station list repeatedly;
5. start playback;
6. change volume and mute state;
7. switch between search, favorites, history and a tag playlist;
8. stop playback;
9. close during idle state;
10. relaunch, start playback and close while playback is active;
11. relaunch, start a search and close before it completes;
12. inspect terminal output and relevant user-journal messages.

Useful diagnostics:

```bash
journalctl --user --since "10 minutes ago" \
    | grep -Ei 'flatpak|fluxtuner|gtk|gdk|wayland|x11|portal|pipewire|pulse'
```

## Validation matrix

| Environment | Display path | Build/install | Permissions checked | Smoke passed | Diagnostics clean | Result |
| --- | --- | --- | --- | --- | --- | --- |
| CRUX | Xorg | passed | passed | passed | no regressions observed | passed |
| CRUX | Wayland | passed | passed | passed | no regressions observed | passed |
| Ubuntu | Xorg | passed | passed | passed | IBus warnings only, no functional regression | passed |

## Evidence

Record for each run:

- distribution and version;
- desktop environment or compositor;
- `echo "$XDG_SESSION_TYPE"`;
- `flatpak --version`;
- `flatpak-builder --version`;
- relevant `flatpak info --show-permissions` output;
- selected player from `--list-players`;
- any terminal or journal warnings;
- whether software rendering or unusual environment overrides were active.

## Acceptance rule

Keep the removal only when all three required environments pass the same smoke
sequence without a regression attributable to shared IPC.

Any reproducible startup, rendering, interaction, playback or shutdown
regression means restoring `--share=ipc` and recording the failure here.

## Recorded CRUX evidence

The candidate manifest was built and installed successfully on CRUX.

Effective permissions:

```ini
[Context]
shared=network;
sockets=fallback-x11;pulseaudio;wayland;
devices=dri;
```

`shared=ipc` is absent while network, X11 fallback, Wayland, PulseAudio and DRI
remain available.

The GTK GUI completed the required smoke sequence successfully in both Xorg and
Wayland sessions. No startup, rendering, interaction, playback, volume, mute,
view-transition or shutdown regression was observed.

## Recorded Ubuntu Xorg evidence

The candidate manifest was installed from a clean local build on Ubuntu in an
Xorg session.

Effective permissions:

    [Context]
    shared=network;
    sockets=x11;wayland;pulseaudio;fallback-x11;
    devices=dri;

`shared=ipc` is absent. The GTK GUI passed terminal and desktop launch, search,
rendering, scrolling, resizing, playback, volume, mute, view transitions,
tag-playlist behavior and shutdown checks.

The selected packaged backend was `ffplay`; `mpv`, `mpg123` and `ogg123` were
not available inside the sandbox.

Repeated IBus warnings reported an unavailable `PostProcessKeyEvent` D-Bus
property while typing. Text input and the complete smoke sequence continued to
work, and no startup, rendering, playback or shutdown regression was observed.
The warnings are recorded as environmental diagnostic noise rather than a
failure attributable to removing shared IPC.

## Current result

CRUX Xorg, CRUX Wayland and Ubuntu Xorg all passed. The matrix acceptance rule
is satisfied, so removing `--share=ipc` is accepted.
