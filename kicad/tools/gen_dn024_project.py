#!/usr/bin/env python3
"""Generate the TI DN024 monopole project: schematic, board and project file.

Dual band, 868 + 2440 MHz, on the reference design's own ground plane.  Both
of those are choices with consequences, so they are written down here:

  * **Dual band.**  L4 stays at its published 38.0 mm, so the radiator is an
    exact copy of Table 1 with nothing guessed.  The single band variant needs
    L4 "shortened to the silkscreen marking" and SWRA227E dimensions that
    marking nowhere - it can only be read off Figure 2 by eye, which would
    stop the antenna being an exact copy.
  * **43 x 63 mm ground plane**, the size Table 2 and Table 3 name.  The note
    warns that "Optimum length for the last antenna segment is dependent on
    the geometry of the ground plane.  For larger ground planes L4 would have
    to be further reduced or the antenna match re-calculated", so this is the
    one ground plane on which the published matching values apply as given.

The matching network is TI's, not this project's.  Unlike SWRA117D, DN024
requires one - "It is recommended to use a pi-matching network at the feed
point of the antenna ... since the geometry of the ground plane affects the
impedance of the antenna" - and Table 3 gives the dual band BOM:

    Z61  NC        shunt, connector side
    Z62  3.9 pF    series
    Z63  NC        shunt, antenna side

which measured SWR 1.2 at 868 MHz and 1.6 at 2.44 GHz.  Z61 and Z63 are laid
out and left unfitted, because the note's whole reason for the network is to
have somewhere to compensate detuning from enclosures and nearby objects.

Which of Z61/Z63 sits on which side of Z62 is inferred, not stated: Figure 2
draws Z63 above Z61 with the connector below both, and the single band BOM -
series 1.8 nH with a shunt 2.7 pF - is an L match that only works with the
shunt on the source side.  Both readings put Z61 nearest the connector.

    python3 kicad/tools/gen_dn024_project.py
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_project as gp  # noqa: E402
from sexpr import Sym, dumps, num  # noqa: E402

gp.NAMESPACE = uuid.UUID("7a3c5d91-4e62-5b07-9d18-3c6f2a8b1e45")
gp.ROOT_UUID = gp.U("sheet", "root")
gp.LIB_NICK = LIB_NICK = "TI_DN024"
gp.PROJECT = PROJECT = "dn024_monopole_868_2440"

PRJ_DIR = gp.PRJ_DIR
OUT_DIR = PRJ_DIR / "dn024"

# ------------------------------------------------------------------- board
# SWRA227E Table 2/3: PCB board 45 x 95 mm, GND 43 x 63 mm.  The ground plane
# sits 1 mm in from the sides and the bottom; the antenna's 25 mm sits above
# it; what is left is bare FR4 at the top, which is what the reference board
# has and what its OTA numbers were measured with.
BOARD_X0, BOARD_Y0 = 100.0, 60.0
BOARD_W, BOARD_H = 45.0, 95.0
BOARD_X1, BOARD_Y1 = BOARD_X0 + BOARD_W, BOARD_Y0 + BOARD_H
GND_W, GND_H = 43.0, 63.0
GND_X0 = BOARD_X0 + (BOARD_W - GND_W) / 2
GND_X1 = GND_X0 + GND_W
GND_Y1 = BOARD_Y1 - 1.0
PLANE_EDGE = GND_Y1 - GND_H                 # top of the ground plane

ANT_FOOTPRINT = "TI_DN024_Monopole_868_2440"
L5 = 1.0                                     # Table 1: plane edge to the feed
FEED_X = BOARD_X0 + BOARD_W / 2
ANT_ORIGIN = (FEED_X, PLANE_EDGE - L5)

SUB_H, SUB_ER = gp.SUB_H, gp.SUB_ER          # 1.6 mm FR4, as DN024 specifies
W50 = gp.W50                                 # 2.95 mm on this stackup
W_ANT = 2.0                                  # the antenna's own trace width
W_PI = 0.6                                   # interconnect inside the network
POUR_GAP = gp.POUR_GAP

# the pi network, from the antenna down to the connector
Z63_AT = (FEED_X + 3.0, PLANE_EDGE + 3.0)    # shunt, antenna side
Z62_AT = (FEED_X, PLANE_EDGE + 6.5)          # series
Z61_AT = (FEED_X + 3.0, PLANE_EDGE + 10.0)   # shunt, connector side
PAD_DX = 0.48                                # 0402 land, pad centre offset
PI_BOX = (FEED_X - 5.5, PLANE_EDGE, FEED_X + 6.0, PLANE_EDGE + 14.0)
TAPER_TOP, TAPER_LEN, TAPER_STEPS = PI_BOX[3], 3.0, 5
LAUNCH_Y = BOARD_Y1 - gp.PAD_LEN_IN / 2

FENCE_PITCH, GRID_PITCH = 3.0, 4.0
VIA_SIZE, VIA_DRILL = 0.6, 0.3

NETS = {"": 0, "GND": 1, "ANT_FEED": 2, "RF_IN": 3}

TITLE = ("TI DN024 (SWRA227E) meandering monopole - 868 + 2440 MHz dual band, "
         "reference 43 x 63 mm ground plane")

SCH_NOTE = (
    "TI DN024 / SWRA227E meandering monopole, dual band 868 + 2440 MHz.\n"
    "\n"
    "Unlike the SWRA117D inverted-F, this antenna is NOT a 50 ohm part: the\n"
    "note requires a pi network at the feed and gives its values, because the\n"
    "ground plane geometry sets the antenna's impedance.\n"
    "\n"
    "Table 3, dual band BOM:   Z61 NC   Z62 3.9 pF series   Z63 NC\n"
    "  -> measured SWR 1.2 at 868 MHz and 1.6 at 2.44 GHz\n"
    "Table 2, single band 868: Z61 2.7 pF   Z62 1.8 nH series   Z63 NC\n"
    "  -> SWR 1.1, but it also needs L4 shortened, which the note does not\n"
    "     dimension, so that variant is not an exact copy of Table 1.\n"
    "\n"
    "Z61 and Z63 are laid out and left unfitted on purpose: the note's reason\n"
    "for the network is to have somewhere to compensate detuning caused by\n"
    "plastic encapsulation and objects near the antenna.\n"
    "\n"
    "Ground plane 43 x 63 mm - the size the published match belongs to. A\n"
    "larger plane needs L4 reduced or the match recalculated (section 3).\n"
    "No ground plane, no copper and no components under or beside the\n"
    "antenna; 2.5 mm clear either side, as the reference board leaves."
)


def parts() -> list:
    def cap(ref, value, at, pcb, nets, desc, dnp=False, sch_rot=0):
        # a series part lies along the wire, a shunt part hangs off it
        label = (2.54, -3.81) if sch_rot else (2.54, -1.27)
        return dict(ref=ref, lib=f"{LIB_NICK}:C", value=value, fp="SWRA117D_RF:"
                    "Chip_0402_1005Metric_RF", sch=(at[0], at[1], sch_rot),
                    pcb=pcb, nets=nets,
                    ref_at=(at[0] + label[0], at[1] + label[1]),
                    val_at=(at[0] + label[0], at[1] + label[1] + 2.54),
                    dnp=dnp, in_bom=not dnp, desc=desc)

    return [
        dict(ref="J1", lib=f"{LIB_NICK}:Conn_Coaxial_SMA", value="SMA edge launch",
             fp="SWRA117D_RF:SMA_EdgeMount_Generic", sch=(63.5, 88.9, 0),
             pcb=(FEED_X, BOARD_Y1, 90), nets={"1": "RF_IN", "2": "GND"},
             ref_at=(63.5, 81.28), val_at=(63.5, 83.82),
             desc="Coaxial connector, 50 ohm test port"),
        cap("Z61", "DNP", (78.74, 92.71), (Z61_AT[0], Z61_AT[1], 0),
            {"1": "RF_IN", "2": "GND"},
            "Pi network, shunt on the connector side. Not fitted for dual band "
            "(SWRA227E Table 3); 2.7 pF for the single band 868 MHz build "
            "(Table 2)", dnp=True),
        cap("Z62", "3.9pF", (95.25, 88.9), (Z62_AT[0], Z62_AT[1], 90),
            {"1": "RF_IN", "2": "ANT_FEED"},
            "Pi network, series. SWRA227E Table 3 dual band: 3.9 pF C0G 0402 "
            "(Murata GRM1555C1H3R9CZ01D). 1.8 nH for the single band build",
            sch_rot=90),
        cap("Z63", "DNP", (111.76, 92.71), (Z63_AT[0], Z63_AT[1], 0),
            {"1": "ANT_FEED", "2": "GND"},
            "Pi network, shunt on the antenna side. Not fitted in either "
            "published build; laid out for retuning against an enclosure",
            dnp=True),
        dict(ref="AE1", lib=f"{LIB_NICK}:ANT_DN024_Monopole",
             value="ANT_DN024_Monopole", fp=f"{LIB_NICK}:{ANT_FOOTPRINT}",
             sch=(146.05, 81.28, 0), pcb=ANT_ORIGIN + (0,),
             nets={"1": "ANT_FEED"},
             ref_at=(150.0, 77.47), val_at=(150.0, 80.01),
             fp_ref_at=(0.0, 3.2), in_bom=False,
             datasheet="https://www.ti.com/lit/an/swra227e/swra227e.pdf",
             desc="TI DN024 meandering monopole, 868 + 2440 MHz, exact copy of "
                  "SWRA227E Table 1"),
    ]


WIRES = [
    ((68.58, 88.9), (91.44, 88.9)),        # J1 -> Z62 pin 1
    ((99.06, 88.9), (146.05, 88.9)),       # Z62 pin 2 -> AE1
    ((63.5, 93.98), (63.5, 99.06)),        # J1 shell -> GND
    ((63.5, 99.06), (58.42, 99.06)),       # GND -> PWR_FLAG
    ((78.74, 96.52), (78.74, 99.06)),      # Z61 -> GND
    ((111.76, 96.52), (111.76, 99.06)),    # Z63 -> GND
]
JUNCTIONS = [(63.5, 99.06)]
LABELS = [("RF_IN", (73.66, 88.9)), ("ANT_FEED", (104.14, 88.9))]
POWER = [("#PWR01", (63.5, 99.06)), ("#PWR02", (78.74, 99.06)),
         ("#PWR03", (111.76, 99.06))]
PWR_FLAGS = [("#FLG01", (58.42, 99.06))]


def feed_tracks() -> list:
    """Antenna -> Z63 tap -> Z62 -> Z61 tap -> taper -> 50 ohm line -> J1."""
    z63_pad = (Z63_AT[0] - PAD_DX, Z63_AT[1])
    z61_pad = (Z61_AT[0] - PAD_DX, Z61_AT[1])
    z62_ant = (Z62_AT[0], Z62_AT[1] - PAD_DX)      # pad 2, antenna side
    z62_in = (Z62_AT[0], Z62_AT[1] + PAD_DX)       # pad 1, connector side

    tracks = [
        # antenna side: the antenna's own 2.0 mm width down to the tap
        ((FEED_X, ANT_ORIGIN[1]), (FEED_X, Z63_AT[1]), W_ANT, "ANT_FEED"),
        ((FEED_X, Z63_AT[1]), (FEED_X, z62_ant[1]), W_PI, "ANT_FEED"),
        ((FEED_X, Z63_AT[1]), z63_pad, W_PI, "ANT_FEED"),
        # connector side
        ((FEED_X, z62_in[1]), (FEED_X, Z61_AT[1]), W_PI, "RF_IN"),
        ((FEED_X, Z61_AT[1]), z61_pad, W_PI, "RF_IN"),
        ((FEED_X, Z61_AT[1]), (FEED_X, TAPER_TOP), W_PI, "RF_IN"),
    ]
    # widen to the 50 ohm line: 0.6 mm cannot simply butt onto 2.95 mm
    for i in range(TAPER_STEPS):
        y0 = TAPER_TOP + i * TAPER_LEN / TAPER_STEPS
        y1 = TAPER_TOP + (i + 1) * TAPER_LEN / TAPER_STEPS
        width = W_PI + (W50 - W_PI) * (i + 0.5) / TAPER_STEPS
        tracks.append(((FEED_X, y0), (FEED_X, y1), round(width, 3), "RF_IN"))
    tracks.append(((FEED_X, TAPER_TOP + TAPER_LEN), (FEED_X, LAUNCH_Y),
                   W50, "RF_IN"))
    # the shunt pads' ground side, out to a via into the bottom plane
    for at in (Z63_AT, Z61_AT):
        tracks.append(((at[0] + PAD_DX, at[1]), (at[0] + 1.4, at[1]), W_PI, "GND"))
    return tracks


def stitching() -> list[tuple[float, float]]:
    out = [(Z63_AT[0] + 1.4, Z63_AT[1]), (Z61_AT[0] + 1.4, Z61_AT[1])]
    x = GND_X0 + 1.2
    while x <= GND_X1 - 1.2:
        if abs(x - FEED_X) > W50 / 2 + POUR_GAP + 0.5:
            out.append((x, PLANE_EDGE + 1.0))
        x += FENCE_PITCH
    half = W50 / 2 + POUR_GAP
    y = PLANE_EDGE + 1.0 + GRID_PITCH
    while y <= GND_Y1 - 1.2:
        x = GND_X0 + 1.2
        while x <= GND_X1 - 1.2:
            inside_pi = (PI_BOX[0] - 0.8 <= x <= PI_BOX[2] + 0.8
                         and PI_BOX[1] <= y <= PI_BOX[3] + 0.8)
            in_corridor = FEED_X - half - 0.5 <= x <= FEED_X + half + 0.5
            at_launch = abs(x - FEED_X) <= 7.0 and y >= LAUNCH_Y - 2.5
            crowded = any(math.dist((x, y), p) < 2.0 for p in out)
            if not (inside_pi or in_corridor or at_launch or crowded):
                out.append((x, y))
            x += GRID_PITCH
        y += GRID_PITCH
    out += [(FEED_X + s * (gp.LAUNCH_OFFSET + dx), LAUNCH_Y + dy)
            for s in (-1, 1) for dx in (-1.0, 1.0) for dy in (-0.8, 0.8)]
    return out


def build_board() -> list:
    gp.PARTS, gp.NETS = parts(), NETS
    layers = [(0, "F.Cu", "signal", None), (31, "B.Cu", "signal", None),
              (32, "B.Adhes", "user", "B.Adhesive"), (33, "F.Adhes", "user", "F.Adhesive"),
              (34, "B.Paste", "user", None), (35, "F.Paste", "user", None),
              (36, "B.SilkS", "user", "B.Silkscreen"), (37, "F.SilkS", "user", "F.Silkscreen"),
              (38, "B.Mask", "user", None), (39, "F.Mask", "user", None),
              (40, "Dwgs.User", "user", "User.Drawings"), (41, "Cmts.User", "user", "User.Comments"),
              (42, "Eco1.User", "user", "User.Eco1"), (43, "Eco2.User", "user", "User.Eco2"),
              (44, "Edge.Cuts", "user", None), (45, "Margin", "user", None),
              (46, "B.CrtYd", "user", "B.Courtyard"), (47, "F.CrtYd", "user", "F.Courtyard"),
              (48, "B.Fab", "user", None), (49, "F.Fab", "user", None)]
    layer_nodes = [Sym("layers")]
    for number, name, ltype, alias in layers:
        node = [Sym(str(number)), name, Sym(ltype)]
        if alias:
            node.append(alias)
        layer_nodes.append(node)

    pcb = [Sym("kicad_pcb"),
           [Sym("version"), Sym("20241229")],
           [Sym("generator"), "gen_dn024_project.py"],
           [Sym("generator_version"), "9.0"],
           [Sym("general"), [Sym("thickness"), num(SUB_H + 0.09)],
            [Sym("legacy_teardrops"), Sym("no")]],
           [Sym("paper"), "A4"],
           [Sym("title_block"),
            [Sym("title"), TITLE],
            [Sym("date"), "2026-09-15"],
            [Sym("rev"), "A"],
            [Sym("comment"), Sym("1"),
             f"2 layer, {BOARD_W} x {BOARD_H} mm, {SUB_H} mm FR4 er={SUB_ER}"],
            [Sym("comment"), Sym("2"),
             f"Ground plane {GND_W} x {GND_H} mm - the published match belongs to it"],
            [Sym("comment"), Sym("3"),
             "Dual band: Z62 = 3.9 pF series, Z61 and Z63 not fitted (Table 3)"]],
           layer_nodes,
           [Sym("setup"), gp.stackup(),
            [Sym("pad_to_mask_clearance"), Sym("0")],
            [Sym("allow_soldermask_bridges_in_footprints"), Sym("no")]]]

    for name, number in NETS.items():
        pcb.append([Sym("net"), Sym(str(number)), name])
    for part in gp.PARTS:
        pcb.append(gp.board_footprint(part))

    corners = [(BOARD_X0, BOARD_Y0), (BOARD_X1, BOARD_Y0),
               (BOARD_X1, BOARD_Y1), (BOARD_X0, BOARD_Y1)]
    for i in range(4):
        pcb.append(gp.gr_line(corners[i], corners[(i + 1) % 4], "Edge.Cuts"))

    pcb.append(gp.gr_line((BOARD_X0, PLANE_EDGE), (BOARD_X1, PLANE_EDGE),
                          "Cmts.User", 0.12))
    pcb.append(gp.gr_text("GND plane edge - no copper above this line on any layer",
                          (BOARD_X0 + 0.8, PLANE_EDGE - 0.8), "Cmts.User", size=0.9))
    pcb.append(gp.gr_text("ANTENNA KEEP-OUT - 2.5 mm clear either side",
                          (BOARD_X0 + 1.2, BOARD_Y0 + 3.0), "F.SilkS", size=1.0))
    pcb.append(gp.gr_text("TI DN024 monopole - 868 + 2440 MHz",
                          (BOARD_X0 + 1.5, BOARD_Y1 - 8.0), "F.SilkS", size=1.2))
    pcb.append(gp.gr_text(f"Z62 = 3.9pF series; Z61, Z63 NC (SWRA227E Table 3)",
                          (BOARD_X0 + 1.5, BOARD_Y1 - 6.4), "F.SilkS", size=0.9))

    for a, b, width, net in feed_tracks():
        pcb.append(gp.segment(a, b, width, net))
    for pos in stitching():
        pcb.append(gp.via(pos, size=VIA_SIZE, drill=VIA_DRILL))

    plane = [(GND_X0, PLANE_EDGE), (GND_X1, PLANE_EDGE),
             (GND_X1, GND_Y1), (GND_X0, GND_Y1)]
    pcb.append(gp.gnd_zone("F.Cu", plane))
    pcb.append(gp.gnd_zone("B.Cu", plane))
    pcb.append(gp.keepout_zone("ANTENNA_KEEPOUT",
                               [(BOARD_X0 - 0.5, BOARD_Y0 - 0.5),
                                (BOARD_X1 + 0.5, BOARD_Y0 - 0.5),
                                (BOARD_X1 + 0.5, PLANE_EDGE),
                                (BOARD_X0 - 0.5, PLANE_EDGE)]))
    # the network sits in a cut-out, as Figure 2 draws it: its shunt pads reach
    # the plane through vias, not through the top pour
    pcb.append(gp.keepout_zone("PI_NETWORK_CLEARANCE",
                               [(PI_BOX[0], PI_BOX[1]), (PI_BOX[2], PI_BOX[1]),
                                (PI_BOX[2], PI_BOX[3]), (PI_BOX[0], PI_BOX[3])],
                               layers=("F.Cu",), tracks="allowed", vias="allowed"))
    half = W50 / 2 + POUR_GAP
    pcb.append(gp.keepout_zone("RF_POUR_KEEPAWAY",
                               [(FEED_X - half, PI_BOX[3]), (FEED_X + half, PI_BOX[3]),
                                (FEED_X + half, BOARD_Y1 + 0.5),
                                (FEED_X - half, BOARD_Y1 + 0.5)],
                               layers=("F.Cu",), tracks="allowed", vias="allowed"))
    pcb.append([Sym("embedded_fonts"), Sym("no")])
    return pcb


def build_schematic() -> list:
    gp.TITLE, gp.SCH_NOTE, gp.NETS = TITLE, SCH_NOTE, NETS
    gp.PARTS, gp.WIRES, gp.JUNCTIONS = parts(), WIRES, JUNCTIONS
    gp.LABELS, gp.POWER, gp.PWR_FLAGS = LABELS, POWER, PWR_FLAGS
    return gp.build_schematic()


def build_project() -> dict:
    pro = gp.build_project()
    pro["meta"]["filename"] = f"{PROJECT}.kicad_pro"
    pro["sheets"] = [[gp.ROOT_UUID, "Root"]]
    return pro


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{PROJECT}.kicad_sch").write_text(dumps(build_schematic()) + "\n")
    (OUT_DIR / f"{PROJECT}.kicad_pcb").write_text(dumps(build_board()) + "\n")
    (OUT_DIR / f"{PROJECT}.kicad_pro").write_text(
        json.dumps(build_project(), indent=2) + "\n")
    for ext in ("kicad_sch", "kicad_pcb", "kicad_pro"):
        print(f"wrote {(OUT_DIR / f'{PROJECT}.{ext}').relative_to(PRJ_DIR.parent)}")


if __name__ == "__main__":
    main()
