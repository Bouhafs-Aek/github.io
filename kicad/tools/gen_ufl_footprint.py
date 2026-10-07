#!/usr/bin/env python3
"""Generate the U.FL land pattern the kit launches from.

The kit feeds every board through a Hirose U.FL-R-SMT-1(10) and a pigtail to
a bulkhead SMA, rather than an SMA soldered to the board edge.  Three reasons,
in order of how much they matter:

  * the bulkhead SMA stays on the test jig, so the connector body and its
    ground tabs are no longer copper sitting in the near field of a board
    whose ground plane IS half the antenna;
  * the pigtail can carry a ferrite or a sleeve balun, which is the only real
    cure for common-mode current on the feed cable.  On a 45 x 60 mm plane at
    868 MHz the cable braid is part of the antenna unless you choke it, and
    that shows up as an S11 null that moves when you move the cable;
  * it is what an actual IoT product has on it, so the board under test is
    closer to the thing being designed.

THE NUMBERS ARE NOT INVENTED AND NOT MEASURED OFF A PICTURE.  They are the
manufacturer's recommended land pattern, taken from the KiCad footprint
library's ``Connector_Coaxial.pretty/U.FL_Hirose_U.FL-R-SMT-1_Vertical``,
which cites Hirose's own page for the part:

    https://www.hirose.com/product/en/products/U.FL/U.FL-R-SMT-1%2810%29/

    signal pad   1.05 x 1.00 mm at (-1.05, 0)
    ground pads  2.20 x 1.05 mm at (0.475, +/-1.475)

They are reproduced here rather than the file being copied, so that this
library stays self-contained and so that the provenance is written down next
to the geometry.  KiCad's libraries are CC-BY-SA 4.0 with a design exception;
this is attribution.

A 50 ohm line on 1.6 mm FR4 is 2.95 mm wide and this pad is 1.05 mm, so the
line cannot butt onto it - the launch tapers, exactly as it has to for a
through-hole SMA's ground posts.  ``gen_kit.py`` does the tapering and
``check_kit.py`` fails the board if it stops.

    python3 kicad/tools/gen_ufl_footprint.py
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, dumps, num  # noqa: E402

NAME = "U_FL_Hirose_U_FL_R_SMT_1_Vertical"
DEST = (pathlib.Path(__file__).resolve().parent.parent / "library"
        / "SWRA117D_RF.pretty" / f"{NAME}.kicad_mod")
UUID = "f0b61d35-8e27-5a4c-9311-0000000000"

DATASHEET = ("https://www.hirose.com/product/en/products/U.FL/"
             "U.FL-R-SMT-1%2810%29/")
SIGNAL_AT, SIGNAL_SIZE = (-1.05, 0.0), (1.05, 1.0)
GROUND_AT_Y, GROUND_SIZE = 1.475, (2.2, 1.05)
GROUND_X = 0.475
COURTYARD = (-2.02, -2.5, 2.28, 2.5)
BODY = (-0.425, -1.5, 1.775, 1.5)      # the connector shell, for F.Fab


def build() -> list:
    n = [0]

    def uid():
        n[0] += 1
        return [Sym("uuid"), f"{UUID}{n[0]:02d}"]

    def pad(number, at, size, name):
        return [Sym("pad"), number, Sym("smd"), Sym("rect"),
                [Sym("at"), num(at[0]), num(at[1])],
                [Sym("size"), num(size[0]), num(size[1])],
                [Sym("layers"), "F.Cu", "F.Paste", "F.Mask"],
                [Sym("pinfunction"), name], uid()]

    def text(kind, value, y, layer, size):
        return [Sym("property"), kind.capitalize(), value,
                [Sym("at"), num(GROUND_X), num(y), Sym("0")],
                [Sym("layer"), layer], uid(),
                [Sym("effects"), [Sym("font"), [Sym("size"), num(size), num(size)],
                                  [Sym("thickness"), num(size * 0.15)]]]]

    def rect(box, layer, width):
        x0, y0, x1, y1 = box
        out = []
        pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        for i in range(4):
            a, b = pts[i], pts[(i + 1) % 4]
            out.append([Sym("fp_line"),
                        [Sym("start"), num(a[0]), num(a[1])],
                        [Sym("end"), num(b[0]), num(b[1])],
                        [Sym("stroke"), [Sym("width"), num(width)],
                         [Sym("type"), Sym("solid")]],
                        [Sym("layer"), layer], uid()])
        return out

    fp = [Sym("footprint"), NAME,
          [Sym("version"), Sym("20241229")],
          [Sym("generator"), "gen_ufl_footprint.py"],
          [Sym("generator_version"), "9.0"],
          [Sym("layer"), "F.Cu"],
          [Sym("descr"),
           f"Hirose U.FL-R-SMT-1(10) vertical coaxial receptacle. "
           f"Manufacturer's recommended land pattern, via the KiCad "
           f"Connector_Coaxial library, which cites {DATASHEET} . Signal pad "
           f"{SIGNAL_SIZE[0]} x {SIGNAL_SIZE[1]} mm, two ground pads "
           f"{GROUND_SIZE[0]} x {GROUND_SIZE[1]} mm. The signal pad is "
           f"{SIGNAL_SIZE[1]} mm across, so a 50 ohm line on 1.6 mm FR4 "
           f"(2.95 mm) must taper into it, not butt onto it."],
          [Sym("tags"), "U.FL IPEX coaxial RF receptacle Hirose 50 ohm"],
          [Sym("attr"), Sym("smd")],
          [Sym("property"), "Datasheet", DATASHEET,
           [Sym("at"), num(0), num(0), Sym("0")], [Sym("layer"), "F.Fab"], uid(),
           [Sym("effects"), [Sym("font"), [Sym("size"), num(1), num(1)]],
            [Sym("hide"), Sym("yes")]]],
          text("reference", "REF**", -3.2, "F.SilkS", 1.0),
          text("value", NAME, 3.2, "F.Fab", 0.8),
          pad("1", SIGNAL_AT, SIGNAL_SIZE, "SIGNAL"),
          pad("2", (GROUND_X, GROUND_AT_Y), GROUND_SIZE, "GND"),
          pad("2", (GROUND_X, -GROUND_AT_Y), GROUND_SIZE, "GND")]
    fp += rect(COURTYARD, "F.CrtYd", 0.05)
    fp += rect(BODY, "F.Fab", 0.1)
    fp.append([Sym("embedded_fonts"), Sym("no")])
    return fp


def main() -> None:
    argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(dumps(build()) + "\n")
    print(f"wrote library/SWRA117D_RF.pretty/{DEST.name}")
    print(f"  signal pad {SIGNAL_SIZE[0]} x {SIGNAL_SIZE[1]} mm at "
          f"{SIGNAL_AT}, ground pads {GROUND_SIZE[0]} x {GROUND_SIZE[1]} mm "
          f"at x={GROUND_X}, y=+/-{GROUND_AT_Y}")
    print("  Hirose recommended land pattern, via KiCad Connector_Coaxial")


if __name__ == "__main__":
    main()
