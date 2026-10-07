#!/usr/bin/env python3
"""Generate library/TI_DN023.kicad_sym for the SWRA228C inverted-F.

One new symbol - the antenna - plus copies of the parts every project here
places.  The copies are copies on purpose: a schematic embeds the symbols it
places and KiCad raises ``lib_symbol_mismatch`` on any difference, so each
project resolving everything inside one in-project library is what keeps ERC
quiet.  Sharing one library across projects does not.

    python3 kicad/tools/gen_dn023_symbols.py
"""

from __future__ import annotations

import copy
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, dumps, find_all, num, parse  # noqa: E402

LIB_DIR = pathlib.Path(__file__).resolve().parent.parent / "library"
SOURCE = LIB_DIR / "SWRA117D_RF.kicad_sym"
DEST = LIB_DIR / "TI_DN023.kicad_sym"
SHARED = ("C", "L", "R", "Conn_Coaxial_SMA", "GND", "PWR_FLAG", "RF_PORT")
NAME = "ANT_DN023_IFA"
DATASHEET = "https://www.ti.com/lit/an/swra228c/swra228c.pdf"


def effects(size=1.27, hide=False):
    node = [Sym("effects"), [Sym("font"), [Sym("size"), num(size), num(size)]]]
    if hide:
        node.append([Sym("hide"), Sym("yes")])
    return node


def prop(name, value, at, hide=False):
    return [Sym("property"), name, value,
            [Sym("at"), num(at[0]), num(at[1]), Sym(str(at[2]))],
            effects(hide=hide)]


def antenna_symbol() -> list:
    """An inverted-F: a feed, a short to ground, and a meandered arm.

    Drawn as the shape it is - the two legs and the square-wave arm - so the
    sheet says which antenna this is and which pin is the short.
    """
    def line(points, width=0.254):
        return [Sym("polyline"),
                [Sym("pts")] + [[Sym("xy"), num(x), num(y)] for x, y in points],
                [Sym("stroke"), [Sym("width"), num(width)],
                 [Sym("type"), Sym("default")]],
                [Sym("fill"), [Sym("type"), Sym("none")]]]

    # the top rail, then a square wave running right to the open stub
    rail_y, depth, pitch = 2.54, 1.524, 1.27
    pts = [(-5.08, rail_y)]
    x, down = -2.54, True
    for _ in range(4):
        pts += [(x, rail_y), (x, rail_y - depth if down else rail_y)]
        x += pitch
        pts += [(x, rail_y - depth if down else rail_y)]
        down = not down
    pts += [(x, rail_y), (5.08, rail_y), (5.08, rail_y - 2.54)]   # the L6 stub

    body = [line(pts),
            line([(-5.08, rail_y), (-5.08, -2.54)]),              # shorting leg
            line([(-2.54, rail_y), (-2.54, -2.54)], 0.4)]         # feed leg, W2
    # the ground bar, because an inverted-F works against its plane
    body += [line([(-6.35, -3.81), (-3.81, -3.81)], 0.3),
             line([(-5.842, -4.318), (-4.318, -4.318)], 0.3),
             line([(-5.08, -2.54), (-5.08, -3.81)], 0.254)]

    return [Sym("symbol"), NAME,
            [Sym("pin_numbers"), [Sym("hide"), Sym("yes")]],
            [Sym("pin_names"), [Sym("offset"), num(0.762)]],
            [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("no")],
            [Sym("on_board"), Sym("yes")],
            prop("Reference", "AE", (-7.62, 5.08, 0)),
            prop("Value", NAME, (0.0, 6.35, 0)),
            prop("Footprint", "TI_DN023:TI_DN023_IFA_868", (0.0, 0.0, 0), hide=True),
            prop("Datasheet", DATASHEET, (0.0, 0.0, 0), hide=True),
            prop("Description",
                 "TI DN023 (SWRA228C) printed inverted-F PCB antenna for "
                 "868 / 915 / 955 MHz. 43 x 20 mm, one layer, no ground plane "
                 "beneath it. Approximately 50 ohm with nothing fitted; the "
                 "note lays out one series and two shunt sites anyway, to "
                 "compensate detuning from an enclosure. Tuned by trimming L6: "
                 "Table 1 draws 17 mm, the note measured 11 mm at 868 MHz and "
                 "3 mm at 915 MHz.", (0.0, 0.0, 0), hide=True),
            prop("ki_keywords",
                 "antenna inverted-F IFA 868 915 955 sub-GHz TI DN023",
                 (0.0, 0.0, 0), hide=True),
            prop("ki_fp_filters", "TI_DN023_IFA*", (0.0, 0.0, 0), hide=True),
            [Sym("symbol"), f"{NAME}_0_1"] + body,
            [Sym("symbol"), f"{NAME}_1_1",
             [Sym("pin"), Sym("passive"), Sym("line"),
              [Sym("at"), num(-2.54), num(-5.08), Sym("90")],
              [Sym("length"), num(2.54)],
              [Sym("name"), "FEED", effects()],
              [Sym("number"), "1", effects()]],
             [Sym("pin"), Sym("passive"), Sym("line"),
              [Sym("at"), num(-5.08), num(-6.35), Sym("90")],
              [Sym("length"), num(2.54)],
              [Sym("name"), "SHORT", effects()],
              [Sym("number"), "2", effects()]]],
            [Sym("embedded_fonts"), Sym("no")]]


def main() -> None:
    source = parse(SOURCE.read_text())
    have = {str(s[1]): s for s in find_all(source, "symbol")}
    missing = [n for n in SHARED if n not in have]
    if missing:
        raise SystemExit(f"{SOURCE.name} has no {', '.join(missing)}")

    lib = [Sym("kicad_symbol_lib"),
           [Sym("version"), Sym("20241209")],
           [Sym("generator"), "gen_dn023_symbols.py"],
           [Sym("generator_version"), "9.0"],
           antenna_symbol()]
    lib += [copy.deepcopy(have[n]) for n in SHARED]
    DEST.write_text(dumps(lib) + "\n")
    print(f"wrote {DEST.relative_to(LIB_DIR.parent)}: "
          f"{NAME} + {', '.join(SHARED)}")


if __name__ == "__main__":
    main()
