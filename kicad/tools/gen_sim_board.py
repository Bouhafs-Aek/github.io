#!/usr/bin/env python3
"""Generate the RFsim project: the antenna and its feed line, with no connector.

This is a complete KiCad project - schematic, board and project file - not a
stripped board.  Open it and run RFsim on it.

It is the fabrication project with the connector replaced by a bare port
land.  J1, the SMA, is real hardware and belongs on the board that gets built,
but inside a simulation its coplanar ground tabs are copper that is not the
antenna, they carry the port's return current, and the bright field around
them gets read as an antenna problem.

What is left in its place is the minimum a solver needs and nothing more:

  * P1, ``RF_Port_Land`` - the signal pad the solver drives, the width of the
    50 ohm line, with a solid B.Cu ground pad directly under it.  RFsim
    attaches ports to *pads*, and it needs reference copper under the one it
    drives, so a bare track end is not enough: without this land RFsim falls
    back to the antenna's own feed pad, which has no plane under it, and stops
    with "no copper on reference layer B.Cu under the pad".
  * The B.Cu pad is real copper in the file, so the reference exists whether
    or not the zones have been filled.
  * No coplanar ground beside the line, which is the difference that matters
    against the SMA: the line stays a plain microstrip, so a microstrip (MSL)
    port is the model that fits it, not CPW.

Everything else is shared with the fabrication project by construction: same
antenna footprint, same 1.6 mm FR4 stackup, same 2.95 mm line and taper, same
board outline and ground plane edge.  ``tools/gen_project.py`` is imported
rather than copied, so the two cannot drift apart.

  * Ground vias sit either side of the land, inside its B.Cu ground pad, so
    the port's return current reaches the bottom plane at the port rather than
    somewhere downstream.
  * Copper is allowed to touch the board edge here (the project's edge
    clearance rule is 0), because a port launch is supposed to be at the edge.

    python3 kicad/tools/gen_sim_board.py
"""

from __future__ import annotations

import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_project as gp  # noqa: E402
from sexpr import Sym, dumps, num  # noqa: E402

# Its own uuid namespace, so nothing here shares an identity with the
# fabrication project even though the two are generated from the same sources.
gp.NAMESPACE = uuid.UUID("2f81b6ce-7d44-5a0e-9b3c-5e1d0c72a985")
gp.ROOT_UUID = gp.U("sheet", "root")
U = gp.U

PRJ_DIR = gp.PRJ_DIR
OUT_DIR = PRJ_DIR / "sim" / "board"
PROJECT = "swra117d_2g4_sim"
LIB_NICK = gp.LIB_NICK

BOARD_X0, BOARD_Y0 = gp.BOARD_X0, gp.BOARD_Y0
BOARD_X1, BOARD_Y1 = gp.BOARD_X1, gp.BOARD_Y1
ANT_ORIGIN, ANT_FOOTPRINT = gp.ANT_ORIGIN, gp.ANT_FOOTPRINT
FEED_X, GND_EDGE_Y = gp.FEED_X, gp.GND_EDGE_Y
W50, W_NECK, POUR_GAP = gp.W50, gp.W_NECK, gp.POUR_GAP
TAPER_LEN, TAPER_STEPS = gp.TAPER_LEN, gp.TAPER_STEPS
SUB_H, SUB_ER = gp.SUB_H, gp.SUB_ER
NETS = gp.NETS

PAD_LEN_IN = gp.PAD_LEN_IN
LAUNCH_Y = BOARD_Y1 - PAD_LEN_IN / 2    # centre of the port land's signal pad
VIA_SIZE, VIA_DRILL = 0.6, 0.3
# clear of the pour keep-away corridor, inside the land's B.Cu ground pad
LAUNCH_VIA_X = (W50 / 2 + POUR_GAP + VIA_SIZE / 2 + 0.2, gp.LAUNCH_OFFSET + 1.0)
LAUNCH_VIA_Y = (LAUNCH_Y - 0.8, LAUNCH_Y + 0.8)
FENCE_PITCH, GRID_PITCH = 3.0, 5.0

TITLE = "SWRA117D 2.45 GHz IFA - RFsim model: antenna + 50 ohm feed, no connector"

SCH_NOTE = (
    "RFsim model of the SWRA117D 2.45 GHz inverted-F antenna.\n"
    "\n"
    "Same antenna and same feed as the fabrication project, with the SMA\n"
    "removed: the 50 ohm line runs to the board edge and stops there, and\n"
    "P1 marks where port 1 attaches.  P1 has no footprint and is not placed\n"
    "on the board - it is the solver's source, not a part.\n"
    "\n"
    f"{W50} mm wide 50 ohm microstrip on {SUB_H} mm FR4 (er {SUB_ER}, tan d 0.02),\n"
    f"tapering to {W_NECK} mm over the last {TAPER_LEN} mm to meet AE1 pin 1.\n"
    "AE1 pin 2 is the inverted-F ground pin and sits on the ground plane edge.\n"
    "\n"
    "Before simulating: fill the zones (B in the PCB editor).  An unfilled\n"
    "pour is not a ground plane, and an inverted-F radiates against its plane."
)


def parts() -> list:
    """The fabrication project's parts, minus the connector, plus the port."""
    antenna = next(p for p in gp.PARTS if p["ref"] == "AE1")
    port = dict(ref="P1", lib=f"{LIB_NICK}:RF_PORT", value="50R port",
                fp="RF_Port_Land", sch=(76.2, 88.9, 0),
                pcb=(FEED_X, BOARD_Y1, 90),
                nets={"1": "ANT_FEED", "2": "GND"},
                ref_at=(71.12, 84.0), val_at=(71.12, 86.0),
                in_bom=False,
                desc="50 ohm board-edge port land - attach RFsim port 1 to "
                     "pad 1, with pad 2 on B.Cu as its reference")
    return [port, antenna]


def build_schematic() -> list:
    """Reuse the fabrication schematic generator with this sheet's contents."""
    gp.PROJECT = PROJECT
    gp.TITLE = TITLE
    gp.SCH_NOTE = SCH_NOTE
    gp.PARTS = parts()
    gp.WIRES = [
        ((80.01, 88.9), (127.0, 88.9)),       # P1 pin 1 -> antenna feed
        ((127.0, 88.9), (127.0, 86.36)),      # up into AE1 pin 1
        ((76.2, 93.98), (76.2, 96.52)),       # P1 ground pad -> GND
        ((76.2, 96.52), (71.12, 96.52)),      # GND -> PWR_FLAG
        ((129.54, 86.36), (129.54, 96.52)),   # AE1 ground pin -> GND
    ]
    gp.JUNCTIONS = [(76.2, 96.52)]
    gp.LABELS = [("ANT_FEED", (95.25, 88.9))]
    gp.POWER = [("#PWR01", (76.2, 96.52)), ("#PWR02", (129.54, 96.52))]
    gp.PWR_FLAGS = [("#FLG01", (71.12, 96.52))]
    return gp.build_schematic()


def feed_tracks() -> list:
    """The same feed as the fabrication board, launching at the board edge."""
    taper_top = ANT_ORIGIN[1] + 0.5
    taper_bot = taper_top + TAPER_LEN
    tracks = [((FEED_X, LAUNCH_Y), (FEED_X, taper_bot), W50, "ANT_FEED")]
    for i in range(TAPER_STEPS):
        y0 = taper_bot - i * TAPER_LEN / TAPER_STEPS
        y1 = taper_bot - (i + 1) * TAPER_LEN / TAPER_STEPS
        width = W50 + (W_NECK - W50) * (i + 0.5) / TAPER_STEPS
        tracks.append(((FEED_X, y0), (FEED_X, y1), round(width, 3), "ANT_FEED"))
    tracks.append(((FEED_X, taper_top), (FEED_X, ANT_ORIGIN[1]), W_NECK, "ANT_FEED"))
    return tracks


def stitching() -> list[tuple[float, float]]:
    """Vias at the launch, along the plane edge, then over the rest of the pour."""
    out = [(FEED_X + sign * dx, y)
           for sign in (-1, 1) for dx in LAUNCH_VIA_X for y in LAUNCH_VIA_Y]

    x = BOARD_X0 + 1.5
    while x <= BOARD_X1 - 1.5:
        if abs(x - FEED_X) > W50 / 2 + POUR_GAP + 0.5:
            out.append((x, GND_EDGE_Y + 1.0))
        x += FENCE_PITCH
    out += gp.stitch_grid(out, LAUNCH_Y - 2.0, pitch=GRID_PITCH)
    return out


def build_board() -> list:
    gp.PROJECT = PROJECT
    gp.TITLE = TITLE
    gp.PARTS = parts()

    pcb = gp.build_board()

    # gp.build_board() drew the fabrication board's feed, stitching and notes;
    # replace exactly those, and leave outline, pours and keep-outs alone.
    keep = []
    for node in pcb:
        if node[0] in ("segment", "via"):
            continue
        if node[0] == "gr_text" and str(node[1]).startswith(("SWRA117D 2.45 GHz IFA - RF",
                                                            "50R microstrip")):
            continue
        keep.append(node)
    pcb = keep

    tail = pcb.pop()                      # (embedded_fonts no) stays last
    for a, b, width, net in feed_tracks():
        pcb.append(gp.segment(a, b, width, net))
    for pos in stitching():
        pcb.append(gp.via(pos, size=VIA_SIZE, drill=VIA_DRILL))
    pcb.append(gp.gr_text("SWRA117D 2.45 GHz IFA - RFsim model, no connector",
                          (BOARD_X0 + 1.0, BOARD_Y1 - 7.0), "F.SilkS", size=1.2))
    pcb.append(gp.gr_text(f"50R microstrip w={W50}mm / {SUB_H}mm FR4 er={SUB_ER}",
                          (BOARD_X0 + 1.0, BOARD_Y1 - 5.6), "F.SilkS", size=0.9))
    pcb.append(gp.gr_text("PORT 1: P1 pad 1, referenced to its B.Cu ground pad - "
                          "microstrip (MSL), not CPW: no coplanar ground here",
                          (BOARD_X0 + 0.8, BOARD_Y1 - 1.0), "Cmts.User", size=0.8))
    pcb.append(tail)
    return pcb


def build_project() -> dict:
    pro = gp.build_project()
    pro["meta"]["filename"] = f"{PROJECT}.kicad_pro"
    pro["sheets"] = [[gp.ROOT_UUID, "Root"]]
    # The launch is deliberately on the board edge, which is what a port wants
    # and what an edge clearance rule exists to prevent on a fabricated board.
    pro["board"]["design_settings"]["rules"]["min_copper_edge_clearance"] = 0.0
    return pro


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sch_path = OUT_DIR / f"{PROJECT}.kicad_sch"
    pcb_path = OUT_DIR / f"{PROJECT}.kicad_pcb"
    pro_path = OUT_DIR / f"{PROJECT}.kicad_pro"
    sch_path.write_text(dumps(build_schematic()) + "\n")
    pcb_path.write_text(dumps(build_board()) + "\n")
    pro_path.write_text(json.dumps(build_project(), indent=2) + "\n")
    for path in (sch_path, pcb_path, pro_path):
        print(f"wrote {path.relative_to(PRJ_DIR.parent)}")


if __name__ == "__main__":
    main()
