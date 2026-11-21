# Development

## Repository layout

```
shell/        weston-appliance-shell: the weston shell plugin (stacking by
              rule, per-window rotation, control socket) and
              appliance-screensaver; see shell/README.md
compositor/   the launcher (hooks, config merge, exec weston), the base
              weston.ini, and appliance-touch (the touchscreen mapper)
tests/        appliance-touch decision tests (python3 -m unittest discover -s tests)
audio/        WirePlumber rules for the sound server
packaging/    build-fpk.sh, the FygoOS package skeleton (fpk/), icon generator
docs/         the runtime contract, architecture, installation, this file
```

## Build

```sh
packaging/build-fpk.sh      # → build/appliance-compositor.fpk
```

Needs:
- [`fygopack`](https://developer.fygonas.com/docs/cli/fygopack/), meson and
  ninja;
- the dev headers of the weston it will run under (Debian
  bookworm-backports: `libweston-14-dev weston-dev`);
- `libwayland-dev` and `wayland-protocols`, for appliance-screensaver.

The shell on its own builds with meson; see
[shell/README.md](../shell/README.md).

## The contract comes first

Client apps rely only on [CONTRACT.md](CONTRACT.md): the paths, unit names,
client environment and configuration directories. They never use files of
this repository, so they build and ship on their own.

A change that breaks something the contract promises needs a new contract
version: the `CONTRACT` file in the package, which clients check before they
install.
