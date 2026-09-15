#!/usr/bin/env python3
"""Generate the wide-land 0402 footprint for a part sitting in a 50 ohm line.

A 50 ohm microstrip on 1.6 mm FR4 is 2.95 mm wide.  A normal 0402 land is
0.56 mm.  Butting one onto the other does not work: KiCad tracks have round
caps, so a 2.95 mm track ending on the pad bulges 1.475 mm past its endpoint
and swallows the opposite pad, which sits 0.96 mm away.

Necking the line down to the pads is worse than it looks.  0.6 mm of track is
about 100 ohm here, and the 6.5 mm it takes to get down and back is 3.8 nH -
j58 ohm at 2.45 GHz, in series with the antenna.  That is not a rounding
error, it is a matching network nobody asked for.

So the land is widened to the line instead.  The pads keep the 0402 pitch, so
the part solders normally; they are simply as wide as the track, and the line
runs straight into them with no step at all.  The 0.4 mm of bare substrate
between them is bridged by the component.

    python3 kicad/tools/gen_rf_lands.py --width 2.95
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, dumps, num  # noqa: E402

NAME = "Chip_0402_RF_WideLand"
DEST = (pathlib.Path(__file__).resolve().parent.parent / "library"
        / "SWRA117D_RF.pretty" / f"{NAME}.kicad_mod")
UUID = "d3f1a205-6c18-5b93-a742-0000000000"
PAD_DY = 0.48        # 0402 pad centre offset, same as the normal land
PAD_LEN = 0.56       # along the line


def build(width: float) -> list:
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

    def pad(number, y):
        return [Sym("pad"), number, Sym("smd"), Sym("roundrect"),
                [Sym("at"), num(0), num(y)],
                [Sym("size"), num(width), num(PAD_LEN)],
                [Sym("layers"), "F.Cu", "F.Paste", "F.Mask"],
                [Sym("roundrect_rratio"), num(0.1)], uid()]

    edge = width / 2 + 0.25
    fp = [Sym("footprint"), NAME,
          [Sym("version"), Sym("20241229")],
          [Sym("generator"), "gen_rf_lands.py"],
          [Sym("generator_version"), "9.0"],
          [Sym("layer"), "F.Cu"],
          [Sym("descr"),
           f"0402 land widened to {width} mm so a 50 ohm microstrip of that "
           "width runs into it with no step. Pads keep the 0402 pitch, so the "
           "part solders normally. For the series position of a pi network on "
           "a wide line; the shunt positions use the ordinary land, because a "
           "short narrow stub into a shunt element is not in the through path."],
          [Sym("tags"), "0402 RF land wide 50 ohm series pi matching"],
          [Sym("attr"), Sym("smd")],
          text("reference", "REF**", -(PAD_DY + PAD_LEN / 2 + 1.0), "F.SilkS", 1.0),
          text("value", NAME, PAD_DY + PAD_LEN / 2 + 1.0, "F.Fab", 0.8),
          pad("1", PAD_DY), pad("2", -PAD_DY),
          [Sym("fp_rect"),
           [Sym("start"), num(-edge), num(-(PAD_DY + PAD_LEN / 2 + 0.2))],
           [Sym("end"), num(edge), num(PAD_DY + PAD_LEN / 2 + 0.2)],
           [Sym("stroke"), [Sym("width"), num(0.05)], [Sym("type"), Sym("solid")]],
           [Sym("fill"), Sym("no")], [Sym("layer"), "F.CrtYd"], uid()],
          [Sym("embedded_fonts"), Sym("no")]]
    return fp


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=float, required=True,
                    help="pad width [mm] - the width of the line it sits in")
    args = ap.parse_args()
    DEST.write_text(dumps(build(args.width)) + "\n")
    print(f"wrote {DEST.name}: pads {args.width} x {PAD_LEN} mm at "
          f"{2 * PAD_DY} mm pitch, {2 * PAD_DY - PAD_LEN:.2f} mm gap between them")


if __name__ == "__main__":
    main()
