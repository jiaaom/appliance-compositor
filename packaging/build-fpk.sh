#!/bin/bash
# Build appliance-compositor.fpk (FygoOS package) into build/.
#
#   packaging/build-fpk.sh
#
# Needs: fygopack; meson, ninja and the dev headers of the weston it will run
# under (Debian bookworm-backports: libweston-14-dev, weston-dev), plus
# libwayland-dev and wayland-protocols for appliance-screensaver.
set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)   # packaging/
REPO=$(dirname "$SCRIPT_DIR")
BUILD_DIR=$REPO/build
NAME=appliance-compositor
CONTRACT=1   # docs/CONTRACT.md

log() { printf '==> %s\n' "$*"; }
die() { printf 'error: %s\n' "$*" >&2; exit 1; }

command -v fygopack >/dev/null || die "fygopack not found (https://developer.fygonas.com/docs/cli/fygopack/)"
command -v meson >/dev/null && command -v ninja >/dev/null || die "meson and ninja are needed"

dst=$BUILD_DIR/fpk/$NAME
rm -rf "$dst"
mkdir -p "$BUILD_DIR/fpk"
cp -r "$SCRIPT_DIR/fpk/$NAME" "$dst"
app=$dst/app
mkdir -p "$app/bin" "$app/shell" "$app/compositor" "$app/audio/config"

# weston-appliance-shell: the shell module and the screensaver client.
log "building weston-appliance-shell"
bdir=$BUILD_DIR/shell
rm -rf "$bdir"
{ meson setup "$bdir" "$REPO/shell" --buildtype=release && ninja -C "$bdir"; } >/dev/null \
    || die "weston-appliance-shell build failed"
cp "$bdir/appliance-shell.so" "$REPO/shell/LICENSE" "$app/shell/"
cp "$bdir/appliance-screensaver" "$REPO/shell/tools/appliance-shell-ctl" "$app/bin/"

# The touchscreen mapper (appliance-touch.service), after its tests.
log "testing appliance-touch"
python3 -m unittest discover -s "$REPO/tests" >/dev/null 2>&1 \
    || die "appliance-touch tests failed (python3 -m unittest discover -s tests)"
cp "$REPO/compositor/appliance-touch" "$app/bin/"

# The launcher and its base config, the WirePlumber rules.
cp "$REPO/compositor/appliance-compositor" "$REPO/compositor/weston.ini" "$app/compositor/"
cp -r "$REPO/audio/wireplumber" "$app/audio/config/"

# Contract files clients read (docs/CONTRACT.md).
echo "$CONTRACT" > "$app/CONTRACT"
printf 'XDG_RUNTIME_DIR=/run/user/0\nWAYLAND_DISPLAY=wayland-appliance\n' > "$app/client.env"
cp "$REPO/docs/CONTRACT.md" "$app/"

# Plain permissions (the source tree may carry odd ones, e.g. from ACLs).
find "$dst" -type d -exec chmod 755 {} +
find "$dst" -type f -exec chmod 644 {} +
chmod 755 "$dst"/cmd/* "$app/compositor/appliance-compositor" "$app/bin/"*

log "packing $NAME $(sed -n 's/^version="\(.*\)"/\1/p' "$dst/manifest")"
(cd "$BUILD_DIR" && fygopack build --directory "$dst" >/dev/null) || die "fygopack build failed"
ls -l "$BUILD_DIR/$NAME.fpk"
