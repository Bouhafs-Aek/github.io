#!/usr/bin/env python3
"""Generate the through-hole SMA jack that DN024's reference board uses.

SWRA227E Figure 2 shows the connector as P6: four plated ground posts on a
square with the signal pin in the middle - the ordinary vertical/PCB-mount SMA
jack, not the edge launch used on the 2.45 GHz board here.

The geometry is measured off Figure 2 rather than taken from a datasheet,
because the note gives none.  Reading the plated barrels out of the figure at
its own scale (7.86 px/mm, set by X1 = 63 mm) gives:

    post pitch   5.15 mm in x, 5.06 mm in y   -> 5.08 mm (0.200"), the
                                                 standard SMA flange square
    post drill   1.21, 1.27, 1.21, 1.21 mm    -> 1.2 mm
    centre pin   1.08 mm, exactly centred     -> 1.1 mm

That is about +/- 0.1 mm of reading error on a raster, so **check it against
the connector you actually buy before ordering boards**.  The pitch is the one
number that is certain, because 5.08 mm is a standard and the measurement
lands on it from both axes.

    python3 kicad/tools/gen_sma_through_hole.py
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, dumps, num  # noqa: E402

NAME = "SMA_ThruHole_4Post"
DEST = (pathlib.Path(__file__).resolve().parent.parent / "library"
        / "TI_DN024.pretty" / f"{NAME}.kicad_mod")
UUID = "e8a4c760-9d25-5f31-b0c8-0000000000"

PITCH = 5.08         # 0.200", the standard SMA flange square
POST_DRILL, POST_PAD = 1.2, 1.9
PIN_DRILL, PIN_PAD = 1.1, 1.8
# The signal pin passes through the bottom ground plane, so the plane has to
# pull back around it.  0.5 mm is a starting value, not a computed one: a
# coaxial launch through a plane wants an anti-pad sized with the barrel
# diameter and the dielectric, and that is a tuning exercise on a real board.
PIN_CLEARANCE = 0.5
BODY = 6.35          # the jack's square body, for silkscreen and courtyard


def build() -> list:
    n = [0]

    def uid():
        n[0] += 1
        return [Sym("uuid"), f"{UUID}{n[0]:02d}"]

    def text(kind, value, y, layer, size, prop=True):
        head = [Sym("property"), kind.capitalize(), value] if prop else \
               [Sym("fp_text"), Sym(kind), value]
        return head + [
            [Sym("at"), num(0), num(y), Sym("0")],
            [Sym("layer"), layer], uid(),
            [Sym("effects"), [Sym("font"), [Sym("size"), num(size), num(size)],
                              [Sym("thickness"), num(size * 0.15)]]]]

    def hole(number, at, drill, pad, clearance=None):
        node = [Sym("pad"), number, Sym("thru_hole"), Sym("circle"),
                [Sym("at"), num(at[0]), num(at[1])],
                [Sym("size"), num(pad), num(pad)],
                [Sym("drill"), num(drill)],
                [Sym("layers"), "*.Cu", "*.Mask"]]
        if clearance is not None:
            node.append([Sym("clearance"), num(clearance)])
        node.append(uid())
        return node

    def rect(half, layer, width):
        return [Sym("fp_rect"),
                [Sym("start"), num(-half), num(-half)],
                [Sym("end"), num(half), num(half)],
                [Sym("stroke"), [Sym("width"), num(width)], [Sym("type"), Sym("solid")]],
                [Sym("fill"), Sym("no")], [Sym("layer"), layer], uid()]

    half = PITCH / 2
    fp = [Sym("footprint"), NAME,
          [Sym("version"), Sym("20241229")],
          [Sym("generator"), "gen_sma_through_hole.py"],
          [Sym("generator_version"), "9.0"],
          [Sym("layer"), "F.Cu"],
          [Sym("descr"),
           f"Vertical through-hole SMA jack: signal pin with four ground posts "
           f"on a {PITCH} mm square. The connector SWRA227E Figure 2 shows as "
           f"P6. Post and pin drills are measured off that figure to about "
           f"+/-0.1 mm, not taken from a datasheet - check them against the "
           f"connector you buy. The pin carries a {PIN_CLEARANCE} mm clearance "
           f"so the bottom ground pulls back where it passes through."],
          [Sym("tags"), "SMA jack through hole vertical PCB mount 50 ohm RF"],
          [Sym("attr"), Sym("through_hole")],
          text("reference", "REF**", -(BODY / 2 + 1.2), "F.SilkS", 1.0),
          text("value", NAME, BODY / 2 + 1.2, "F.Fab", 0.8),
          rect(BODY / 2, "F.SilkS", 0.12),
          rect(BODY / 2, "F.Fab", 0.1),
          rect(BODY / 2 + 0.25, "F.CrtYd", 0.05),
          hole("1", (0, 0), PIN_DRILL, PIN_PAD, PIN_CLEARANCE)]
    for sx in (-1, 1):
        for sy in (-1, 1):
            fp.append(hole("2", (sx * half, sy * half), POST_DRILL, POST_PAD))
    fp.append([Sym("embedded_fonts"), Sym("no")])
    return fp


def main() -> None:
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter
                            ).parse_args()
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(dumps(build()) + "\n")
    print(f"wrote {DEST.name}")
    print(f"  signal pin drill {PIN_DRILL} mm, pad {PIN_PAD} mm, "
          f"{PIN_CLEARANCE} mm clearance through the plane")
    print(f"  four ground posts on a {PITCH} mm square, drill {POST_DRILL} mm, "
          f"pad {POST_PAD} mm")


if __name__ == "__main__":
    main()
