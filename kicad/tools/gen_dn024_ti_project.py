#!/usr/bin/env python3
"""Generate the DN024 board in the reference design's own form.

Same antenna, same ground plane, same matching BOM as ``dn024/`` - what
changes is the launch, and it changes because SWRA227E Figure 2 draws it
differently from the edge-launch used on the 2.45 GHz board:

  * **The connector is P6**, a vertical through-hole SMA jack: signal pin with
    four ground posts on a 5.08 mm square.  Measured off Figure 2 by
    ``gen_sma_through_hole.py``, which records what is certain and what is
    reading error.
  * **It sits inboard**, not on the board edge - about 22 mm below the ground
    plane edge in the reference, with the rest of the board below it.  On the
    CC-Antenna-DK that space held the radio.
  * **The top ground is cut away** around the feed line and the matching
    network, in the tall chamfered opening Figure 2 shows, reaching from the
    plane edge down past the connector.  The bottom ground stays solid: it is
    what the feed line is referenced to.

The opening's outline is approximated.  Figure 2 is a raster with a hatched
fill and no dimensions on this feature, so its width was read at about 11-12
mm and its corners are chamfered by eye.  What is *not* approximate is what it
is for - no top ground beside the 50 ohm line or the pi network - and the
width is set from that rule instead: wide enough that the pour is further from
the line than the keep-away that keeps it 50 ohm.

The feed stays 2.95 mm.  That is the 50 ohm width for this stackup, computed
rather than copied, and the opening is wide enough to leave it a microstrip
referenced to the bottom plane.

    python3 kicad/tools/gen_dn024_ti_project.py
"""

from __future__ import annotations

import json
import math
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_project as gp  # noqa: E402
import gen_dn024_project as dn  # noqa: E402
from sexpr import Sym, dumps, num  # noqa: E402

gp.NAMESPACE = uuid.UUID("5b2e8f04-1a76-5c39-8e42-9d10b7c3a68f")
gp.ROOT_UUID = gp.U("sheet", "root")
gp.LIB_NICK = LIB_NICK = "TI_DN024"
gp.PROJECT = PROJECT = "dn024_monopole_ti_form"

PRJ_DIR = gp.PRJ_DIR
OUT_DIR = PRJ_DIR / "dn024_ti_form"

# the board, the plane and the antenna are the reference design's, unchanged
BOARD_X0, BOARD_Y0 = dn.BOARD_X0, dn.BOARD_Y0
BOARD_X1, BOARD_Y1 = dn.BOARD_X1, dn.BOARD_Y1
BOARD_W, BOARD_H = dn.BOARD_W, dn.BOARD_H
GND_W, GND_H = dn.GND_W, dn.GND_H
GND_X0, GND_X1, GND_Y1 = dn.GND_X0, dn.GND_X1, dn.GND_Y1
PLANE_EDGE = dn.PLANE_EDGE
ANT_ORIGIN, ANT_FOOTPRINT = dn.ANT_ORIGIN, dn.ANT_FOOTPRINT
FEED_X, W50, W_PI, POUR_GAP = dn.FEED_X, dn.W50, dn.W_PI, dn.POUR_GAP
SUB_H, SUB_ER, PAD_DX = dn.SUB_H, dn.SUB_ER, dn.PAD_DX
NETS = dn.NETS

# P6 sits inboard.  Figure 2 puts it about 22 mm below the plane edge, with
# the rest of the board - the radio, on the CC-Antenna-DK - below it.
CONN_AT = (FEED_X, PLANE_EDGE + 22.0)
CONN_PITCH = 5.08

# the pi network, as close to the antenna as Figure 2 puts it
Z63_AT = (FEED_X + 3.0, PLANE_EDGE + 3.0)
Z62_AT = (FEED_X, PLANE_EDGE + 6.5)
Z61_AT = (FEED_X + 3.0, PLANE_EDGE + 10.0)

# the opening in the top ground: wide enough to leave the line a microstrip,
# down past the connector, with the chamfers Figure 2 draws
OPENING_W = 11.5
OPENING_BOTTOM = CONN_AT[1] + CONN_PITCH / 2 + 2.2
CHAMFER = 2.0
# A 2.95 mm line does not fit between ground posts 5.08 mm apart: it leaves
# 0.115 mm, under the 0.15 mm rule.  So it necks down for the last 4 mm, which
# is the launch transition every through-hole connector needs anyway: 2.5 mm
# of taper into 1.5 mm of 1.0 mm line, which line_impedance.py puts at 84.5
# ohm.  Against a 50 ohm line of the same 4.0 mm the transition adds j2.6 ohm
# at 868 MHz and j6.5 ohm at 2.44 GHz - about 0.45 nH either way, which is one
# of the things the pi network upstream exists to absorb.  The neck leaves
# 1.09 mm to each post.
LAUNCH_NECK = 1.0
LAUNCH_TAPER, LAUNCH_STEPS = 2.5, 5
FENCE_PITCH, GRID_PITCH = 3.0, 4.0
VIA_SIZE, VIA_DRILL = 0.6, 0.3

TITLE = ("TI DN024 (SWRA227E) monopole, reference form - through-hole SMA, "
         "868 + 2440 MHz, 43 x 63 mm ground plane")

SCH_NOTE = (
    "TI DN024 / SWRA227E meandering monopole, dual band 868 + 2440 MHz,\n"
    "laid out the way the note's own Figure 2 lays it out.\n"
    "\n"
    "J1 is P6: a vertical through-hole SMA jack, signal pin with four ground\n"
    "posts on a 5.08 mm square, sitting 22 mm inboard of the ground plane\n"
    "edge rather than on the board edge. Its drills are measured off Figure 2\n"
    "to about +/-0.1 mm - check them against the connector you buy.\n"
    "\n"
    "Table 3, dual band BOM:   Z61 NC   Z62 3.9 pF series   Z63 NC\n"
    "  -> measured SWR 1.2 at 868 MHz and 1.6 at 2.44 GHz\n"
    "\n"
    "The top ground is cut away around the feed and the network, as Figure 2\n"
    "draws it; the bottom ground stays solid and is what the 2.95 mm 50 ohm\n"
    "line is referenced to.\n"
    "\n"
    "Everything else - antenna, ground plane, clearances - is identical to\n"
    "the dn024/ project, which uses an edge-launch SMA instead."
)


def parts() -> list:
    base = {p["ref"]: p for p in dn.parts()}
    z61, z62, z63, ae1 = base["Z61"], base["Z62"], base["Z63"], base["AE1"]
    z63["pcb"] = (Z63_AT[0], Z63_AT[1], 0)
    z62["pcb"] = (Z62_AT[0], Z62_AT[1], 90)
    z61["pcb"] = (Z61_AT[0], Z61_AT[1], 0)
    conn = dict(base["J1"])
    conn["fp"] = f"{LIB_NICK}:SMA_ThruHole_4Post"
    conn["pcb"] = (CONN_AT[0], CONN_AT[1], 0)
    conn["value"] = "SMA jack, through hole"
    conn["desc"] = ("Vertical through-hole SMA jack - the connector SWRA227E "
                    "Figure 2 shows as P6. Four ground posts on a 5.08 mm "
                    "square with the signal pin in the middle")
    return [conn, z61, z62, z63, ae1]


def feed_tracks() -> list:
    """Antenna -> Z63 tap -> Z62 -> Z61 tap -> taper -> 50 ohm line -> J1 pin."""
    z62_ant = (Z62_AT[0], Z62_AT[1] - PAD_DX)
    z62_in = (Z62_AT[0], Z62_AT[1] + PAD_DX)
    taper_top = Z61_AT[1] + 2.0
    taper_len, steps = 3.0, 5

    tracks = [
        ((FEED_X, ANT_ORIGIN[1]), (FEED_X, Z63_AT[1]), dn.W_ANT, "ANT_FEED"),
        ((FEED_X, Z63_AT[1]), (FEED_X, z62_ant[1]), W_PI, "ANT_FEED"),
        ((FEED_X, Z63_AT[1]), (Z63_AT[0] - PAD_DX, Z63_AT[1]), W_PI, "ANT_FEED"),
        ((FEED_X, z62_in[1]), (FEED_X, Z61_AT[1]), W_PI, "RF_IN"),
        ((FEED_X, Z61_AT[1]), (Z61_AT[0] - PAD_DX, Z61_AT[1]), W_PI, "RF_IN"),
        ((FEED_X, Z61_AT[1]), (FEED_X, taper_top), W_PI, "RF_IN"),
    ]
    for i in range(steps):
        y0 = taper_top + i * taper_len / steps
        y1 = taper_top + (i + 1) * taper_len / steps
        width = W_PI + (W50 - W_PI) * (i + 0.5) / steps
        tracks.append(((FEED_X, y0), (FEED_X, y1), round(width, 3), "RF_IN"))
    # the 50 ohm run, then the launch transition into the signal pin
    neck_start = CONN_AT[1] - 1.5
    taper_start = neck_start - LAUNCH_TAPER
    tracks.append(((FEED_X, taper_top + taper_len), (FEED_X, taper_start),
                   W50, "RF_IN"))
    for i in range(LAUNCH_STEPS):
        y0 = taper_start + i * LAUNCH_TAPER / LAUNCH_STEPS
        y1 = taper_start + (i + 1) * LAUNCH_TAPER / LAUNCH_STEPS
        width = W50 + (LAUNCH_NECK - W50) * (i + 0.5) / LAUNCH_STEPS
        tracks.append(((FEED_X, y0), (FEED_X, y1), round(width, 3), "RF_IN"))
    tracks.append(((FEED_X, neck_start), (FEED_X, CONN_AT[1]),
                   LAUNCH_NECK, "RF_IN"))
    for at in (Z63_AT, Z61_AT):
        tracks.append(((at[0] + PAD_DX, at[1]), (at[0] + 1.4, at[1]), W_PI, "GND"))
    return tracks


def opening() -> list:
    """The chamfered hole in the top ground, from the plane edge down past P6."""
    half = OPENING_W / 2
    x0, x1 = FEED_X - half, FEED_X + half
    y0, y1 = PLANE_EDGE, OPENING_BOTTOM
    return [(x0, y0), (x1, y0),
            (x1, y1 - CHAMFER), (x1 - CHAMFER, y1),
            (x0 + CHAMFER, y1), (x0, y1 - CHAMFER)]


def stitching() -> list[tuple[float, float]]:
    out = [(at[0] + 1.4, at[1]) for at in (Z63_AT, Z61_AT)]
    hole = opening()
    hx0 = min(p[0] for p in hole) - 1.0
    hx1 = max(p[0] for p in hole) + 1.0
    hy1 = max(p[1] for p in hole) + 1.0

    x = GND_X0 + 1.2
    while x <= GND_X1 - 1.2:
        if not (hx0 <= x <= hx1):
            out.append((x, PLANE_EDGE + 1.0))
        x += FENCE_PITCH
    y = PLANE_EDGE + 1.0 + GRID_PITCH
    while y <= GND_Y1 - 1.2:
        x = GND_X0 + 1.2
        while x <= GND_X1 - 1.2:
            in_hole = hx0 <= x <= hx1 and PLANE_EDGE <= y <= hy1
            crowded = any(math.dist((x, y), p) < 2.0 for p in out)
            if not (in_hole or crowded):
                out.append((x, y))
            x += GRID_PITCH
        y += GRID_PITCH
    return out


def build_board() -> list:
    gp.PARTS, gp.NETS = parts(), NETS
    pcb = [Sym("kicad_pcb"),
           [Sym("version"), Sym("20241229")],
           [Sym("generator"), "gen_dn024_ti_project.py"],
           [Sym("generator_version"), "9.0"],
           [Sym("general"), [Sym("thickness"), num(SUB_H + 0.09)],
            [Sym("legacy_teardrops"), Sym("no")]],
           [Sym("paper"), "A4"],
           [Sym("title_block"),
            [Sym("title"), TITLE],
            [Sym("date"), "2026-09-16"],
            [Sym("rev"), "A"],
            [Sym("comment"), Sym("1"),
             f"2 layer, {BOARD_W} x {BOARD_H} mm, {SUB_H} mm FR4 er={SUB_ER}"],
            [Sym("comment"), Sym("2"),
             "J1 = P6: through-hole SMA, 4 ground posts on a 5.08 mm square"],
            [Sym("comment"), Sym("3"),
             "Top ground cut away around the feed and the pi network, as Figure 2 draws it"]]]
    layer_nodes = [Sym("layers")]
    for number, name, ltype, alias in [
            (0, "F.Cu", "signal", None), (31, "B.Cu", "signal", None),
            (32, "B.Adhes", "user", "B.Adhesive"), (33, "F.Adhes", "user", "F.Adhesive"),
            (34, "B.Paste", "user", None), (35, "F.Paste", "user", None),
            (36, "B.SilkS", "user", "B.Silkscreen"), (37, "F.SilkS", "user", "F.Silkscreen"),
            (38, "B.Mask", "user", None), (39, "F.Mask", "user", None),
            (40, "Dwgs.User", "user", "User.Drawings"), (41, "Cmts.User", "user", "User.Comments"),
            (42, "Eco1.User", "user", "User.Eco1"), (43, "Eco2.User", "user", "User.Eco2"),
            (44, "Edge.Cuts", "user", None), (45, "Margin", "user", None),
            (46, "B.CrtYd", "user", "B.Courtyard"), (47, "F.CrtYd", "user", "F.Courtyard"),
            (48, "B.Fab", "user", None), (49, "F.Fab", "user", None)]:
        node = [Sym(str(number)), name, Sym(ltype)]
        if alias:
            node.append(alias)
        layer_nodes.append(node)
    pcb.append(layer_nodes)
    pcb.append([Sym("setup"), gp.stackup(),
                [Sym("pad_to_mask_clearance"), Sym("0")],
                [Sym("allow_soldermask_bridges_in_footprints"), Sym("no")]])

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
    pcb.append(gp.gr_text("TI DN024 monopole - 868 + 2440 MHz, reference form",
                          (BOARD_X0 + 1.5, BOARD_Y1 - 8.0), "F.SilkS", size=1.1))
    pcb.append(gp.gr_text("J1 = P6 through-hole SMA; Z62 = 3.9pF, Z61/Z63 NC",
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
    pcb.append(gp.keepout_zone("PI_NETWORK_CLEARANCE", opening(),
                               layers=("F.Cu",), tracks="allowed", vias="allowed"))
    pcb.append([Sym("embedded_fonts"), Sym("no")])
    return pcb


def build_schematic() -> list:
    gp.TITLE, gp.SCH_NOTE, gp.NETS = TITLE, SCH_NOTE, NETS
    gp.PARTS, gp.WIRES, gp.JUNCTIONS = parts(), dn.WIRES, dn.JUNCTIONS
    gp.LABELS, gp.POWER, gp.PWR_FLAGS = dn.LABELS, dn.POWER, dn.PWR_FLAGS
    return gp.build_schematic()


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{PROJECT}.kicad_sch").write_text(dumps(build_schematic()) + "\n")
    (OUT_DIR / f"{PROJECT}.kicad_pcb").write_text(dumps(build_board()) + "\n")
    pro = gp.build_project()
    pro["meta"]["filename"] = f"{PROJECT}.kicad_pro"
    pro["sheets"] = [[gp.ROOT_UUID, "Root"]]
    (OUT_DIR / f"{PROJECT}.kicad_pro").write_text(json.dumps(pro, indent=2) + "\n")
    for ext in ("kicad_sch", "kicad_pcb", "kicad_pro"):
        print(f"wrote {(OUT_DIR / f'{PROJECT}.{ext}').relative_to(PRJ_DIR.parent)}")


if __name__ == "__main__":
    main()
