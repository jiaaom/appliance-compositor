# Touchscreens

How appliance-compositor decides which display each touchscreen belongs to,
and how an app or an administrator can tell it.

## The problem

A touchscreen reports only where on its own surface it was touched, as
coordinates from 0 to 1. To turn that into a point on screen, the compositor
has to know which display (output) that surface covers. weston reads this
from the udev property `WL_OUTPUT` of the input device. udev is Linux's
device manager, and its rules can attach such properties to a device. The
value is an output name such as `DP-2`, and weston reads it only once, when
the device appears. A touchscreen without `WL_OUTPUT` is bound to weston's
first output.

On a machine with a built-in touch panel, the first output is usually that
panel. An external touch monitor plugged in later therefore steered the
built-in screen: you touched the external monitor, and the touch landed on
the panel. This was first seen with a USB touch monitor on DP-2 next to the
T6's built-in screen (HDMI-A-1). Apps could each install their own udev rule,
but they cannot know about each other or about monitors plugged in later,
and the rules pile up. So the compositor package now decides for every
touchscreen in one place.

## appliance-touch

`appliance-touch.service` runs `bin/appliance-touch run`. It starts before
weston and is restarted together with it. It watches input and display
hot-plugs, and on each one it:

1. lists the touchscreens, grouping each with the other input nodes of the
   same physical device: a USB touch monitor often also has a mouse or pen
   interface, and weston binds those to an output in the same way;
2. lists the connected displays, identified by their EDID (the identity data
   a monitor reports: maker, model, serial number);
3. decides an output for every touchscreen (below);
4. writes the decisions as udev rules to
   `/run/udev/rules.d/71-appliance-touch.rules`;
5. replays a remove + add uevent for each input node whose binding changed.
   weston (through libinput) then drops the device and adds it again, and
   reads the new `WL_OUTPUT`. weston keeps running, and no window closes.

`/run` is in memory, so the rules disappear at reboot and are written again
at start-up. USB devices with a serial number are matched by vendor, product
and serial number; others by their device path. A remembered USB device
keeps its rule while it is unplugged, so when it is plugged in again udev
binds it at once, before weston opens it, and no replay is needed.

## Decisions, in order

| # | name | when | result |
|---|---|---|---|
| 1 | udev rule | another udev rule (an app's or the administrator's) already sets `WL_OUTPUT` | respected; that output counts as taken |
| 2 | config | a `[touchscreen]` section in `clients.d/*.ini` matches the device | the configured output |
| 3 | remembered | the device was paired with a monitor before | that monitor's connector now, wherever it is plugged in; while the monitor is not connected, no output |
| 4 | only free display | exactly one touchscreen is left, and exactly one connected display has no touchscreen | paired; remembered (#3) only if the two were plugged in together (below) |
| – | no free display | every connected display already has its touchscreen | no output |
| – | ambiguous | anything else | left to weston (its first output), as before |

"No output" means `WL_OUTPUT=none`. No connector has that name, so weston
leaves the device unbound and drops its touches. This is better than
steering another screen. A typical case is a touch monitor whose USB stays
connected while its screen is switched off or unplugged. When the monitor
comes back, weston binds the device by name without waiting for the mapper.

Rule 4 covers the common case of one external touch monitor and needs no
configuration. With two or more candidates (a touch monitor and a TV both
connected for the first time), the mapper cannot tell which one has the
touch layer. Configure it in that case, or plug the touch monitor in once
while the TV is off, so that rule 4 applies and the pairing is remembered;
after that rule 3 applies. A later version may offer "touch this screen"
identification.

### Remembering only what was plugged in together

Rule 4 can also be a coincidence. Take a NAS driving a TV, with a touch
monitor's USB cable plugged in while its video cable is not (or goes to
another computer). There is one loose touchscreen and one free display, so
rule 4 pairs the touchscreen with the TV. If that pairing were remembered,
rule 3 would keep it even after the monitor's video is connected, until
someone ran `appliance-touch forget`.

So a rule-4 pairing is used right away but remembered only when the daemon
saw the touchscreen and the display appear within 15 seconds of each other.
That is what plugging in a touch monitor looks like: its touch controller is
usually powered by the monitor, or both cables go in at once. The first
monitor this was tested with, for example, showed its USB touch device about
one second after its DisplayPort. Devices already present when the daemon
starts (at boot) have no known time, so a pairing made then works but is not
remembered; it is simply made again on the next start, as long as the
situation is still unambiguous.

Pairings are remembered in `/var/lib/appliance-compositor/touch.json`.
Devices are keyed by USB vendor, product and serial number (or the device
path when there is no serial), and monitors by their EDID. A pairing
therefore survives reboots and moving the cable to another port. A
monitor without EDID is paired but never remembered.

## Configuration: `[touchscreen]`

In a client's fragment (`/etc/appliance-compositor/clients.d/<client>.ini`,
see [CONTRACT.md](CONTRACT.md)), or in an administrator's own fragment there:

```ini
[touchscreen]
# which device: name= (a glob on the input device name, as listed by
# `appliance-touch status` or /proc/bus/input/devices) and/or
# usb=vendor:product[:serial] (hex, as in lsusb)
name=FT8722 *
# the output it is on, or none
output=HDMI-A-1
```

- Sections are matched in file-name order. The first match wins.
- Every configured `output=` counts as taken, even while its device is
  unplugged, so rule 4 never gives that display to another touchscreen.
- `output=none` turns a touchscreen off for the compositor.
- Changes take effect on the next hot-plug, on `systemctl reload
  appliance-touch`, or when the compositor restarts.
- Compositors before 1.2.0 ignore the section (they log that it was
  dropped).

## Commands

```sh
appliance-touch status          # devices, displays, decisions and why
appliance-touch status --json   # the same, for programs
appliance-touch forget all      # drop remembered pairings (or one device id)
```

(`/usr/local/lib/appliance-compositor/bin/appliance-touch`). `journalctl -u
appliance-touch` logs every change of decision, and weston's log (`journalctl
-u appliance-compositor`) shows the result as `associating input device
eventN with output X (X by udev)`.

## Limits

- Output names are the kernel's connector names (`DP-2`, `HDMI-A-1`), which
  weston uses too. With more than one GPU the names can repeat. That case is
  not handled yet.
- A touchscreen is recognised by udev's `ID_INPUT_TOUCHSCREEN`. Graphics
  tablets are not mapped.
- The mapper respects foreign `WL_OUTPUT` rules. To let it decide for a
  device instead, remove that rule.
