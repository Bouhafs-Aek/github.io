#!/usr/bin/env python3
"""Generate the RFsim project for the DN024 monopole.

The fabrication boards in ``dn024/`` and ``dn024_ti_form/`` are for building.
Handing either of them straight to a full-wave solver produces a meaningless
answer, for two reasons that have nothing to do with the antenna:

  1. **KiCad stores zones unfilled.**  A ``.kicad_pcb`` written by a script
     has zone *outlines* and no ``filled_polygon`` at all until someone
     presses B in the PCB editor and saves.  A solver reads the file, so it
     sees no ground plane.  For a monopole that is fatal: the plane is the
     other half of the antenna, and without it there is nothing to resonate
     against.  So this board has **no zones**.  Its ground is pads - real
     copper in the file, no fill step, nothing to forget.

  2. **Z62 is a 3.9 pF capacitor, and copper is all a field solver meshes.**
     In the fabrication board Z62 is an 0402 land: two pads 0.40 mm apart.
     A solver sees that gap, not the part that will be soldered across it -
     a fraction of a picofarad where 3.9 pF belongs, which at 868 MHz is
     -j6000 ohm instead of -j47 ohm.  That is an open circuit: the antenna
     is simply not connected to the port, and S11 sits at 0 dB.  So here
     **Z62 is a copper bridge**.

The second one also gives the run something to be checked against, which is
the real reason to do it this way rather than guess at lumped models.
SWRA227E section 4.3.1 measured exactly this configuration:

    "With no antenna match components (Z62: 0 ohm), at 868 MHz the match is
     poor with SWR 2.9 and excellent at 2.44 GHz with SWR 1.2."

So a correct run of *this* board must land near:

    868 MHz    SWR 2.9  ->  S11 = -6.3 dB
    2440 MHz   SWR 1.2  ->  S11 = -20.8 dB

Not the matched -10 dB band TI plots in Figure 13 - that one includes the
3.9 pF, and no copper-only model can produce it.  Match the copper first,
then add the capacitor in a circuit simulator.

Geometry is ``dn024_ti_form`` - the note's own Figure 2 layout, connector
inboard - because that is the board TI measured.  ``gen_dn024_ti_project`` is
imported rather than copied, so the two cannot drift apart.

    python3 kicad/tools/gen_dn024_sim_board.py
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_project as gp  # noqa: E402
import gen_dn024_project as dn  # noqa: E402
import gen_dn024_ti_project as ti  # noqa: E402
from sexpr import Sym, dumps, find, num  # noqa: E402

# Its own uuid namespace: nothing here shares an identity with either
# fabrication project, even though all three come from the same sources.
gp.NAMESPACE = uuid.UUID("c41d9a27-6b30-5e88-a4f2-1e7c05d93b6a")
gp.ROOT_UUID = gp.U("sheet", "root")
gp.LIB_NICK = LIB_NICK = "TI_DN024"
gp.PROJECT = PROJECT = "dn024_monopole_sim"

PRJ_DIR = gp.PRJ_DIR
OUT_DIR = PRJ_DIR / "sim" / "board"
FP_NAME = "DN024_Sim_Plane_Port"
FP_DEST = PRJ_DIR / "library" / f"{LIB_NICK}.pretty" / f"{FP_NAME}.kicad_mod"

BOARD_X0, BOARD_Y0 = dn.BOARD_X0, dn.BOARD_Y0
BOARD_X1, BOARD_Y1 = dn.BOARD_X1, dn.BOARD_Y1
BOARD_W, BOARD_H = dn.BOARD_W, dn.BOARD_H
GND_X0, GND_X1, GND_Y1 = dn.GND_X0, dn.GND_X1, dn.GND_Y1
GND_W, GND_H = dn.GND_W, dn.GND_H
PLANE_EDGE = dn.PLANE_EDGE
FEED_X, W50, W_ANT, W_PI = dn.FEED_X, dn.W50, dn.W_ANT, dn.W_PI
SUB_H, SUB_ER, PAD_DX = dn.SUB_H, dn.SUB_ER, dn.PAD_DX
ANT_ORIGIN = dn.ANT_ORIGIN

PORT_AT = ti.CONN_AT                    # where the SMA sits on the real board
PORT_PAD_L = 2.0                        # signal pad, along the line
OPEN_X0 = FEED_X - ti.OPENING_W / 2
OPEN_X1 = FEED_X + ti.OPENING_W / 2
OPEN_BOTTOM = ti.OPENING_BOTTOM

# RF_IN and ANT_FEED are one net here: Z62 is a bridge, not a part.
NETS = {"": 0, "GND": 1, "ANT_FEED": 2}

# TI's own measurement of this exact configuration, SWRA227E 4.3.1.
TARGETS = ((868.0, 2.9), (2440.0, 1.2))


def s11_db(swr: float) -> float:
    return 20 * math.log10(abs((swr - 1) / (swr + 1)))


TITLE = ("TI DN024 monopole - RFsim model, Z62 shorted (SWRA227E 4.3.1), "
         "ground as pads, no connector")

SCH_NOTE = (
    "RFsim model of the TI DN024 / SWRA227E meandering monopole.\n"
    "\n"
    "Two things are deliberately different from the boards in dn024/ and\n"
    "dn024_ti_form/, and both exist because a field solver meshes copper:\n"
    "\n"
    "1. THERE ARE NO ZONES. The ground plane is pads - solid copper in the\n"
    "   file. KiCad stores zones unfilled, and an unfilled pour is not a\n"
    "   ground plane. A monopole radiates against its plane, so a run with\n"
    "   the pour unfilled is not a weak answer, it is no answer.\n"
    "\n"
    "2. Z62 IS A COPPER BRIDGE, not the 3.9 pF part. A solver sees the\n"
    "   0402 land as a 0.40 mm gap, which is a fraction of a pF - an open\n"
    "   circuit at 868 MHz, with the antenna disconnected from the port.\n"
    "\n"
    "That makes this the configuration SWRA227E 4.3.1 measured: \"With no\n"
    "antenna match components (Z62: 0 ohm), at 868 MHz the match is poor\n"
    "with SWR 2.9 and excellent at 2.44 GHz with SWR 1.2.\"\n"
    "\n"
    "  EXPECTED:  868 MHz  SWR 2.9 -> S11 = -6.3 dB\n"
    "            2440 MHz  SWR 1.2 -> S11 = -20.8 dB\n"
    "\n"
    "Do NOT expect Figure 13's matched -10 dB bands. Those include the\n"
    "3.9 pF; add it in a circuit simulator afterwards, on top of the Zin\n"
    "this run produces.\n"
    "\n"
    "P1 is the port land: pad 1 is the signal pad the solver drives, pad 2\n"
    "is the ground - the B.Cu plane runs directly underneath it. The top\n"
    "ground is cut away around the feed, so the line is a plain microstrip:\n"
    f"use an MSL port, not CPW. {W50} mm on {SUB_H} mm FR4 (er {SUB_ER}).\n"
    "\n"
    "Sweep from 0.6 GHz, and give the domain at least a quarter wavelength\n"
    "at the lowest frequency you sweep: 86 mm at 868 MHz, 125 mm at 0.6 GHz."
)


def plane_rects() -> list:
    """Ground copper as rectangles, local to the port land at PORT_AT.

    B.Cu is the whole 43 x 63 mm plane.  F.Cu is the same plane minus the
    opening around the feed and the network, squared off: the chamfers the
    fabrication board carries are cosmetic and a solver does not care, but
    the opening itself is not - it is what makes the line a microstrip.
    """
    px, py = PORT_AT

    def rect(x0, y0, x1, y1, layer):
        return ((x0 + x1) / 2 - px, (y0 + y1) / 2 - py,
                x1 - x0, y1 - y0, layer)

    return [
        rect(GND_X0, PLANE_EDGE, GND_X1, GND_Y1, "B.Cu"),
        rect(GND_X0, PLANE_EDGE, OPEN_X0, GND_Y1, "F.Cu"),
        rect(OPEN_X1, PLANE_EDGE, GND_X1, GND_Y1, "F.Cu"),
        rect(OPEN_X0, OPEN_BOTTOM, OPEN_X1, GND_Y1, "F.Cu"),
    ]


def build_footprint() -> list:
    """The port land and the ground plane, as one part with no zones."""
    n = [0]

    def uid():
        n[0] += 1
        return [Sym("uuid"), gp.U("simfp", str(n[0]))]

    def pad(number, at, size, layers):
        return [Sym("pad"), number, Sym("smd"), Sym("rect"),
                [Sym("at"), num(at[0]), num(at[1])],
                [Sym("size"), num(size[0]), num(size[1])],
                [Sym("layers")] + list(layers), uid()]

    def text(kind, value, y, layer, size):
        return [Sym("property"), kind.capitalize(), value,
                [Sym("at"), num(0), num(y), Sym("0")],
                [Sym("layer"), layer], uid(),
                [Sym("effects"), [Sym("font"), [Sym("size"), num(size), num(size)],
                                  [Sym("thickness"), num(size * 0.15)]]]]

    fp = [Sym("footprint"), FP_NAME,
          [Sym("version"), Sym("20241229")],
          [Sym("generator"), "gen_dn024_sim_board.py"],
          [Sym("generator_version"), "9.0"],
          [Sym("layer"), "F.Cu"],
          [Sym("descr"),
           "Simulation only. Pad 1 is the RFsim port land, the width of the "
           "50 ohm line. The pads numbered 2 are the DN024 ground plane - "
           f"{GND_W} x {GND_H} mm solid on B.Cu, and the same plane on F.Cu "
           "minus the opening around the feed and the pi network. They are "
           "pads and not zones on purpose: KiCad stores zones unfilled, and a "
           "solver reads the file, so an unfilled pour is no ground plane at "
           "all. Do not put this on a board you intend to fabricate."],
          [Sym("tags"), "simulation port ground plane RFsim openEMS DN024"],
          [Sym("attr"), Sym("exclude_from_pos_files"),
           Sym("exclude_from_bom"), Sym("allow_missing_courtyard")],
          text("reference", "REF**", -(PORT_PAD_L / 2 + 1.4), "F.SilkS", 1.0),
          text("value", FP_NAME, PORT_PAD_L / 2 + 1.4, "F.Fab", 0.8),
          pad("1", (0, 0), (W50, PORT_PAD_L), ("F.Cu", "F.Mask"))]
    for cx, cy, w, h, layer in plane_rects():
        fp.append(pad("2", (cx, cy), (w, h),
                      (layer, "B.Mask" if layer == "B.Cu" else "F.Mask")))
    fp.append([Sym("embedded_fonts"), Sym("no")])
    return fp


TI_PARTS = ti.parts          # captured before build_board() swaps ti.parts out


def parts() -> list:
    """The TI-form parts, minus the connector and Z62, plus the port land."""
    base = {p["ref"]: p for p in TI_PARTS()}
    z61, z63, ae1 = base["Z61"], base["Z63"], base["AE1"]
    z61 = dict(z61, nets={"1": "ANT_FEED", "2": "GND"}, sch=(78.74, 92.71, 0),
               ref_at=(81.28, 91.44), val_at=(81.28, 93.98))
    z63 = dict(z63, sch=(111.76, 92.71, 0),
               ref_at=(114.3, 91.44), val_at=(114.3, 93.98))
    port = dict(ref="P1", lib=f"{LIB_NICK}:RF_PORT", value="50R port",
                fp=f"{LIB_NICK}:{FP_NAME}", sch=(63.5, 88.9, 0),
                # rotation 0, not 90: this footprint carries the ground
                # plane, and its pads are drawn in board orientation already
                pcb=(PORT_AT[0], PORT_AT[1], 0),
                nets={"1": "ANT_FEED", "2": "GND"},
                ref_at=(58.42, 85.09), val_at=(58.42, 87.63),
                in_bom=False,
                desc="RFsim port land and the ground plane, in one part. "
                     "Attach port 1 to pad 1; pad 2 is the plane, and the "
                     "B.Cu half of it runs directly under pad 1 as the "
                     "port's reference")
    return [port, z61, z63, ae1]


def feed_tracks() -> list:
    """Antenna -> Z63 tap -> straight through where Z62 was -> Z61 tap -> port.

    One net the whole way: the 0402 land that carries 3.9 pF on the
    fabrication board is a continuous run of copper here.
    """
    taper_top = ti.Z61_AT[1] + 2.0
    taper_len, steps = 3.0, 5
    tracks = [
        ((FEED_X, ANT_ORIGIN[1]), (FEED_X, ti.Z63_AT[1]), W_ANT, "ANT_FEED"),
        ((FEED_X, ti.Z63_AT[1]), (ti.Z63_AT[0] - PAD_DX, ti.Z63_AT[1]),
         W_PI, "ANT_FEED"),
        # where Z62 was: no gap, no part, just copper
        ((FEED_X, ti.Z63_AT[1]), (FEED_X, ti.Z61_AT[1]), W_PI, "ANT_FEED"),
        ((FEED_X, ti.Z61_AT[1]), (ti.Z61_AT[0] - PAD_DX, ti.Z61_AT[1]),
         W_PI, "ANT_FEED"),
        ((FEED_X, ti.Z61_AT[1]), (FEED_X, taper_top), W_PI, "ANT_FEED"),
    ]
    for i in range(steps):
        y0 = taper_top + i * taper_len / steps
        y1 = taper_top + (i + 1) * taper_len / steps
        width = W_PI + (W50 - W_PI) * (i + 0.5) / steps
        tracks.append(((FEED_X, y0), (FEED_X, y1), round(width, 3), "ANT_FEED"))
    # the 50 ohm run into the port pad.  No launch neck: there are no ground
    # posts here to squeeze past, so the line stays 50 ohm to the port.
    tracks.append(((FEED_X, taper_top + taper_len),
                   (FEED_X, PORT_AT[1]), W50, "ANT_FEED"))
    for at in (ti.Z63_AT, ti.Z61_AT):
        tracks.append(((at[0] + PAD_DX, at[1]), (at[0] + 1.4, at[1]),
                       W_PI, "GND"))
    return tracks


def build_board() -> list:
    """The TI-form board, with the zones taken out and the copper closed up."""
    # ti.build_board() reads these by name at call time, so swapping them
    # here is what makes it build this board instead of the fabrication one.
    ti.parts, ti.feed_tracks, ti.NETS, ti.TITLE = parts, feed_tracks, NETS, TITLE
    pcb = ti.build_board()

    def drop(node) -> bool:
        if node[0] == "zone":
            name = find(node, "name")
            if name is not None and str(name[1]) == "PI_NETWORK_CLEARANCE":
                return True
            return not find(node, "keepout")        # the two ground pours
        if node[0] == "gr_text" and str(node[1]).startswith(
                ("TI DN024 monopole - 868", "J1 = P6")):
            return True
        return False

    pcb = [node for node in pcb if not drop(node)]
    tail = pcb.pop()                                # (embedded_fonts no) last
    pcb.append(gp.gr_text("TI DN024 monopole - RFsim model, NOT FOR FABRICATION",
                          (BOARD_X0 + 1.5, BOARD_Y1 - 8.0), "F.SilkS", size=1.1))
    pcb.append(gp.gr_text("Z62 shorted (SWRA227E 4.3.1) - ground is pads, not "
                          "zones, so no fill step",
                          (BOARD_X0 + 1.5, BOARD_Y1 - 6.4), "F.SilkS", size=0.9))
    pcb.append(gp.gr_text("PORT 1: P1 pad 1 over the B.Cu plane - microstrip "
                          "(MSL), not CPW",
                          (BOARD_X0 + 0.8, PORT_AT[1] - 4.0), "Cmts.User", size=0.8))
    pcb.append(gp.gr_text("EXPECT " + ", ".join(
        f"{f:.0f} MHz S11 = {s11_db(swr):.1f} dB (SWR {swr})"
        for f, swr in TARGETS), (BOARD_X0 + 0.8, BOARD_Y1 - 1.2),
        "Cmts.User", size=0.8))
    pcb.append(tail)
    return pcb


def build_schematic() -> list:
    gp.PROJECT, gp.TITLE, gp.SCH_NOTE = PROJECT, TITLE, SCH_NOTE
    gp.PARTS = parts()
    gp.WIRES = [
        ((67.31, 88.9), (146.05, 88.9)),        # P1 pin 1 -> AE1, one net
        ((63.5, 93.98), (63.5, 99.06)),         # P1 ground pad -> GND
        ((63.5, 99.06), (58.42, 99.06)),        # GND -> PWR_FLAG
        ((78.74, 96.52), (78.74, 99.06)),       # Z61 -> GND
        ((111.76, 96.52), (111.76, 99.06)),     # Z63 -> GND
    ]
    gp.JUNCTIONS = [(63.5, 99.06), (78.74, 88.9), (111.76, 88.9)]
    gp.LABELS = [("ANT_FEED", (95.25, 88.9))]
    gp.POWER = [("#PWR01", (63.5, 99.06)), ("#PWR02", (78.74, 99.06)),
                ("#PWR03", (111.76, 99.06))]
    gp.PWR_FLAGS = [("#FLG01", (58.42, 99.06))]
    return gp.build_schematic()


def main() -> None:
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter
                            ).parse_args()
    FP_DEST.parent.mkdir(parents=True, exist_ok=True)
    FP_DEST.write_text(dumps(build_footprint()) + "\n")
    print(f"wrote library/{LIB_NICK}.pretty/{FP_DEST.name}")
    print(f"  port pad {W50} x {PORT_PAD_L} mm, ground {GND_W} x {GND_H} mm "
          f"as {len(plane_rects())} pads on B.Cu + F.Cu - no fill step")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for suffix, node in (("kicad_sch", build_schematic()),
                         ("kicad_pcb", build_board())):
        dest = OUT_DIR / f"{PROJECT}.{suffix}"
        dest.write_text(dumps(node) + "\n")
        print(f"wrote {dest.relative_to(PRJ_DIR.parent)}")
    dest = OUT_DIR / f"{PROJECT}.kicad_pro"
    dest.write_text(json.dumps(gp.build_project(), indent=2) + "\n")
    print(f"wrote {dest.relative_to(PRJ_DIR.parent)}")
    for f, swr in TARGETS:
        print(f"  expect {f:7.0f} MHz  SWR {swr}  ->  S11 = {s11_db(swr):6.1f} dB"
              "   (SWRA227E 4.3.1, Z62 = 0 ohm)")


if __name__ == "__main__":
    main()
