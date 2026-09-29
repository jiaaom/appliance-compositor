# Installing and removing

## Install

Install `appliance-compositor.fpk` from App Center's manual installation, or
with `appcenter-cli install-fpk build/appliance-compositor.fpk`. Apps that
depend on it (`install_dep_apps`) get it installed first.

Before anything is copied, the install checks the system packages. It installs
missing or outdated ones from **Debian bookworm-backports**:

| needs | why |
|---|---|
| weston ≥ 14 | appliance-shell is built against libweston 14 (Debian 12 itself has 10) |
| Mesa ≥ 24 (`libgl1-mesa-dri libegl-mesa0 libglx-mesa0 libgbm1`) | Debian 12's Mesa 22.3 doesn't know current Intel GPUs (e.g. Meteor Lake), and everything would render in software |
| PipeWire, WirePlumber, pipewire-pulse, `libspa-0.2-bluetooth` | the sound server |

- apt waits for another apt run instead of failing on its lock, and refreshes
  the package lists once if the first attempt fails.
- Its output goes to the journal: `journalctl -t appliance-compositor-apt`.
- When an automatic install fails, App Center's error dialog names the
  missing package and the command to run over SSH.

**The install is refused next to PulseAudio.** A second sound server would
fight PipeWire over the same cards and Bluetooth. Other apps sometimes install
PulseAudio (for example Bluetooth or audio-player apps). Remove the app that
installed it, or `apt purge pulseaudio`, and install again.

## Remove

- **The uninstall is refused while apps are registered in
  `/etc/appliance-compositor/clients.d/`.** The error names them; uninstall
  those first.
- Otherwise it:
  - stops and removes its units;
  - unmasks root's per-user PipeWire units;
  - turns root's linger off, if it turned it on;
  - removes `/etc/appliance-compositor` and `/var/lib/appliance-compositor`
    completely.
- The system packages (weston, Mesa, PipeWire) stay installed.

## Upgrade

App Center's command line can't upgrade an app that is already installed:
`install-fpk` of a newer version only answers "is installed".

- **Releases:** upgrade with a manual installation of the new `.fpk` from the
  App Center web UI.
- **Test builds:** copy the files into `/usr/local/apps/@appcenter/appliance-compositor/`
  and `systemctl restart appliance-compositor` (which also restarts every
  client window).

## Taking over from T6 Front Panel ≤ 1.4

Before this package existed, T6 Front Panel ran its own weston and the same
PipeWire trio (`t6-audio`, `t6-audio-session`, `t6-audio-pulse`). Installing
Appliance Compositor next to such a panel:

- **Replaces its audio units.** They run the same programs in the same runtime
  directory, so running clients reconnect.
- **Keeps its sound state:** default output and volumes, from
  `/var/lib/t6-paneld/audio`.
- **Adopts its root-linger marker.**
- **Doesn't start a second weston** while the old panel's own weston still
  drives the displays. `appliance-compositor.service` keeps retrying until
  the panel is upgraded to a version that is a client of this package.
