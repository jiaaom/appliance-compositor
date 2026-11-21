# appliance-compositor — runtime contract (version 1)

Everything a client package (a front-panel app, a TV app, …) may rely on.
Clients use **only** what is written here — no files, scripts or build
outputs of this repository — so they build without it and keep working
across its releases while the contract version stays the same.

The contract version is `1`. It changes only when something below changes
incompatibly; additions keep the number.

## What it provides

One Wayland compositor (weston + weston-appliance-shell) driving **every**
display of the machine, and one system-wide sound server (PipeWire). Clients
are ordinary Wayland / PipeWire clients running as root. There is no web UI.

Only one process can drive a GPU's displays (DRM master), so two apps that
each started their own compositor could never share a machine; with this
package they are windows on the same compositor, placed by rule.

## Installed paths

| path | what |
|---|---|
| `/usr/local/lib/appliance-compositor/` | stable link to the installed package |
| `…/CONTRACT` | the contract version, one line (`1`) |
| `…/client.env` | the client environment below, `KEY=value` lines (systemd `EnvironmentFile=`, or `set -a; . file`) |
| `…/bin/appliance-shell-ctl` | control-socket client (see `shell/README.md`, "Control socket") |
| `…/bin/appliance-screensaver` | black input-catching screen (see `shell/README.md`) |
| `…/bin/appliance-touch` | touchscreen mapper: `status [--json]`, `forget` (see `docs/touchscreens.md`); since 1.2.0 |
| `/etc/appliance-compositor/clients.d/` | per-client compositor config (below) |
| `/etc/appliance-compositor/pre-start.d/` | per-client hooks run before the compositor takes the displays (below) |

`/etc/appliance-compositor/` is removed when appliance-compositor is
uninstalled. A client removes its own files there when it is uninstalled.

## Client environment (`client.env`)

```
XDG_RUNTIME_DIR=/run/user/0
WAYLAND_DISPLAY=wayland-appliance
```

- Wayland socket: `/run/user/0/wayland-appliance`.
- Shell control socket: `/run/user/0/wayland-appliance.appliance-shell`
  (mode 0600, root).
- PipeWire: `/run/user/0/pipewire-0`; PulseAudio protocol (for Chromium /
  Electron, pactl): `/run/user/0/pulse/native`. PipeWire tools (`wpctl`,
  `pw-dump`) and PulseAudio clients find them through `XDG_RUNTIME_DIR`.

`/run/user/0` is root's session runtime dir. appliance-compositor keeps
root's session alive from boot (`loginctl enable-linger root`) so the
directory is mounted once and never hidden or removed by a later root login.

## systemd units

| unit | role |
|---|---|
| `appliance-compositor.service` | weston. `Type=notify`: active once the socket accepts clients |
| `appliance-touch.service` | binds each touchscreen to its display (since 1.2.0); started and restarted with the compositor |
| `appliance-audio.service` | PipeWire |
| `appliance-audio-session.service` | WirePlumber (session manager, system-wide profile) |
| `appliance-audio-pulse.service` | pipewire-pulse (PulseAudio protocol) |

A client unit that shows windows:

```ini
[Unit]
Requires=appliance-compositor.service
After=appliance-compositor.service
# restart with the compositor (a compositor restart closes every window)
PartOf=appliance-compositor.service

[Service]
EnvironmentFile=/usr/local/lib/appliance-compositor/client.env
```

and for sound `Wants=`/`After=appliance-audio-pulse.service`.

`systemctl restart appliance-compositor` re-reads `clients.d/` and re-runs
`pre-start.d/`; clients with `PartOf=` come back with it.

## `clients.d/<client>.ini`

weston.ini fragments, one file per client package, named after it. Only
these section types are allowed; anything else is ignored with a warning:

- `[appliance-rule]` — window placement for the client's app-ids (keys in
  `shell/README.md`: `app-id`, `layer`, `rotation`, `focusable`,
  `focus-priority`, `output`, `output-fallback`).
- `[output]` — settings for an output the client owns (weston's keys:
  `name`, `scale`, `transform`, `mode`, …).
- `[touchscreen]` (since 1.2.0) — which output a touchscreen is on:
  `name=` (glob on the input device name) and/or
  `usb=vendor:product[:serial]`, and `output=` (an output name, or `none`).
  Read by `appliance-touch`, not passed to weston; older compositors drop it
  with a warning.

Touchscreens: the compositor binds each touchscreen to a display by itself
when it can tell which one it is (an external touch monitor next to a
built-in panel needs no configuration; see `docs/touchscreens.md`). A client
that owns a built-in touchscreen declares it with `[touchscreen]`, so the
compositor never hands that display to another touchscreen. An existing udev
rule that sets `WL_OUTPUT` is respected as well.

Layer numbers: `0–49` clients' normal windows, `50–99` overlays, `100` and up
screensavers. A client that runs `appliance-screensaver` for its own screen
gives it its own app-id (`--app-id`) and a rule `layer=100` + `output=`; the
compositor's base rule for the default app-id `screensaver` has no output.

Keyboard focus: there is one keyboard (and remote) for all screens. It goes
to the visible focusable window with the highest `focus-priority` (default
0), the topmost among equals. The stack spans every output, so without a
priority a screensaver on one screen would take the keys from an app on
another. Priorities: `0` default (front panels, their players and
screensavers), `10` an app that owns the remote while it runs (a TV app).
Touching a window never moves the focus. Older compositors ignore the key.

Outputs that come and go (a TV): a rule with `output-fallback=none` keeps
the window hidden while its output is not connected, instead of opening it
on the default output (another app's screen). To move an app to another
output without restarting the compositor, write the new fragment (for the
next start) and send `set-output <app-id> <output>` on the control socket.
A compositor without it answers `{"ok":false,"error":"unknown command"}`:
fall back to restarting `appliance-compositor.service`.

The compositor merges its own base config with all fragments (sorted by
file name) into the weston.ini it starts with. A client's install writes its
fragment and restarts the compositor; its uninstall deletes the fragment.

## `pre-start.d/<client>`

Executables, run as root in file-name order before weston starts, while no
one holds DRM master — the only moment e.g. a connector's "Broadcast RGB"
property can be set. Keep them short (≤ 5 s each); a failing or slow hook is
logged and skipped, never blocks the compositor.

## Audio

WirePlumber keeps its state (default output, volumes) in
`/var/lib/appliance-compositor/audio`. Clients may change the default output
and volumes (e.g. `wpctl`), or route their own streams (PulseAudio
`PULSE_SINK`, Chromium `setSinkId`). PulseAudio (the daemon) must not be
installed alongside; the compositor refuses to install next to it.

## Requirements it takes care of

weston ≥ 14 (Debian bookworm-backports), Mesa ≥ 24 GL stack (for current
Intel GPUs), PipeWire from bookworm-backports — installed at install time
from apt, with a message naming the command when that fails.
