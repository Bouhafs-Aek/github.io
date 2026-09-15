#!/usr/bin/env python3
"""Compose library/TI_DN024.kicad_sym for the DN024 monopole project.

The antenna symbol is written here; the passives, the connector, GND and
PWR_FLAG are copied verbatim out of the first project's library.  Copied
rather than referenced across libraries on purpose: a schematic embeds a copy
of every symbol it places and KiCad raises lib_symbol_mismatch on any
difference, so each project resolving every symbol it places inside one
in-project library is what keeps ERC quiet on any install.

    python3 kicad/tools/gen_dn024_symbols.py
"""

from __future__ import annotations

import copy
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, dumps, find_all, num, parse  # noqa: E402

LIB_DIR = pathlib.Path(__file__).resolve().parent.parent / "library"
SOURCE = LIB_DIR / "SWRA117D_RF.kicad_sym"
DEST = LIB_DIR / "TI_DN024.kicad_sym"
SHARED = ("C", "L", "Conn_Coaxial_SMA", "GND", "PWR_FLAG", "RF_PORT")

DATASHEET = "https://www.ti.com/lit/an/swra227e/swra227e.pdf"


def effects(size=1.27, hide=False, italic=False):
    font = [Sym("font"), [Sym("size"), num(size), num(size)]]
    if italic:
        font.append([Sym("italic"), Sym("yes")])
    out = [Sym("effects"), font]
    if hide:
        out.append([Sym("hide"), Sym("yes")])
    return out


def prop(name, value, at, hide=False):
    return [Sym("property"), name, value,
            [Sym("at"), num(at[0]), num(at[1]), Sym(str(at[2]))],
            effects(hide=hide)]


def antenna_symbol() -> list:
    """A meandering monopole: one terminal, and the ground plane is the other.

    Drawn as the shape it is rather than as a generic antenna triangle - four
    arms over a ground bar - so the sheet says which antenna this is.
    """
    def line(points, width=0.254):
        return [Sym("polyline"),
                [Sym("pts")] + [[Sym("xy"), num(x), num(y)] for x, y in points],
                [Sym("stroke"), [Sym("width"), num(width)], [Sym("type"), Sym("default")]],
                [Sym("fill"), [Sym("type"), Sym("none")]]]

    # the meander, small: four arms, alternating, open at the top left
    arms = []
    x0, x1 = -3.81, 3.81
    y = 0.0
    pts = [(0.0, -2.54), (0.0, 0.0)]          # feed stub up into the bottom arm
    right = True
    for i in range(4):
        y = i * 1.905
        pts.append((x1 if right else x0, y))
        if i < 3:
            pts.append((x1 if right else x0, y + 1.905))
            right = not right
    pts.append((x0, 3 * 1.905))                # open tip
    body = [line(pts)]
    # ground bar under the feed, because a monopole works against its plane
    body += [line([(-2.54, -3.81), (2.54, -3.81)], 0.3),
             line([(-1.524, -4.572), (1.524, -4.572)], 0.3),
             line([(-0.635, -5.334), (0.635, -5.334)], 0.3),
             line([(0.0, -2.54), (0.0, -3.81)], 0.254)]

    return [Sym("symbol"), "ANT_DN024_Monopole",
            [Sym("pin_numbers"), [Sym("hide"), Sym("yes")]],
            [Sym("pin_names"), [Sym("offset"), num(0.762)]],
            [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("no")],
            [Sym("on_board"), Sym("yes")],
            prop("Reference", "AE", (-6.35, -7.62, 0)),
            prop("Value", "ANT_DN024_Monopole", (0.0, 9.0, 0)),
            prop("Footprint", "TI_DN024:TI_DN024_Monopole_868_2440",
                 (0.0, 0.0, 0), hide=True),
            prop("Datasheet", DATASHEET, (0.0, 0.0, 0), hide=True),
            prop("Description",
                 "TI DN024 (SWRA227E) meandering monopole PCB antenna. "
                 "868/915/920 MHz single band, or 868 + 2440 MHz dual band. "
                 "38 x 25 mm, 1.6 mm FR4, copper on both layers, no ground "
                 "plane beneath it. Needs a pi matching network at the feed: "
                 "the note gives the values and they depend on the band and on "
                 "the ground plane size.", (0.0, 0.0, 0), hide=True),
            prop("ki_keywords", "antenna monopole meander 868 915 920 2440 sub-GHz TI DN024",
                 (0.0, 0.0, 0), hide=True),
            prop("ki_fp_filters", "TI_DN024_Monopole*", (0.0, 0.0, 0), hide=True),
            [Sym("symbol"), "ANT_DN024_Monopole_0_1"] + body,
            [Sym("symbol"), "ANT_DN024_Monopole_1_1",
             [Sym("pin"), Sym("passive"), Sym("line"),
              [Sym("at"), num(0.0), num(-7.62), Sym("90")],
              [Sym("length"), num(2.54)],
              [Sym("name"), "FEED", effects()],
              [Sym("number"), "1", effects()]]],
            [Sym("embedded_fonts"), Sym("no")]]


def main() -> None:
    source = parse(SOURCE.read_text())
    have = {str(s[1]): s for s in find_all(source, "symbol")}
    missing = [n for n in SHARED if n not in have]
    if missing:
        raise SystemExit(f"{SOURCE.name} has no {', '.join(missing)}")

    lib = [Sym("kicad_symbol_lib"),
           [Sym("version"), Sym("20241209")],
           [Sym("generator"), "gen_dn024_symbols.py"],
           [Sym("generator_version"), "9.0"],
           antenna_symbol()]
    lib += [copy.deepcopy(have[n]) for n in SHARED]
    DEST.write_text(dumps(lib) + "\n")
    print(f"wrote {DEST.relative_to(LIB_DIR.parent)}: "
          f"ANT_DN024_Monopole + {', '.join(SHARED)}")


if __name__ == "__main__":
    main()
