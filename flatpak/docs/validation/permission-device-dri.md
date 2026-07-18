# Flatpak `--device=dri` validation

## Purpose

Determine whether FluxTuner can remove `--device=dri` without breaking GTK
rendering, interaction or playback across the supported display environments.

This validation changes only one permission. The previously accepted removal
of `--share=ipc` remains in place, and every other current `finish-args` entry
is unchanged.

## Candidate change

Remove:

    - --device=dri

Retain:

    - --share=network
    - --socket=fallback-x11
    - --socket=wayland
    - --socket=pulseaudio

## Clean build and installation

Close any running instance:

    flatpak kill io.github.pitill0.Fluxtuner 2>/dev/null || true

Remove the user installation, application data and stored overrides:

    flatpak uninstall --user --delete-data \
        io.github.pitill0.Fluxtuner 2>/dev/null || true

    flatpak override --user --reset \
        io.github.pitill0.Fluxtuner 2>/dev/null || true

    flatpak permission-reset \
        io.github.pitill0.Fluxtuner 2>/dev/null || true

    rm -rf ~/.var/app/io.github.pitill0.Fluxtuner

From the repository root, remove all local Flatpak build products:

    rm -rf build-dir .flatpak-builder repo
    rm -f fluxtuner.flatpak

Build and install from scratch:

    flatpak-builder --user --install --force-clean \
        build-dir flatpak/io.github.pitill0.Fluxtuner.yml

Confirm the installed permission set:

    flatpak info --show-permissions io.github.pitill0.Fluxtuner

The output must contain neither `shared=ipc` nor `devices=dri`.

## Required smoke sequence

Run the GUI:

    flatpak run io.github.pitill0.Fluxtuner --gui

For each environment:

1. launch from a terminal;
2. launch from the desktop file;
3. search for stations;
4. scroll the station list repeatedly;
5. resize the window repeatedly, including narrow and wide layouts;
6. inspect row text, icons, selection markers and Now Playing projection;
7. start playback;
8. change volume and mute state;
9. switch between search, favorites, history and a tag playlist;
10. play a random station from a tag;
11. stop playback;
12. close during idle state;
13. relaunch, start playback and close while playback is active;
14. relaunch, start a search and close before it completes;
15. leave playback running for at least ten minutes while scrolling and resizing;
16. inspect terminal output and relevant user-journal messages.

## Rendering checks

Because this candidate removes GPU-device access, specifically verify:

- initial window paint is complete;
- no blank, black or transparent regions appear;
- station rows repaint correctly while scrolling;
- selection and current-station markers update;
- labels do not leave visual artifacts;
- resizing does not corrupt or freeze the interface;
- software-rendering fallback remains responsive;
- suspend/resume does not leave the window unpainted, where practical.

Useful diagnostics:

    journalctl --user --since "15 minutes ago" \
        | grep -Ei \
          'flatpak|fluxtuner|gtk|gdk|gsk|gl|egl|mesa|dri|render|wayland|x11|portal|pipewire|pulse'

Optional verbose run:

    G_MESSAGES_DEBUG=all \
    flatpak run io.github.pitill0.Fluxtuner --gui \
        2>&1 | tee /tmp/fluxtuner-flatpak-no-dri.log

## Validation matrix

| Environment | Display path | Clean build | Permissions checked | Rendering passed | Full smoke passed | Diagnostics | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CRUX | Xorg | passed | passed | passed | passed | no regressions observed | passed |
| CRUX | Wayland | passed | passed | passed | passed | no regressions observed | passed |
| Ubuntu | Xorg | passed | passed | passed | passed | no regressions observed | passed |

## Evidence

The candidate was built and installed cleanly in all three required
environments.

The effective Flatpak permissions contained neither `shared=ipc` nor
`devices=dri`. Network access, X11 fallback, Wayland and PulseAudio remained
available.

The GTK GUI passed terminal and desktop launch, search, rendering, repeated
scrolling and resizing, playback, volume, mute, view transitions, tag-playlist
behavior and shutdown checks.

The extended rendering checks showed no blank or black regions, repaint
artifacts, frozen layouts, corrupt selection markers or responsiveness
regressions. Repeated resizing remained smooth in all three environments.

No reproducible GTK, GDK, GSK, Mesa, rendering, playback or shutdown regression
was observed.

## Acceptance rule

Keep the removal only when all three required environments pass the rendering
checks and complete smoke sequence without a regression attributable to missing
DRI access.

Any reproducible blank window, rendering corruption, severe responsiveness
regression, startup failure or GTK/GDK/GSK crash means restoring
`--device=dri` and recording the failure here.

## Current result

CRUX Xorg, CRUX Wayland and Ubuntu Xorg all passed. The matrix acceptance rule
is satisfied, so removing `--device=dri` is accepted.
