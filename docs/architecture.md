# Architecture

What runs, in which order, and where its files live. For how an app uses it,
see the runtime contract, [CONTRACT.md](CONTRACT.md). For the shell plugin
itself (stacking rules, rotation, control socket, screensaver), see
[shell/README.md](../shell/README.md).

## Units

All run as root, from boot (`multi-user.target`).

| unit | runs |
|---|---|
| `appliance-compositor.service` | weston with appliance-shell, through the launcher (below); `Type=notify` via weston's `systemd-notify.so`, so clients start once its socket takes connections |
| `appliance-touch.service` | `bin/appliance-touch run`: binds each touchscreen to its display through udev `WL_OUTPUT`; before the compositor, `PartOf=` it; see [touchscreens.md](touchscreens.md) |
| `appliance-audio.service` | `pipewire`, the sound server |
| `appliance-audio-session.service` | `wireplumber --profile main-systemwide`, the session manager |
| `appliance-audio-pulse.service` | `pipewire-pulse`, for apps that speak the PulseAudio protocol (Chromium/Electron among them) |

The audio units are `BindsTo=` the sound server.

`appliance-compositor.service` never gives up restarting
(`StartLimitIntervalSec=0`). While another program still drives the
displays, weston can't take them over, so the service keeps retrying until
they are free.

## The launcher (`compositor/appliance-compositor`)

Each start:

1. **Check** that no other DRM-backend weston is running, for example an old
   front-panel app with its own. If one is, it exits (status 75), and systemd
   retries.
2. **Hooks:** run the clients' pre-start hooks in
   `/etc/appliance-compositor/pre-start.d/`, 5 s each, while nothing holds
   the displays. Failures are logged and ignored.
3. **Config:** merge the base `compositor/weston.ini` with the clients'
   fragments (`/etc/appliance-compositor/clients.d/*.ini`) into
   `/var/lib/appliance-compositor/weston.ini`.
   - A fragment may contain only `[output]` and `[appliance-rule]` sections,
     plus `[touchscreen]`, which is for appliance-touch and not copied;
     anything else is dropped with a log line.
4. **Shell:** `exec weston` with appliance-shell, on the `wayland-appliance`
   socket.
   - If the shell module is missing, it uses weston's kiosk-shell instead:
     windows show, but without stacking rules or rotation.

Clients find the socket through `client.env`, the only environment they
need:

```
XDG_RUNTIME_DIR=/run/user/0
WAYLAND_DISPLAY=wayland-appliance
```

## Root's runtime directory

weston's and PipeWire's sockets live in `/run/user/0`, where other root
programs look for them (`pactl`, `wpctl`). That directory belongs to root's
user session, which causes two problems:
- Starting root's session (a root SSH login) mounts a fresh tmpfs over it,
  hiding the sockets.
- Ending the session deletes it.

So the package handles it as follows:

- **Linger:** it keeps root's session up from boot (`loginctl enable-linger
  root`), and orders its units after `user-runtime-dir@0.service`.
  - A marker in `/var/lib/appliance-compositor` records that linger was
    turned on by us, so uninstalling only undoes our own change.
- **Masking:** it masks Debian's per-user PipeWire units for root only
  (`/root/.config/systemd/user/`). Otherwise a root login would start a
  second sound server in the same directory.

## Sound

- PipeWire runs system-wide: one server for every app. It keeps its state
  (default output, volumes) in `/var/lib/appliance-compositor/audio`.
- Our WirePlumber rules are in `audio/wireplumber/`. At present they turn off
  the PC-speaker "beeper" card, which is not a real output.
- Bluetooth audio goes through the same server (`libspa-0.2-bluetooth`).

## Files on the system

| path | what |
|---|---|
| `/usr/local/lib/appliance-compositor` | link to the installed package; `CONTRACT`, `client.env`, `bin/appliance-shell-ctl`, `bin/appliance-screensaver`, `bin/appliance-touch` |
| `/etc/appliance-compositor/clients.d/<app>.ini` | the clients' fragments (window rules, output settings) |
| `/etc/appliance-compositor/pre-start.d/<app>` | the clients' hooks |
| `/var/lib/appliance-compositor/weston.ini` | the merged configuration of the last start |
| `/var/lib/appliance-compositor/audio/` | PipeWire / WirePlumber state |
| `/var/lib/appliance-compositor/touch.json` | remembered touchscreen ↔ monitor pairings |
| `/run/udev/rules.d/71-appliance-touch.rules` | appliance-touch's current decisions as udev rules (regenerated; gone at reboot) |
| `/run/user/0/wayland-appliance` | the Wayland socket; `wayland-appliance.appliance-shell` is the shell's control socket |
