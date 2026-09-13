#!/usr/bin/env python3
"""Generate the end-launch SMA footprint for a given stackup.

The signal pad has to be the width of the 50 ohm line, and the coplanar
ground has to sit far enough back that the launch is also 50 ohm. Both follow
from the dielectric height, so the footprint is generated rather than drawn
once and left to rot when the stackup changes.

    python3 gen_sma_footprint.py --width 2.95 --gap 2.0
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from line_impedance import cpwg  # noqa: E402
from sexpr import Sym, dumps, num  # noqa: E402

NAME = "SMA_EdgeMount_Generic"
DEST = (pathlib.Path(__file__).resolve().parent.parent / "library"
        / "SWRA117D_RF.pretty" / f"{NAME}.kicad_mod")
UUID = "b1b7b0d2-1a01-5a01-9001-0000000000"
PAD_LEN = 3.5      # how far the pads reach in from the board edge
GND_W = 3.0        # width of each coplanar ground pad


def build(width: float, gap: float, h: float, er: float) -> list:
    z0, _eps = cpwg(width, gap, h, er)
    offset = width / 2 + gap + GND_W / 2          # centre of each ground pad
    span = 2 * offset + GND_W                     # bottom-side ground pad
    edge = offset + GND_W / 2

    def uid(n):
        return [Sym("uuid"), f"{UUID}{n:02d}"]

    def text(kind, value, y, layer, size, prop=True):
        head = [Sym("property"), kind.capitalize(), value] if prop else \
               [Sym("fp_text"), Sym(kind), value]
        return head + [
            [Sym("at"), num(PAD_LEN / 2), num(y), Sym("0")],
            [Sym("layer"), layer], uid(hash(value) % 90),
            [Sym("effects"), [Sym("font"), [Sym("size"), num(size), num(size)],
                              [Sym("thickness"), num(size * 0.15)]]]]

    def line(a, b, layer, w, n):
        return [Sym("fp_line"), [Sym("start"), num(a[0]), num(a[1])],
                [Sym("end"), num(b[0]), num(b[1])],
                [Sym("stroke"), [Sym("width"), num(w)], [Sym("type"), Sym("solid")]],
                [Sym("layer"), layer], uid(n)]

    def pad(number, y, w, layers, n):
        return [Sym("pad"), number, Sym("smd"), Sym("rect"),
                [Sym("at"), num(PAD_LEN / 2), num(y)],
                [Sym("size"), num(PAD_LEN), num(w)],
                [Sym("layers")] + list(layers), uid(n)]

    fp = [Sym("footprint"), NAME,
          [Sym("version"), Sym("20241229")],
          [Sym("generator"), "gen_sma_footprint.py"],
          [Sym("generator_version"), "9.0"],
          [Sym("layer"), "F.Cu"],
          [Sym("descr"),
           f"Generic end-launch (edge-mount) SMA jack, generated for a {h} mm "
           f"substrate (er {er}). Signal pad {width} mm wide to match the 50 ohm "
           f"line; coplanar ground set back {gap} mm, which makes the launch "
           f"{z0:.1f} ohm. Origin sits on the board edge. Pad 1 = signal, pad 2 = "
           f"shell ground: two tabs on top, one solid plane underneath so the "
           f"launch keeps its reference without relying on a zone fill."],
          [Sym("tags"), "SMA edge launch end launch RF connector 50 ohm"],
          [Sym("attr"), Sym("smd")],
          text("reference", "REF**", -(edge + 0.8), "F.SilkS", 1.0),
          text("value", NAME, edge + 0.8, "F.Fab", 1.0),
          text("user", "%R", 0, "F.Fab", 0.8, prop=False)]

    for n, (layer, w) in enumerate((("F.SilkS", 0.12), ("F.Fab", 0.1))):
        fp += [line((-0.2, -edge), (PAD_LEN + 0.6, -edge), layer, w, 10 + n * 4),
               line((-0.2, edge), (PAD_LEN + 0.6, edge), layer, w, 11 + n * 4),
               line((PAD_LEN + 0.6, -edge), (PAD_LEN + 0.6, edge), layer, w, 12 + n * 4)]
    for n, layer in enumerate(("F.CrtYd", "B.CrtYd")):
        fp.append([Sym("fp_rect"),
                   [Sym("start"), num(-0.4), num(-(edge + 0.2))],
                   [Sym("end"), num(PAD_LEN + 0.8), num(edge + 0.2)],
                   [Sym("stroke"), [Sym("width"), num(0.05)], [Sym("type"), Sym("solid")]],
                   [Sym("fill"), Sym("no")], [Sym("layer"), layer], uid(18 + n)])

    fp += [pad("1", 0, width, ("F.Cu", "F.Paste", "F.Mask"), 20),
           pad("2", -offset, GND_W, ("F.Cu", "F.Paste", "F.Mask"), 21),
           pad("2", offset, GND_W, ("F.Cu", "F.Paste", "F.Mask"), 22),
           pad("2", 0, span, ("B.Cu", "B.Paste", "B.Mask"), 23),
           [Sym("embedded_fonts"), Sym("no")]]
    return fp, z0, offset


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=float, required=True, help="signal pad width [mm]")
    ap.add_argument("--gap", type=float, required=True, help="coplanar ground gap [mm]")
    ap.add_argument("--h", type=float, default=1.6, help="dielectric height [mm]")
    ap.add_argument("--er", type=float, default=4.5)
    args = ap.parse_args()
    fp, z0, offset = build(args.width, args.gap, args.h, args.er)
    DEST.write_text(dumps(fp) + "\n")
    print(f"wrote {DEST.name}")
    print(f"  signal pad {args.width} mm, coplanar gap {args.gap} mm -> launch {z0:.1f} ohm")
    print(f"  ground pads at y = +/-{offset} mm, bottom ground pad "
          f"{2 * offset + GND_W:.2f} mm across")


if __name__ == "__main__":
    main()
