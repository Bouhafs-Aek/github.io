#!/usr/bin/env python3
"""Generate the simulation-only board: the SWRA117D antenna and nothing else.

The fabrication board (``swra117d_2g4_antenna.kicad_pcb``) carries an SMA
connector and the 50 ohm microstrip that reaches it.  Both are real hardware
and both end up inside the answer when you simulate that board: the resonance
you read off S11 is the resonance of *antenna + line + launch*.

This board is the model you point a field solver at.  It is SWRA117D Figure 3
and Table 1 and nothing else:

  * the same antenna footprint, byte for byte, on the same 1.6 mm FR4;
  * the same ground plane, top and bottom, starting at the same plane edge;
  * no connector, no feed line, no taper, no matching network;
  * the port is the gap between the antenna's own feed pad and the plane
    edge - a direct feed, PORT_GAP mm of it, cut into the top pour so that
    re-filling the zones in KiCad cannot change it;
  * that same cut runs on to the short pad, so the pour meets the radiator
    only at the short and Table 1's D5 = 1.40 mm stays the feed-to-short
    distance instead of being whatever the pour happens to touch first;
  * ground vias right at that gap, so the port's return current reaches the
    bottom plane at the port instead of somewhere downstream.

Run it, then open sim/board/swra117d_2g4_sim.kicad_pcb:

    python3 kicad/tools/gen_sim_board.py
"""

from __future__ import annotations

import copy
import json
import math
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_project as gp  # noqa: E402
from sexpr import Sym, dumps, find, find_all, num, parse  # noqa: E402

# Its own uuid namespace, so nothing in this board shares an identity with the
# fabrication board even though the two are generated from the same sources.
gp.NAMESPACE = uuid.UUID("2f81b6ce-7d44-5a0e-9b3c-5e1d0c72a985")
U = gp.U

PRJ_DIR = gp.PRJ_DIR
OUT_DIR = PRJ_DIR / "sim" / "board"
PROJECT = "swra117d_2g4_sim"
LIB_NICK = gp.LIB_NICK
FP_DIR = gp.FP_DIR

BOARD_X0, BOARD_Y0 = gp.BOARD_X0, gp.BOARD_Y0
BOARD_X1, BOARD_Y1 = gp.BOARD_X1, gp.BOARD_Y1
ANT_ORIGIN = gp.ANT_ORIGIN
ANT_FOOTPRINT = gp.ANT_FOOTPRINT
FEED_X = gp.FEED_X
GND_EDGE_Y = gp.GND_EDGE_Y
SUB_H, SUB_ER, SUB_TAND = gp.SUB_H, gp.SUB_ER, gp.SUB_TAND
NETS = gp.NETS

# The port.  A lumped/gap port needs a gap that survives two things: KiCad
# re-filling the zones (hence a keep-out, not the pour clearance) and the
# solver's mesh (hence 0.4 mm rather than the 0.2 mm KiCad would leave, which
# is under two cells at the 0.25 mm resolution the openEMS script defaults to).
PORT_GAP = 0.4
VIA_SIZE, VIA_DRILL = 0.6, 0.3
PORT_VIA_PITCH = 0.7        # vias right at the port
FENCE_PITCH = 3.0           # lambda/19 in FR4 at 2.45 GHz, along the plane edge
GRID_PITCH = 5.0            # over the rest of the pour

TITLE = "SWRA117D 2.45 GHz IFA - simulation model, direct port (no connector)"


def antenna_geometry() -> dict:
    """The parts of the antenna the port is built against, read from the file.

    Nothing here is written down twice: rescale or redraw the antenna and the
    port gap follows the pad and the bar instead of drifting off them.
    """
    fp = parse((FP_DIR / f"{ANT_FOOTPRINT}.kicad_mod").read_text())

    def pad_rect(number):
        pad = next(p for p in find_all(fp, "pad") if str(p[1]) == number)
        at, size = find(pad, "at"), find(pad, "size")
        cx = ANT_ORIGIN[0] + float(at[1])
        cy = ANT_ORIGIN[1] + float(at[2])
        w, h = float(size[1]), float(size[2])
        return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

    poly = [(ANT_ORIGIN[0] + float(xy[1]), ANT_ORIGIN[1] + float(xy[2]))
            for xy in find(find(fp, "fp_poly"), "pts")[1:]]
    # the bottom bar: the only radiator copper that reaches past the plane edge
    bar = [p for p in poly if p[1] >= GND_EDGE_Y - 1e-9]
    return dict(feed=pad_rect("1"), short=pad_rect("2"),
                bar_left=min(p[0] for p in bar),
                bar_bottom=max(p[1] for p in bar))


ANT = antenna_geometry()
PAD = ANT["feed"]
# The cut in the top pour.  It has to do two jobs, and they set its two ends:
#
#   * open the port, PORT_GAP below the feed pad;
#   * stop exactly at the short pad's left edge.  Anywhere the pour touches
#     the bottom bar is a short to ground, so if the cut ended early the pour
#     would short the bar closer to the feed than the short pad does and
#     Table 1's D5 = 1.40 mm - the dimension that sets the input impedance -
#     would no longer be the feed-to-short distance.
NOTCH = (ANT["bar_left"] - PORT_GAP, GND_EDGE_Y,
         ANT["short"][0], ANT["bar_bottom"] + PORT_GAP)


def antenna_footprint() -> list:
    """The antenna footprint embedded verbatim, with nets on its two pads."""
    src = parse((FP_DIR / f"{ANT_FOOTPRINT}.kicad_mod").read_text())
    nets = {"1": "ANT_FEED", "2": "GND"}
    out = [Sym("footprint"), f"{LIB_NICK}:{src[1]}",
           [Sym("layer"), "F.Cu"],
           [Sym("uuid"), U("fp", "AE1")],
           [Sym("at"), num(ANT_ORIGIN[0]), num(ANT_ORIGIN[1])]]
    for child in src[2:]:
        head = child[0]
        if head in ("version", "generator", "generator_version", "layer",
                    "embedded_fonts"):
            continue
        child = copy.deepcopy(child)
        if head == "property":
            if child[1] == "Reference":
                child[2] = "AE1"
                at = find(child, "at")
                at[1], at[2] = num(-6.0), num(1.6)
            elif child[1] == "Value":
                child[2] = ANT_FOOTPRINT
            child.append([Sym("unlocked"), Sym("yes")])
        elif head == "fp_text":
            child.append([Sym("unlocked"), Sym("yes")])
        elif head == "pad":
            net = nets[str(child[1])]
            child.append([Sym("net"), Sym(str(NETS[net])), net])
            child.append([Sym("pinfunction"), net])
            child.append([Sym("pintype"), "passive"])
        out.append(child)
    out.append([Sym("embedded_fonts"), Sym("no")])
    return out


def port_vias() -> list[tuple[float, float]]:
    """Ground vias at the port, then along the plane edge, then everywhere else.

    The first group is the one the user can see the effect of: without it the
    return current at the port has to run sideways across the top pour until it
    finds a via, and that detour is in series with the antenna.
    """
    y = NOTCH[3] + VIA_SIZE / 2 + 0.15       # clear of the notch, clear of the pad
    out = [(FEED_X + k * PORT_VIA_PITCH, y) for k in (-2, -1, 0, 1, 2)]

    x = BOARD_X0 + 1.5
    while x <= BOARD_X1 - 1.5:
        if all(abs(x - px) > 1.0 for px, _ in out):
            out.append((x, y))
        x += FENCE_PITCH

    row = GND_EDGE_Y + 1.5 + GRID_PITCH
    while row <= BOARD_Y1 - 1.0:
        x = BOARD_X0 + 1.5
        while x <= BOARD_X1 - 1.5:
            if all(math.dist((x, row), p) >= 2.0 for p in out):
                out.append((x, row))
            x += GRID_PITCH
        row += GRID_PITCH
    return out


def build_board() -> list:
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
           [Sym("generator"), "gen_sim_board.py"],
           [Sym("generator_version"), "9.0"],
           [Sym("general"), [Sym("thickness"), num(SUB_H + 0.09)],
            [Sym("legacy_teardrops"), Sym("no")]],
           [Sym("paper"), "A4"],
           [Sym("title_block"),
            [Sym("title"), TITLE],
            [Sym("date"), "2026-09-13"],
            [Sym("rev"), "A"],
            [Sym("comment"), Sym("1"), f"2 layer, {SUB_H} mm FR4 er={SUB_ER}, 35 um Cu"],
            [Sym("comment"), Sym("2"),
             f"Port: AE1 pad 1 to the plane edge, {PORT_GAP} mm gap, lumped, 50 ohm"],
            [Sym("comment"), Sym("3"),
             "No connector, no feed line: what is simulated is the antenna alone"]],
           layer_nodes,
           [Sym("setup"), gp.stackup(),
            [Sym("pad_to_mask_clearance"), Sym("0")],
            [Sym("allow_soldermask_bridges_in_footprints"), Sym("no")]]]

    for name, number in NETS.items():
        pcb.append([Sym("net"), Sym(str(number)), name])

    pcb.append(antenna_footprint())

    corners = [(BOARD_X0, BOARD_Y0), (BOARD_X1, BOARD_Y0),
               (BOARD_X1, BOARD_Y1), (BOARD_X0, BOARD_Y1)]
    for i in range(4):
        pcb.append(gp.gr_line(corners[i], corners[(i + 1) % 4], "Edge.Cuts"))

    # documentation: the plane edge and the port, drawn where they are
    pcb.append(gp.gr_line((BOARD_X0, GND_EDGE_Y), (BOARD_X1, GND_EDGE_Y), "Cmts.User", 0.12))
    pcb.append(gp.gr_text("GND plane edge - no copper above this line on any layer",
                          (BOARD_X0 + 0.8, GND_EDGE_Y - 0.8), "Cmts.User", size=0.9))
    pcb.append(gp.gr_line((NOTCH[0], PAD[3]), (NOTCH[2], PAD[3]), "Cmts.User", 0.1))
    pcb.append(gp.gr_line((NOTCH[0], NOTCH[3]), (NOTCH[2], NOTCH[3]), "Cmts.User", 0.1))
    pcb.append(gp.gr_text(f"PORT 1: {PORT_GAP} mm gap, AE1 pad 1 -> GND plane; "
                          "pour meets the radiator at the short pad only",
                          (BOARD_X0 + 0.8, NOTCH[3] + 1.6), "Cmts.User", size=0.8))
    pcb.append(gp.gr_text("ANTENNA KEEP-OUT", (BOARD_X0 + 0.8, 63.2), "F.SilkS", size=1.0))
    pcb.append(gp.gr_text("SWRA117D 2.45 GHz IFA - SIMULATION MODEL",
                          (BOARD_X0 + 1.0, BOARD_Y1 - 7.0), "F.SilkS", size=1.2))
    pcb.append(gp.gr_text("direct port at the feed pad - not for fabrication",
                          (BOARD_X0 + 1.0, BOARD_Y1 - 5.6), "F.SilkS", size=0.9))

    for pos in port_vias():
        pcb.append(gp.via(pos, size=VIA_SIZE, drill=VIA_DRILL))

    plane = [(BOARD_X0 + 0.2, GND_EDGE_Y), (BOARD_X1 - 0.2, GND_EDGE_Y),
             (BOARD_X1 - 0.2, BOARD_Y1 - 0.2), (BOARD_X0 + 0.2, BOARD_Y1 - 0.2)]
    pcb.append(gp.gnd_zone("F.Cu", plane))
    pcb.append(gp.gnd_zone("B.Cu", plane))    # the bottom ground, same outline

    pcb.append(gp.keepout_zone("ANTENNA_KEEPOUT",
                               [(BOARD_X0 - 0.5, BOARD_Y0 - 0.5),
                                (BOARD_X1 + 0.5, BOARD_Y0 - 0.5),
                                (BOARD_X1 + 0.5, GND_EDGE_Y),
                                (BOARD_X0 - 0.5, GND_EDGE_Y)]))
    # The port gap and the D5 clearance, in one cut.  F.Cu only: the bottom
    # ground stays solid underneath, which is what the vias either side of the
    # gap tie the top pour to.
    pcb.append(gp.keepout_zone("RF_PORT_GAP",
                               [(NOTCH[0], NOTCH[1]), (NOTCH[2], NOTCH[1]),
                                (NOTCH[2], NOTCH[3]), (NOTCH[0], NOTCH[3])],
                               layers=("F.Cu",)))
    pcb.append([Sym("embedded_fonts"), Sym("no")])
    return pcb


def build_project() -> dict:
    pro = gp.build_project()
    pro["meta"]["filename"] = f"{PROJECT}.kicad_pro"
    pro["net_settings"]["netclass_patterns"] = []
    pro["net_settings"]["classes"] = [c for c in pro["net_settings"]["classes"]
                                      if c["name"] == "Default"]
    pro["sheets"] = []          # board only: there is nothing to schematise
    return pro


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pcb_path = OUT_DIR / f"{PROJECT}.kicad_pcb"
    pro_path = OUT_DIR / f"{PROJECT}.kicad_pro"
    pcb_path.write_text(dumps(build_board()) + "\n")
    pro_path.write_text(json.dumps(build_project(), indent=2) + "\n")
    for path in (pcb_path, pro_path):
        print(f"wrote {path.relative_to(PRJ_DIR.parent)}")


if __name__ == "__main__":
    main()
