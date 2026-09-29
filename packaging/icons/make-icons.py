#!/usr/bin/env python3
"""Generate the appliance-compositor package icon without any imaging
library (adapted from up6-linux-drivers' make-icons.py): a rounded-rectangle
body with a stacked-windows glyph, supersampled for anti-aliasing. FygoOS asks for a
rounded-rect body on a square canvas.

    make-icons.py <package dir> <colour hex> [--chip|--panel] [--ui <ui dir>]

Writes ICON.PNG and ICON_256.PNG (both 256 px: App Center scales ICON.PNG
up, so the nominal 64 px looks blurry) and, with --ui, the desktop entry
icons images/icon_64.png and images/icon_256.png.
`--chip` draws a chip outline instead of the fan (used for t6-drivers);
`--panel` draws the portrait front-panel screen with dashboard tiles
(used for t6-panel)."""
import math, struct, sys, zlib


def png(width, height, rows):
    raw = b"".join(b"\x00" + bytes(r) for r in rows)
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def rounded_rect(x, y, size, radius, margin):
    """1 inside the rounded square, 0 outside."""
    lo, hi = margin, size - margin
    if x < lo or x > hi or y < lo or y > hi:
        return 0
    cx = min(max(x, lo + radius), hi - radius)
    cy = min(max(y, lo + radius), hi - radius)
    return 1 if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2 else 0


def in_rrect(u, v, x0, y0, x1, y1, r):
    """1 inside the rounded rectangle (x0,y0)-(x1,y1), coordinates in 0..1."""
    if u < x0 or u > x1 or v < y0 or v > y1:
        return 0
    cx = min(max(u, x0 + r), x1 - r)
    cy = min(max(v, y0 + r), y1 - r)
    return 1 if (u - cx) ** 2 + (v - cy) ** 2 <= r * r else 0


def stack(x, y, size):
    """White glyph: three windows stacked back to front, the compositor's
    layers. Back ones are outlines, the front one is solid with a title bar."""
    u, v = x / size, y / size
    w, h, step, line = 0.40, 0.29, 0.085, 0.024
    x0, y0 = 0.22, 0.24
    # front window last wins: draw back to front and let nearer windows cover
    ink = 0
    for i in range(3):
        a, b = x0 + i * step, y0 + i * step
        if in_rrect(u, v, a, b, a + w, b + h, 0.04):
            if i == 2:
                bar = in_rrect(u, v, a + line, b + line, a + w - line, b + 0.075, 0.02)
                ink = 0.35 if bar else 1          # title bar knocked out
            else:
                inner = in_rrect(u, v, a + line, b + line, a + w - line, b + h - line, 0.02)
                ink = 0 if inner else 0.85
    return ink


def render(size, colour, glyph, ss=4):
    rgb = tuple(int(colour[i:i + 2], 16) for i in (0, 2, 4))
    dark = tuple(max(0, int(c * 0.72)) for c in rgb)
    rows = []
    n = size * ss
    for py in range(size):
        row = []
        for px in range(size):
            body = ink = 0
            for sy in range(ss):
                for sx in range(ss):
                    x, y = px + (sx + 0.5) / ss, py + (sy + 0.5) / ss
                    b = rounded_rect(x, y, size, size * 0.22, size * 0.04)
                    body += b
                    if b:
                        ink += glyph(x, y, size)
            body /= ss * ss
            ink /= ss * ss
            t = py / size  # vertical gradient
            base = tuple(int(rgb[i] * (1 - t) + dark[i] * t) for i in range(3))
            col = tuple(int(base[i] * (1 - ink) + 255 * ink) for i in range(3))
            row += [*col, int(255 * body)]
        rows.append(row)
    return png(size, size, rows)


def main():
    args = sys.argv[1:]
    out, colour = args[0], args[1].lstrip("#")
    glyph = stack
    targets = [(f"{out}/ICON.PNG", 256), (f"{out}/ICON_256.PNG", 256)]
    if "--ui" in args:
        ui = args[args.index("--ui") + 1]
        targets += [(f"{ui}/images/icon_64.png", 64), (f"{ui}/images/icon_256.png", 256)]
    rendered = {}
    for path, size in targets:
        rendered.setdefault(size, render(size, colour, glyph))
        with open(path, "wb") as f:
            f.write(rendered[size])


if __name__ == "__main__":
    main()
