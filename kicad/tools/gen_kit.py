#!/usr/bin/env python3
"""Generate the PCB antenna evaluation kit: three antennas, two ground planes.

AN058 Tables 9 and 10 are TI's catalogue of reference antennas, and this kit
is three of them - the three whose application note is in hand, so the three
that can be exact copies of a published dimension table rather than drawings:

    AN043  SWRA117D   meandered inverted-F   15 x 6 mm    2.45 GHz
    DN023  SWRA228C   printed inverted-F     43 x 20 mm   868 / 915 / 955 MHz
    DN024  SWRA227E   meandering monopole    38 x 25 mm   868 + 2440 MHz

Each is built twice, because a PCB antenna is not a component - the ground
plane is part of the antenna, and which plane you put it on decides what you
measure:

  * on its REFERENCE plane, so the board reproduces the note's own published
    numbers and the measurement validates the build;
  * on a COMMON 45 x 60 mm plane shared by all three, so the three boards
    answer the question a customer actually asks - which of these should go
    in my product - which the reference boards cannot, because they differ.

Putting several antennas on one board instead would answer neither: they
would share a plane and couple to each other.  TI's own CC-Antenna-DK is a
set of separate boards for the same reason.  These six are separate boards
with a common outline in the common-plane set, so they panelise.

Everything else is held constant on purpose: 1.6 mm FR4, the same edge-mount
SMA, the same 50 ohm microstrip, the same three matching sites at the feed.
The only variables are the antenna and the plane.

    python3 kicad/tools/gen_kit.py
    python3 kicad/tools/gen_kit.py --only dn023_common
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
from sexpr import Sym, dumps, find, find_all, num, parse  # noqa: E402

PRJ_DIR = gp.PRJ_DIR
OUT_DIR = PRJ_DIR / "kit"
LIB_DIR = PRJ_DIR / "library"

SUB_H, SUB_ER = gp.SUB_H, gp.SUB_ER      # 1.6 mm FR4, the whole kit
W50 = gp.W50                             # 2.95 mm on this stackup
POUR_GAP = gp.POUR_GAP
W_PI = 0.6                               # interconnect inside the network
PAD_DX = 0.48                            # 0402 land, pad centre offset
NETS = {"": 0, "GND": 1, "ANT_FEED": 2, "RF_IN": 3}

SIDE_MARGIN = 5.0        # bare board either side of the widest copper
TOP_MARGIN = 3.0         # above the antenna
BOTTOM_MARGIN = 1.0      # below the plane, for the connector land
Z3_UP, Z2_UP, Z1_UP = 3.0, 6.5, 10.0     # network sites, above the plane edge
FENCE_PITCH, GRID_PITCH = 3.0, 4.0
VIA_SIZE, VIA_DRILL = 0.6, 0.3

# The kit launches through a U.FL and a pigtail, not an SMA on the board edge:
# the bulkhead SMA stays on the jig instead of sitting as copper in the near
# field of a plane that is half the antenna, and the pigtail is where the
# common-mode choke goes.  See gen_ufl_footprint.py.
CONN_FP = "SWRA117D_RF:U_FL_Hirose_U_FL_R_SMT_1_Vertical"
CONN_UP = 4.0            # connector centre, above the bottom of the plane
CONN_PAD_W = 1.05        # the U.FL signal pad, across the line
LAUNCH_NECK = 1.0        # a 2.95 mm line cannot butt onto a 1.05 mm pad
LAUNCH_TAPER, LAUNCH_STEPS, LAUNCH_RUN = 2.5, 5, 1.5
CONN_ROT = 270           # signal pad toward the antenna, ground pads flanking
MIN_RUN_50 = 3.0         # the shortest run of real 50 ohm line worth having
TAPER_LEN, TAPER_STEPS = 3.0, 5

COMMON_PLANE = (45.0, 60.0)
COMMON_BOARD = (55.0, 90.0)

ANTENNAS = [
    dict(key="an043", note="AN043 / SWRA117D", lib="SWRA117D_RF",
         sym="ANT_SWRA117D_2G4_Left", fp="SWRA117D_RF:Texas_SWRA117D_2.4GHz_Left",
         pins={"1": "ANT_FEED", "2": "GND"}, bands="2450 MHz",
         origin_above_plane=-0.25,  # SWRA117D: the feed pad straddles the plane edge and the
         #                      W1 strap's via lands in the plane behind it
         # 28.0 mm, not the 23.75 of the standalone board: the kit's feed
         # - network, taper, a real run of 50 ohm, launch - needs 27.05 mm
         # and spec() refuses anything shorter.  SWRA117D publishes no plane
         # at all, so this number was always this repo's to choose, and it
         # may as well be one the standard feed fits in.
         ref_plane=(40.0, 28.0), ref_published=False,
         bom=[("Z1", "DNP"), ("Z2", "0R"), ("Z3", "DNP")],
         why=("SWRA117D publishes no matching values and no ground plane "
              "size. The plane here is this repo's own 40 x 23.75 mm, not "
              "TI's - the note only says plane size affects performance."),
         datasheet="https://www.ti.com/lit/an/swra117d/swra117d.pdf"),
    dict(key="dn023", note="DN023 / SWRA228C", lib="TI_DN023",
         sym="ANT_DN023_IFA", fp="TI_DN023:TI_DN023_IFA_868",
         pins={"1": "ANT_FEED", "2": "GND"}, bands="868 / 915 / 955 MHz",
         origin_above_plane=0.0,  # SWRA228C: L1 = 20.0 mm is measured to the plane edge,
         #                     and the shorting leg merges into the plane there
         ref_plane=(31.0, 45.0), ref_published=True,
         bom=[("Z1", "DNP"), ("Z2", "0R"), ("Z3", "DNP")],
         why=('SWRA228C 3: "Since the impedance of this antenna is '
              'approximately matched to 50 ohm, no external matching '
              'components are needed... has included the option for one '
              'series and two shunt components at the feed point." Tuned by '
              "trimming L6: 17 mm as drawn, 11 mm at 868, 3 mm at 915."),
         datasheet="https://www.ti.com/lit/an/swra228c/swra228c.pdf"),
    dict(key="dn024", note="DN024 / SWRA227E", lib="TI_DN024",
         sym="ANT_DN024_Monopole", fp="TI_DN024:TI_DN024_Monopole_868_2440",
         pins={"1": "ANT_FEED"}, bands="868 + 2440 MHz",
         origin_above_plane=1.0,  # SWRA227E Table 1: L5 = 1.0 mm of clear board between the
         #                     antenna and the plane edge
         ref_plane=(43.0, 63.0), ref_published=True,
         bom=[("Z1", "DNP"), ("Z2", "3.9pF"), ("Z3", "DNP")],
         why=("SWRA227E Table 3, dual band, on the 43 x 63 mm plane it was "
              "measured on. Z1/Z2/Z3 are the note's Z61/Z62/Z63."),
         datasheet="https://www.ti.com/lit/an/swra227e/swra227e.pdf"),
]


def footprint_box(qualified: str) -> dict:
    """Copper extent and feed offset of a footprint, read out of the file.

    The three antennas put their origin in different places - DN023 at the
    feed point on the plane edge, DN024 one L5 above it, AN043 a quarter of a
    millimetre below - so nothing here may assume where the origin sits.  It
    is measured instead, and the board is laid out around what is measured.
    """
    nick, _, name = qualified.rpartition(":")
    fp = parse((LIB_DIR / f"{nick}.pretty" / f"{name}.kicad_mod").read_text())
    xs, ys = [], []
    for poly in find_all(fp, "fp_poly"):
        if str(find(poly, "layer")[1]) not in ("F.Cu", "B.Cu"):
            continue
        for xy in find(poly, "pts")[1:]:
            xs.append(float(xy[1])); ys.append(float(xy[2]))
    for pad in find_all(fp, "pad"):
        at, size = find(pad, "at"), find(pad, "size")
        cx, cy = float(at[1]), float(at[2])
        w, h = float(size[1]), float(size[2])
        xs += [cx - w / 2, cx + w / 2]
        ys += [cy - h / 2, cy + h / 2]
    if not xs:
        raise SystemExit(f"{qualified}: no copper found")
    return dict(x0=min(xs), x1=max(xs), y0=min(ys), y1=max(ys),
                w=max(xs) - min(xs), h=max(ys) - min(ys))


def deep(node, tag):
    """Every node with this tag, including ones nested inside a match.

    ``sexpr.find_all`` stops at a match, which is right for pads but wrong
    for symbols: a KiCad symbol's pins live inside a child *symbol* node, so
    a non-recursing search finds the parent and never the pins.
    """
    out = []
    for child in node:
        if isinstance(child, list) and child:
            if str(child[0]) == tag:
                out.append(child)
            out += deep(child, tag)
    return out


def symbol_pins(nick: str, name: str) -> dict:
    """Pin connection points of a library symbol, in symbol coordinates.

    Read rather than assumed, so that placing the antenna on the sheet cannot
    leave a pin off the end of its wire - which is a silent netlist break, and
    one this repo has already had once.
    """
    lib = parse((LIB_DIR / f"{nick}.kicad_sym").read_text())
    for sym in deep(lib, "symbol"):
        if not isinstance(sym[1], str) or not str(sym[1]).startswith(name):
            continue
        pins = {}
        for pin in deep(sym, "pin"):
            at = find(pin, "at")
            pins[str(find(pin, "number")[1])] = (float(at[1]), float(at[2]))
        if pins:
            return pins
    raise SystemExit(f"{nick}:{name} has no pins")


def rot_xy(pt, deg):
    """A footprint-local offset in board coordinates, for a placed rotation."""
    r = math.radians(-deg)
    return (pt[0] * math.cos(r) - pt[1] * math.sin(r),
            pt[0] * math.sin(r) + pt[1] * math.cos(r))


def footprint_pads(qualified: str) -> dict:
    nick, _, name = qualified.rpartition(":")
    fp = parse((LIB_DIR / f"{nick}.pretty" / f"{name}.kicad_mod").read_text())
    out = {}
    for pad in find_all(fp, "pad"):
        at, size = find(pad, "at"), find(pad, "size")
        out.setdefault(str(pad[1]), []).append(
            dict(x=float(at[1]), y=float(at[2]), kind=str(pad[2]),
                 w=float(size[1]), h=float(size[2])))
    return out


def spec(antenna: dict, plane_key: str) -> dict:
    """Everything one board needs, derived rather than tabulated."""
    box = footprint_box(antenna["fp"])
    # how far the copper reaches above the origin, and below it
    above, below = -box["y0"], box["y1"]
    if plane_key == "common":
        plane_w, plane_h = COMMON_PLANE
        board_w, board_h = COMMON_BOARD
    else:
        plane_w, plane_h = antenna["ref_plane"]
        board_w = max(plane_w, box["w"]) + 2 * SIDE_MARGIN
        board_h = TOP_MARGIN + above + plane_h + BOTTOM_MARGIN

    x0, y0 = 100.0, 60.0
    x1, y1 = x0 + board_w, y0 + board_h
    plane_y1 = y1 - BOTTOM_MARGIN
    plane_y0 = plane_y1 - plane_h                     # the plane edge
    if plane_y0 - above < y0:
        raise SystemExit(f"{antenna['key']}/{plane_key}: the antenna needs "
                         f"{above:.1f} mm above the plane edge and the board "
                         f"only leaves {plane_y0 - y0:.1f} mm")
    # centre the antenna's copper on the board; the feed is wherever the
    # footprint's origin is, and the connector follows it so the line is
    # straight.  A straight 50 ohm run beats a cosmetically centred connector.
    origin_x = (x0 + x1) / 2 - (box["x0"] + box["x1"]) / 2
    # Put AE1 on the sheet so its FEED pin lands exactly on the ANT_FEED bus
    # at (146.05, 88.9), whatever the symbol's own pin geometry is.
    pins = symbol_pins(antenna["lib"], antenna["sym"])
    p1x, p1y = pins["1"]
    ae1_sch = (146.05 - p1x, 88.9 + p1y)
    pin2 = None
    if "2" in pins:
        pin2 = (ae1_sch[0] + pins["2"][0], ae1_sch[1] - pins["2"][1])
    conn_y = plane_y1 - CONN_UP
    # The launch ends on the U.FL's SIGNAL PAD, not on its origin: the pad is
    # offset from the origin, and a track run to the origin sails straight
    # past the pad and in under the connector body.
    conn_pad = footprint_pads(CONN_FP)["1"][0]
    conn_feed_y = conn_y + rot_xy((conn_pad["x"], conn_pad["y"]), CONN_ROT)[1]
    run_50 = (conn_feed_y - (LAUNCH_TAPER + LAUNCH_RUN)) - (
        plane_y0 + Z1_UP + 2.0 + TAPER_LEN)
    if run_50 < MIN_RUN_50 - 1e-9:
        raise SystemExit(
            f"{antenna['key']}/{plane_key}: a {plane_h:g} mm plane leaves only "
            f"{run_50:.2f} mm of 50 ohm line between the network and the "
            f"launch; {MIN_RUN_50:g} mm is the least worth calling a line")
    key = f"{antenna['key']}_{plane_key}"
    return dict(
        antenna=antenna, plane_key=plane_key, key=key, box=box,
        ae1_sch=ae1_sch, pin2=pin2, pads=footprint_pads(antenna["fp"]),
        conn_y=conn_y, conn_feed_y=conn_feed_y, run_50=run_50,
        project=f"kit_{key}",
        board=(x0, y0, x1, y1), board_w=board_w, board_h=board_h,
        plane=(x0 + (board_w - plane_w) / 2, plane_y0,
               x0 + (board_w + plane_w) / 2, plane_y1),
        plane_w=plane_w, plane_h=plane_h, plane_edge=plane_y0,
        feed_x=origin_x,
        origin=(origin_x, plane_y0 - antenna["origin_above_plane"]),
        ant_top=plane_y0 - above, ant_below=below)


def parts(s: dict) -> list:
    a = s["antenna"]
    nick = a["lib"]
    fx = s["feed_x"]
    z3 = (fx + 3.0, s["plane_edge"] + Z3_UP)
    z2 = (fx, s["plane_edge"] + Z2_UP)
    z1 = (fx + 3.0, s["plane_edge"] + Z1_UP)
    s["z1"], s["z2"], s["z3"] = z1, z2, z3

    def chip(ref, value, sch, pcb, nets, rot, desc):
        dnp = value == "DNP"
        label = (2.54, -3.81) if rot else (2.54, -1.27)
        return dict(ref=ref, lib=f"{nick}:C" if "pF" in value or dnp
                    else f"{nick}:R", value=value,
                    # The ordinary 0402 land, not the wide one: the 50 ohm
                    # line tapers to W_PI before it reaches the network, so
                    # nothing here has to butt a 2.95 mm track onto a pad.
                    # The wide land is drawn for a part lying ALONG the line
                    # and a series part here stands across it, which would
                    # turn its wide pads the wrong way.
                    fp="SWRA117D_RF:Chip_0402_1005Metric_RF",
                    sch=(sch[0], sch[1], rot), pcb=(pcb[0], pcb[1], 90 if rot else 0),
                    nets=nets, ref_at=(sch[0] + label[0], sch[1] + label[1]),
                    val_at=(sch[0] + label[0], sch[1] + label[1] + 2.54),
                    dnp=dnp, in_bom=not dnp, desc=desc)

    bom = dict(a["bom"])
    out = [
        dict(ref="J1", lib=f"{nick}:Conn_Coaxial_SMA", value="U.FL receptacle",
             fp=CONN_FP, sch=(63.5, 88.9, 0),
             pcb=(fx, s["conn_y"], CONN_ROT), nets={"1": "RF_IN", "2": "GND"},
             ref_at=(63.5, 81.28), val_at=(63.5, 83.82),
             desc="Hirose U.FL-R-SMT-1(10), fed by a pigtail to a bulkhead "
                  "SMA on the jig. The same part on all six boards, so the "
                  "launch is not a variable. Put a ferrite or a sleeve balun "
                  "on the pigtail: on a plane this size the cable braid is "
                  "part of the antenna until you choke it"),
        chip("Z1", bom["Z1"], (78.74, 92.71), z1, {"1": "RF_IN", "2": "GND"}, 0,
             "Matching site, shunt on the connector side. " + a["why"]),
        chip("Z2", bom["Z2"], (95.25, 88.9), z2,
             {"1": "RF_IN", "2": "ANT_FEED"}, 90,
             "Matching site, series. " + a["why"]),
        chip("Z3", bom["Z3"], (111.76, 92.71), z3,
             {"1": "ANT_FEED", "2": "GND"}, 0,
             "Matching site, shunt on the antenna side. " + a["why"]),
        dict(ref="AE1", lib=f"{nick}:{a['sym']}", value=a["sym"],
             fp=a["fp"], sch=(s["ae1_sch"][0], s["ae1_sch"][1], 0),
             pcb=(s["origin"][0], s["origin"][1], 0), nets=a["pins"],
             ref_at=(s["ae1_sch"][0] + 4.0, s["ae1_sch"][1] - 3.81),
             val_at=(s["ae1_sch"][0] + 4.0, s["ae1_sch"][1] - 1.27),
             fp_ref_at=(0.0, 3.2), in_bom=False, datasheet=a["datasheet"],
             desc=f"{a['note']} PCB antenna, {a['bands']}, exact copy of its "
                  f"published dimension table"),
    ]
    return out


def feed_tracks(s: dict) -> list:
    """Antenna -> Z3 tap -> Z2 -> Z1 tap -> taper -> 50 ohm line -> J1."""
    fx = s["feed_x"]
    z1, z2, z3 = s["z1"], s["z2"], s["z3"]
    ant_y = s["origin"][1]
    taper_top = z1[1] + 2.0
    taper_len, steps = TAPER_LEN, TAPER_STEPS
    tracks = [
        ((fx, ant_y), (fx, z3[1]), W_PI, "ANT_FEED"),
        ((fx, z3[1]), (z3[0] - PAD_DX, z3[1]), W_PI, "ANT_FEED"),
        ((fx, z3[1]), (fx, z2[1] - PAD_DX), W_PI, "ANT_FEED"),
        ((fx, z2[1] + PAD_DX), (fx, z1[1]), W_PI, "RF_IN"),
        ((fx, z1[1]), (z1[0] - PAD_DX, z1[1]), W_PI, "RF_IN"),
        ((fx, z1[1]), (fx, taper_top), W_PI, "RF_IN"),
    ]
    for i in range(steps):
        y0 = taper_top + i * taper_len / steps
        y1 = taper_top + (i + 1) * taper_len / steps
        width = W_PI + (W50 - W_PI) * (i + 0.5) / steps
        tracks.append(((fx, y0), (fx, y1), round(width, 3), "RF_IN"))
    # the 50 ohm run, then the launch: the U.FL signal pad is 1.05 mm across
    # and this line is 2.95 mm, so it tapers into the pad rather than butting
    # onto it - the same transition a through-hole SMA's ground posts force.
    neck_start = s["conn_feed_y"] - LAUNCH_RUN
    launch_start = neck_start - LAUNCH_TAPER
    tracks.append(((fx, taper_top + taper_len), (fx, launch_start),
                   W50, "RF_IN"))
    for i in range(LAUNCH_STEPS):
        y0 = launch_start + i * LAUNCH_TAPER / LAUNCH_STEPS
        y1 = launch_start + (i + 1) * LAUNCH_TAPER / LAUNCH_STEPS
        width = W50 + (LAUNCH_NECK - W50) * (i + 0.5) / LAUNCH_STEPS
        tracks.append(((fx, y0), (fx, y1), round(width, 3), "RF_IN"))
    tracks.append(((fx, neck_start), (fx, s["conn_feed_y"]),
                   LAUNCH_NECK, "RF_IN"))
    for at in (z3, z1):
        tracks.append(((at[0] + PAD_DX, at[1]), (at[0] + 1.4, at[1]),
                       W_PI, "GND"))
    # An inverted-F's shorting leg has to reach the plane, and on DN023 it is
    # an SMD pad sitting ON the plane edge: both pours stop there, so without
    # this the short is not shorted to anything.  AN043 needs nothing - its
    # pin 2 is a plated hole that lands in the plane by itself.
    for pad in s["pads"].get("2", []):
        if pad["kind"] != "smd":
            continue
        x = s["origin"][0] + pad["x"]
        y0 = s["origin"][1] + pad["y"]
        tracks.append(((x, y0), (x, s["plane_edge"] + 1.5), max(pad["w"], 0.6),
                       "GND"))
    return tracks


def stitching(s: dict) -> list:
    """A fence along the plane edge and a grid behind it, both clear of the line."""
    px0, py0, px1, py1 = s["plane"]
    fx = s["feed_x"]
    half = W50 / 2 + POUR_GAP + VIA_SIZE / 2 + 0.2
    out = []

    def ok(x, y):
        if abs(x - fx) < half and y > s["plane_edge"]:
            return False
        for at in (s["z1"], s["z2"], s["z3"]):
            if abs(x - at[0]) < 2.6 and abs(y - at[1]) < 2.6:
                return False
        if abs(x - fx) < 3.6 and abs(y - s["conn_y"]) < 3.6:
            return False                      # the connector's own courtyard
        return True

    x = px0 + 1.0
    while x <= px1 - 1.0:
        for y in (py0 + 0.8, py1 - 0.8):
            if ok(x, y):
                out.append((round(x, 3), round(y, 3)))
        x += FENCE_PITCH
    y = py0 + 0.8 + GRID_PITCH
    while y <= py1 - 1.2:
        x = px0 + 1.0
        while x <= px1 - 1.0:
            if ok(x, y):
                out.append((round(x, 3), round(y, 3)))
            x += GRID_PITCH
        y += GRID_PITCH
    # one via per shunt site, so the network's ground is not a long way round
    for at in (s["z1"], s["z3"]):
        out.append((round(at[0] + 1.4, 3), round(at[1], 3)))
    for pad in s["pads"].get("2", []):
        if pad["kind"] == "smd":
            out.append((round(s["origin"][0] + pad["x"], 3),
                        round(s["plane_edge"] + 1.5, 3)))
    # Ground at the launch, beside the U.FL's own ground pads rather than
    # three millimetres away: the return current turns round here.
    for dy in (-1.475, 1.475):
        for dx in (-2.2, 2.2):
            out.append((round(s["feed_x"] + dx, 3),
                        round(s["conn_y"] + dy, 3)))
    return out


def build_board(s: dict) -> list:
    a = s["antenna"]
    x0, y0, x1, y1 = s["board"]
    px0, py0, px1, py1 = s["plane"]
    gp.PARTS, gp.NETS = parts(s), NETS

    title = (f"TI {a['note']} on a {s['plane_w']:g} x {s['plane_h']:g} mm "
             f"{'reference' if s['plane_key'] == 'ref' else 'common'} ground "
             f"plane - antenna evaluation kit")
    pcb = [Sym("kicad_pcb"),
           [Sym("version"), Sym("20241229")],
           [Sym("generator"), "gen_kit.py"],
           [Sym("generator_version"), "9.0"],
           [Sym("general"), [Sym("thickness"), num(SUB_H + 0.09)],
            [Sym("legacy_teardrops"), Sym("no")]],
           [Sym("paper"), "A4"],
           [Sym("title_block"),
            [Sym("title"), title],
            [Sym("date"), "2026-10-07"],
            [Sym("rev"), "A"],
            [Sym("comment"), Sym("1"),
             f"2 layer, {s['board_w']:g} x {s['board_h']:g} mm, {SUB_H} mm FR4 er={SUB_ER}"],
            [Sym("comment"), Sym("2"),
             f"antenna {a['bands']}; matching Z1={a['bom'][0][1]} "
             f"Z2={a['bom'][1][1]} Z3={a['bom'][2][1]}"],
            [Sym("comment"), Sym("3"),
             "Kit board: only the antenna and the ground plane differ "
             "between the six"]]]
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

    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    for i in range(4):
        pcb.append(gp.gr_line(corners[i], corners[(i + 1) % 4], "Edge.Cuts"))
    pcb.append(gp.gr_line((x0, py0), (x1, py0), "Cmts.User", 0.12))
    pcb.append(gp.gr_text("GND plane edge - no copper above this line on any layer",
                          (x0 + 0.8, py0 - 0.8), "Cmts.User", size=0.9))
    pcb.append(gp.gr_text(f"{a['note']}  {a['bands']}",
                          (x0 + 1.5, py1 - 4.6), "F.SilkS", size=1.1))
    pcb.append(gp.gr_text(
        f"{'REFERENCE' if s['plane_key'] == 'ref' else 'COMMON'} plane "
        f"{s['plane_w']:g} x {s['plane_h']:g} mm   "
        f"Z1={a['bom'][0][1]} Z2={a['bom'][1][1]} Z3={a['bom'][2][1]}",
        (x0 + 1.5, py1 - 3.0), "F.SilkS", size=0.8))

    for seg in feed_tracks(s):
        pcb.append(gp.segment(*seg))
    for pos in stitching(s):
        pcb.append(gp.via(pos, size=VIA_SIZE, drill=VIA_DRILL))

    plane = [(px0, py0), (px1, py0), (px1, py1), (px0, py1)]
    pcb.append(gp.gnd_zone("F.Cu", plane))
    pcb.append(gp.gnd_zone("B.Cu", plane))
    pcb.append(gp.keepout_zone("ANTENNA_KEEPOUT",
                               [(x0 - 0.5, y0 - 0.5), (x1 + 0.5, y0 - 0.5),
                                (x1 + 0.5, py0), (x0 - 0.5, py0)]))
    # The keep-away stops short of the connector: its ground pads have to sit
    # ON the pour, and a corridor that ran past them would leave them
    # grounded by nothing but the launch vias.
    half = W50 / 2 + POUR_GAP
    keepaway_end = s["conn_feed_y"] - LAUNCH_TAPER - LAUNCH_RUN
    pcb.append(gp.keepout_zone(
        "RF_POUR_KEEPAWAY",
        [(s["feed_x"] - half, py0), (s["feed_x"] + half, py0),
         (s["feed_x"] + half, keepaway_end), (s["feed_x"] - half, keepaway_end)],
        layers=("F.Cu",), tracks="allowed", vias="allowed"))
    pcb.append(gp.keepout_zone(
        "PI_NETWORK_CLEARANCE",
        [(s["feed_x"] - 4.0, py0), (s["feed_x"] + 5.5, py0),
         (s["feed_x"] + 5.5, py0 + Z1_UP + 1.5),
         (s["feed_x"] - 4.0, py0 + Z1_UP + 1.5)],
        layers=("F.Cu",), tracks="allowed", vias="allowed"))
    pcb.append([Sym("embedded_fonts"), Sym("no")])
    return pcb


def build_schematic(s: dict) -> list:
    a = s["antenna"]
    gp.PROJECT = s["project"]
    gp.TITLE = (f"TI {a['note']} on a {s['plane_w']:g} x {s['plane_h']:g} mm "
                f"{'reference' if s['plane_key'] == 'ref' else 'common'} plane")
    gp.SCH_NOTE = (
        f"Antenna evaluation kit, board {s['key']}.\n"
        "\n"
        f"Antenna: {a['note']}, {a['bands']}, an exact copy of the note's\n"
        "own dimension table, checked by its verify_against_* script.\n"
        "\n"
        f"Ground plane: {s['plane_w']:g} x {s['plane_h']:g} mm, "
        + ("the plane the note publishes and measured its numbers on.\n"
           if s["plane_key"] == "ref" and a["ref_published"] else
           "this repo's own choice - the note publishes no plane size.\n"
           if s["plane_key"] == "ref" else
           "the kit's common plane, shared by all three antennas so the\n"
           "three boards can be compared with each other. On this plane none\n"
           "of them reproduces its published numbers, and that is the point.\n")
        + "\n"
        f"Matching: Z1={a['bom'][0][1]}  Z2={a['bom'][1][1]}  "
        f"Z3={a['bom'][2][1]}\n{a['why']}\n"
        "\n"
        f"{W50} mm wide 50 ohm microstrip on {SUB_H} mm FR4 (er {SUB_ER}),\n"
        "the same on all six boards so the launch is not a variable.\n"
        "\n"
        "Before simulating or running DRC: fill the zones (B in the PCB\n"
        "editor). KiCad stores them unfilled and a plane is half the antenna."
    )
    gp.PARTS = parts(s)
    gp.WIRES = [
        ((68.58, 88.9), (91.44, 88.9)),
        ((99.06, 88.9), (146.05, 88.9)),
        ((63.5, 93.98), (63.5, 99.06)),
        ((63.5, 99.06), (58.42, 99.06)),
        ((78.74, 96.52), (78.74, 99.06)),
        ((111.76, 96.52), (111.76, 99.06)),
    ]
    gp.JUNCTIONS = [(63.5, 99.06), (78.74, 88.9), (111.76, 88.9)]
    gp.LABELS = [("RF_IN", (73.66, 88.9)), ("ANT_FEED", (104.14, 88.9))]
    gp.POWER = [("#PWR01", (63.5, 99.06)), ("#PWR02", (78.74, 99.06)),
                ("#PWR03", (111.76, 99.06))]
    gp.PWR_FLAGS = [("#FLG01", (58.42, 99.06))]
    if s["pin2"] is not None:                   # the inverted-F's shorting leg
        px, py = s["pin2"]
        gp.WIRES.append(((px, py), (px, 101.6)))
        gp.POWER.append(("#PWR04", (px, 101.6)))
    return gp.build_schematic()


def write(s: dict) -> None:
    gp.NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL,
                              f"https://github.io/kicad/kit/{s['key']}")
    gp.ROOT_UUID = gp.U("sheet", "root")
    gp.LIB_NICK = s["antenna"]["lib"]
    out = OUT_DIR / s["key"]
    out.mkdir(parents=True, exist_ok=True)
    for suffix, node in (("kicad_sch", build_schematic(s)),
                         ("kicad_pcb", build_board(s))):
        dest = out / f"{s['project']}.{suffix}"
        dest.write_text(dumps(node) + "\n")
    (out / f"{s['project']}.kicad_pro").write_text(
        json.dumps(gp.build_project(), indent=2) + "\n")
    print(f"{s['key']:14} board {s['board_w']:5.1f} x {s['board_h']:5.1f} mm   "
          f"plane {s['plane_w']:4.1f} x {s['plane_h']:4.1f}   "
          f"antenna {s['box']['w']:5.2f} x {s['box']['h']:5.2f}   "
          f"feed {s['feed_x'] - s['board'][0]:5.2f} mm from the left   "
          f"50R run {s['run_50']:5.2f} mm")


def all_specs() -> list:
    return [spec(a, k) for a in ANTENNAS for k in ("ref", "common")]


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", help="one board key, e.g. dn023_common")
    args = ap.parse_args()
    specs = [s for s in all_specs() if not args.only or s["key"] == args.only]
    if not specs:
        raise SystemExit(f"no board called {args.only}")
    for s in specs:
        write(s)
    print(f"\n{len(specs)} board(s) in kicad/kit/")


if __name__ == "__main__":
    main()
