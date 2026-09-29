# appliance-compositor

The shared display and sound server for screen apps on a FygoOS / fnOS.
It is one Wayland compositor (weston with appliance-shell) on every display
of the machine, and one PipeWire sound server.

It has no window or web UI of its own. Apps that depend on it, such as a
front-panel UI or a TV app, appear as its windows, each placed by rule on the
display it belongs to.

## Why

Only one program can drive a GPU's displays. Two screen apps that each
started their own compositor could never run on the same machine. With a
shared compositor, they are just two of its clients: a front panel on the
built-in screen and a TV app on the HDMI output, side by side.

## Features

- **Windows placed by rule:** on a chosen output, in a stacking layer (a
  video player above a UI, a screensaver above everything), and optionally
  rotated. See [shell/README.md](shell/README.md).
- **Apps stay independent:** each drops a small config fragment and an
  optional hook into `/etc/appliance-compositor/`, and ships on its own.
- **One sound server for everything**, Bluetooth included, with state kept
  across reboots.
- **A screensaver client** (`appliance-screensaver`) and a control tool
  (`appliance-shell-ctl`) for the apps' supervisors.

## Requirements

- FygoOS / fnOS 1.2 or newer (Debian 12).
- An Intel GPU: Meteor Lake and newer are tested, other GPUs later.
- weston 14, Mesa 24 and PipeWire. The install gets them from Debian
  bookworm-backports when they are missing.
- Not PulseAudio: the install is refused while it is present.

## Install

From App Center's manual installation.

Details: [docs/installation.md](docs/installation.md).

## Using it from an app

Read **[docs/CONTRACT.md](docs/CONTRACT.md)**, the runtime contract. In
short, an app:

1. runs its windows with
   `EnvironmentFile=/usr/local/lib/appliance-compositor/client.env`, and
   `Requires=` / `PartOf=appliance-compositor.service`;
2. puts its window rules and output settings in
   `/etc/appliance-compositor/clients.d/<app>.ini`;
3. optionally adds a hook in `/etc/appliance-compositor/pre-start.d/<app>`.

## Build

```sh
packaging/build-fpk.sh      # → build/appliance-compositor.fpk
```

Needs [`fygopack`](https://developer.fygonas.com/docs/cli/fygopack/), meson,
ninja, and the weston 14 dev headers. See
[docs/development.md](docs/development.md).

## Documentation

- [CONTRACT.md](docs/CONTRACT.md): what client apps may rely on.
- [Architecture](docs/architecture.md): the units, the launcher, root's
  runtime directory, sound, files on the system.
- [Installation](docs/installation.md): system packages, removal,
  upgrades, taking over from T6 Front Panel ≤ 1.4.
- [Development](docs/development.md): repository layout, build.
- [shell/README.md](shell/README.md): the weston shell plugin and the
  screensaver.

## License

MIT (see `LICENSE`). The shell is derived from weston's kiosk-shell.
