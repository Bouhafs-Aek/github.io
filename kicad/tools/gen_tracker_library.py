#!/usr/bin/env python3
"""Build the football tracker's in-project library from the KiCad 9 libraries.

Every symbol and footprint the tracker places, except the GNSS patch, is a
copy of the official KiCad library part, taken from the ``9.0.9.1`` tag of

    https://gitlab.com/kicad/libraries/kicad-symbols
    https://gitlab.com/kicad/libraries/kicad-footprints

and written into ``library/EPTS_Tracker.kicad_sym`` and
``library/EPTS_Tracker.pretty``.  Same reason as the antenna projects keep
their symbols in-project: a schematic embeds a copy of every symbol it
places, and KiCad reports ``lib_symbol_mismatch`` whenever that copy differs
from the library it names.  Pinning one tag here makes the project
self-contained and ERC-clean on any install.

Derived symbols (``extends``) are flattened on the way in.  NEO-M9N is
stored by KiCad as "NEO-M8N with different fields", AP2112K-3.3 as an
AP2204K and so on; the schematic has to embed the flat form anyway, so the
library stores that, and the pin table the checker reads is the one that is
actually placed.

The patch antenna footprint is generated, not copied: there is no 25 x 25 mm
single-feed GNSS patch in the KiCad library.  Its one part-specific
dimension, the feed pin's offset from the patch centre, is PATCH_FEED_OFFSET
below - set it from the drawing of the patch you buy.

    python3 kicad/tools/gen_tracker_library.py            # fetch, then write
    python3 kicad/tools/gen_tracker_library.py --cache D  # reuse downloads in D

The KiCad libraries are CC-BY-SA 4.0 with the exception that designs using
them are not affected; the copies here keep their original attribution.
"""

from __future__ import annotations

import argparse
import copy
import pathlib
import sys
import urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, dumps, find, num, parse  # noqa: E402

TAG = "9.0.9.1"
SYM_URL = f"https://gitlab.com/kicad/libraries/kicad-symbols/-/raw/{TAG}/{{lib}}.kicad_sym"
FP_URL = (f"https://gitlab.com/kicad/libraries/kicad-footprints/-/raw/{TAG}/"
          "{lib}.pretty/{name}.kicad_mod")

LIB_DIR = pathlib.Path(__file__).resolve().parent.parent / "library"
NICK = "EPTS_Tracker"

# (source library, symbol) - the order is the order in the output file
SYMBOLS = [
    ("RF_GPS", "NEO-M9N"),
    ("RF_Module", "MDBT50Q-1MV2"),
    ("Sensor_Motion", "ISM330DHCX"),
    ("Battery_Management", "MCP73831-2-OT"),
    ("Regulator_Linear", "AP2112K-3.3"),
    ("Transistor_FET", "AO3401A"),
    ("Power_Protection", "USBLC6-2SC6"),
    ("Connector", "USB_C_Receptacle_USB2.0_16P"),
    ("Connector", "Micro_SD_Card_Det_Hirose_DM3AT"),
    ("Connector", "Conn_01x02_Pin"),
    ("Connector", "Conn_ARM_SWD_TagConnect_TC2030-NL"),
    ("Connector", "TestPoint"),
    ("Device", "Antenna"),
    ("Device", "R"),
    ("Device", "C"),
    ("Device", "LED"),
    ("Device", "D_Schottky"),
    ("Switch", "SW_Push"),
    ("power", "PWR_FLAG"),
]

FOOTPRINTS = [
    ("RF_GPS", "ublox_NEO"),
    ("RF_Module", "Raytac_MDBT50Q"),
    ("Package_LGA", "LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y"),
    ("Package_TO_SOT_SMD", "SOT-23-5"),
    ("Package_TO_SOT_SMD", "SOT-23-6"),
    ("Package_TO_SOT_SMD", "SOT-23"),
    ("Connector_USB", "USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal"),
    ("Connector_Card", "microSD_HC_Hirose_DM3AT-SF-PEJM5"),
    ("Connector_JST", "JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal"),
    ("Connector", "Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical"),
    ("Resistor_SMD", "R_0402_1005Metric"),
    ("Capacitor_SMD", "C_0402_1005Metric"),
    ("Capacitor_SMD", "C_0603_1608Metric"),
    ("Capacitor_SMD", "C_0805_2012Metric"),
    ("LED_SMD", "LED_0603_1608Metric"),
    ("Diode_SMD", "D_SOD-323"),
    ("Button_Switch_SMD", "SW_SPST_TL3342"),
    ("TestPoint", "TestPoint_Pad_D1.0mm"),
]

# ----------------------------------------------------------- the GNSS patch
# A 25 x 25 x 4 mm ceramic L1 patch with one feed pin, the size most single
# feed GPS/GNSS patches are sold in.  The ceramic's underside is a silvered
# ground electrode that sits on the board's top copper, so the footprint has
# no ground pad of its own: the top GND pour under it *is* the contact.
PATCH_SIZE = 25.0
PATCH_HEIGHT = 4.0
# Feed pin offset from the patch centre, towards the board's bottom edge.
# Part specific - read it off the antenna's drawing.  1.5 mm is a typical
# value for a 25 mm L1 patch, not a dimension of any particular product.
PATCH_FEED_OFFSET = 1.5
PATCH_PIN_DRILL = 1.3            # fits a 0.9-1.0 mm feed pin
PATCH_PIN_PAD = 2.2
PATCH_NAME = "GNSS_Patch_25x25mm_SingleFeed"


def fetch(url: str, cache: pathlib.Path | None, name: str) -> str:
    if cache is not None and (cache / name).exists():
        return (cache / name).read_text()
    with urllib.request.urlopen(url, timeout=120) as resp:
        text = resp.read().decode()
    if cache is not None:
        (cache / name).parent.mkdir(parents=True, exist_ok=True)
        (cache / name).write_text(text)
    return text


def symbols_by_name(lib) -> dict:
    return {str(c[1]): c for c in lib[1:]
            if isinstance(c, list) and c[0] == "symbol"}


def flatten(name: str, table: dict) -> list:
    """The symbol as KiCad embeds it: parent graphics and pins, own fields."""
    sym = copy.deepcopy(table[name])
    ext = find(sym, "extends")
    if ext is None:
        return sym
    parent = flatten(str(ext[1]), table)
    own_props = [c for c in sym if isinstance(c, list) and c[0] == "property"]
    out = [Sym("symbol"), name]
    props_done = False
    for child in parent[2:]:
        if isinstance(child, list) and child[0] == "property":
            if not props_done:
                out.extend(own_props)
                props_done = True
            continue
        if isinstance(child, list) and child[0] == "symbol":
            child = copy.deepcopy(child)
            # sub-units are named PARENT_unit_style; they take the new name
            unit = str(child[1]).rsplit("_", 2)
            child[1] = f"{name}_{unit[1]}_{unit[2]}"
        out.append(child)
    return out


def patch_footprint() -> list:
    half = PATCH_SIZE / 2

    def rect(layer, h, width):
        return [Sym("fp_rect"), [Sym("start"), num(-h), num(-h)],
                [Sym("end"), num(h), num(h)],
                [Sym("stroke"), [Sym("width"), num(width)], [Sym("type"), Sym("solid")]],
                [Sym("fill"), Sym("no")], [Sym("layer"), layer]]

    def text(kind, value, at, layer, hide=False):
        node = [Sym("property"), kind, value,
                [Sym("at"), num(at[0]), num(at[1]), Sym("0")],
                [Sym("layer"), layer]]
        if hide:
            node.append([Sym("hide"), Sym("yes")])
        node.append([Sym("effects"), [Sym("font"), [Sym("size"), num(1), num(1)],
                                       [Sym("thickness"), num(0.15)]]])
        return node

    return [Sym("footprint"), PATCH_NAME,
            [Sym("version"), Sym("20241229")],
            [Sym("generator"), "gen_tracker_library.py"],
            [Sym("layer"), "F.Cu"],
            text("Reference", "AE1", (0, -half - 1.5), "F.SilkS"),
            text("Value", PATCH_NAME, (0, half + 1.5), "F.Fab"),
            text("Datasheet", "~", (0, 0), "F.Fab", hide=True),
            text("Description",
                 f"{PATCH_SIZE:g} x {PATCH_SIZE:g} x {PATCH_HEIGHT:g} mm ceramic L1 GNSS "
                 "patch, single feed pin. The ceramic's ground electrode sits "
                 "on the top GND pour; feed offset "
                 f"{PATCH_FEED_OFFSET:g} mm from centre - check against the "
                 "chosen part's drawing", (0, 0), "F.Fab", hide=True),
            [Sym("attr"), Sym("through_hole")],
            rect("F.SilkS", half + 0.15, 0.12),
            rect("F.Fab", half, 0.1),
            rect("F.CrtYd", half + 0.5, 0.05),
            [Sym("fp_circle"), [Sym("center"), num(0), num(PATCH_FEED_OFFSET)],
             [Sym("end"), num(0), num(PATCH_FEED_OFFSET + 1.6)],
             [Sym("stroke"), [Sym("width"), num(0.1)], [Sym("type"), Sym("solid")]],
             [Sym("fill"), Sym("no")], [Sym("layer"), "F.Fab"]],
            [Sym("fp_text"), Sym("user"), "FEED",
             [Sym("at"), num(0), num(PATCH_FEED_OFFSET + 2.6), Sym("0")],
             [Sym("layer"), "F.Fab"],
             [Sym("effects"), [Sym("font"), [Sym("size"), num(0.8), num(0.8)],
                                [Sym("thickness"), num(0.12)]]]],
            [Sym("pad"), "1", Sym("thru_hole"), Sym("circle"),
             [Sym("at"), num(0), num(PATCH_FEED_OFFSET)],
             [Sym("size"), num(PATCH_PIN_PAD), num(PATCH_PIN_PAD)],
             [Sym("drill"), num(PATCH_PIN_DRILL)],
             [Sym("layers"), "*.Cu", "*.Mask"],
             [Sym("remove_unused_layers"), Sym("no")]],
            [Sym("embedded_fonts"), Sym("no")]]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cache", type=pathlib.Path,
                    help="directory to keep/reuse the downloaded KiCad files in")
    args = ap.parse_args()

    tables = {}
    out = [Sym("kicad_symbol_lib"),
           [Sym("version"), Sym("20241209")],
           [Sym("generator"), "gen_tracker_library.py"],
           [Sym("generator_version"), "9.0"]]
    for lib, name in SYMBOLS:
        if lib not in tables:
            text = fetch(SYM_URL.format(lib=lib), args.cache, f"{lib}.kicad_sym")
            tables[lib] = symbols_by_name(parse(text))
        out.append(flatten(name, tables[lib]))
    sym_path = LIB_DIR / f"{NICK}.kicad_sym"
    sym_path.write_text(dumps(out) + "\n")
    print(f"wrote {sym_path.relative_to(LIB_DIR.parent.parent)} ({len(SYMBOLS)} symbols)")

    pretty = LIB_DIR / f"{NICK}.pretty"
    pretty.mkdir(exist_ok=True)
    for lib, name in FOOTPRINTS:
        text = fetch(FP_URL.format(lib=lib, name=name), args.cache,
                     f"{lib}.pretty/{name}.kicad_mod")
        (pretty / f"{name}.kicad_mod").write_text(text)
    (pretty / f"{PATCH_NAME}.kicad_mod").write_text(dumps(patch_footprint()) + "\n")
    print(f"wrote {pretty.relative_to(LIB_DIR.parent.parent)} "
          f"({len(FOOTPRINTS) + 1} footprints)")


if __name__ == "__main__":
    main()
