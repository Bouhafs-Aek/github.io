#!/usr/bin/env python3
"""Static checks for the RFsim project (schematic + board).

The fabrication project has its own checker.  This one asks a different
question: is the board still the arrangement SWRA117D Figure 3 draws - the
antenna and its feed on layer 1, ground on layer 2 and nowhere else, one via,
no connector?  A model that quietly stops being that is the commonest reason a
published antenna "does not resonate where the datasheet says".

    python3 kicad/tools/check_sim_board.py [board.kicad_pcb]
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import find, find_all, parse  # noqa: E402

PRJ_DIR = pathlib.Path(__file__).resolve().parent.parent
DEFAULT_PCB = PRJ_DIR / "sim" / "board" / "swra117d_2g4_sim.kicad_pcb"
PCB_PATH = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PCB
SCH_PATH = PCB_PATH.with_suffix(".kicad_sch")
LIB_PATH = PRJ_DIR / "library" / "SWRA117D_RF.kicad_sym"

MIN_CLEARANCE = 0.15
PORT_LAND = "RF_Port_Land"
GROUND_LAYER = "B.Cu"       # Figure 3: "Ground Layer 2", and only that
EPS = 1e-6

errors: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def q(pt):
    return (round(pt[0], 3), round(pt[1], 3))


def rotate(pt, deg):
    rad = math.radians(deg)
    return (pt[0] * math.cos(rad) - pt[1] * math.sin(rad),
            pt[0] * math.sin(rad) + pt[1] * math.cos(rad))


def on_segment(pt, a, b) -> bool:
    (px, py), (ax, ay), (bx, by) = pt, a, b
    if abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) > 1e-6:
        return False
    dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    length2 = (bx - ax) ** 2 + (by - ay) ** 2
    return -1e-6 <= dot <= length2 + 1e-6


def plane_edge(pcb):
    """Top edge of the ground plane, read from the board's own pour.

    None when the board has no pour at all: check_ground reports that, and the
    checks that need an edge stand down instead of throwing.
    """
    ys = [float(xy[2])
          for zone in find_all(pcb, "zone") if not find(zone, "keepout")
          for xy in find(find(zone, "polygon"), "pts")[1:]]
    return min(ys) if ys else None


def outline(pcb):
    pts = [(float(find(g, s)[1]), float(find(g, s)[2]))
           for g in find_all(pcb, "gr_line")
           if str(find(g, "layer")[1]) == "Edge.Cuts" for s in ("start", "end")]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return min(xs), min(ys), max(xs), max(ys)


def zone_by_name(pcb, name):
    for zone in find_all(pcb, "zone"):
        node = find(zone, "name")
        if node is not None and str(node[1]) == name:
            return zone
    return None


def zone_bbox(zone):
    pts = [(float(xy[1]), float(xy[2])) for xy in find(find(zone, "polygon"), "pts")[1:]]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), min(ys), max(xs), max(ys))


def antenna(pcb):
    """The antenna footprint, its radiator polygon and its two pads."""
    for fp in find_all(pcb, "footprint"):
        if find(fp, "fp_poly") is None:
            continue
        at = find(fp, "at")
        origin = (float(at[1]), float(at[2]))
        if len(at) > 3 and float(at[3]) % 360:
            fail("board: the antenna is rotated; these checks assume it is not")
            return None, None, None
        pads = {}
        for pad in find_all(fp, "pad"):
            pat, size = find(pad, "at"), find(pad, "size")
            cx, cy = origin[0] + float(pat[1]), origin[1] + float(pat[2])
            w, h = float(size[1]), float(size[2])
            net = find(pad, "net")
            drill = find(pad, "drill")
            pads[str(pad[1])] = dict(
                centre=(cx, cy),
                rect=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                type=str(pad[2]),
                drill=float(drill[1]) if drill is not None else None,
                net=str(net[2]) if net is not None else "")
        poly = [(origin[0] + float(xy[1]), origin[1] + float(xy[2]))
                for xy in find(find(fp, "fp_poly"), "pts")[1:]]
        return fp, poly, pads
    return None, None, None


def rect_distance(rect, pt):
    x0, y0, x1, y1 = rect
    return math.hypot(max(x0 - pt[0], 0.0, pt[0] - x1),
                      max(y0 - pt[1], 0.0, pt[1] - y1))


def feed_segments(pcb):
    return [((float(find(s, "start")[1]), float(find(s, "start")[2])),
             (float(find(s, "end")[1]), float(find(s, "end")[2])),
             float(find(s, "width")[1]))
            for s in find_all(pcb, "segment")]


# ------------------------------------------------------------------- checks
def port_land(pcb):
    for fp in find_all(pcb, "footprint"):
        if str(fp[1]).split(":", 1)[-1] == PORT_LAND:
            return fp
    return None


def check_no_connector(pcb):
    """The radiator, and a bare port land - no connector."""
    fps = find_all(pcb, "footprint")
    radiators = [fp for fp in fps if find(fp, "fp_poly") is not None]
    others = [str(fp[1]) for fp in fps if find(fp, "fp_poly") is None]
    if len(radiators) != 1:
        fail(f"board: expected exactly one antenna footprint, found {len(radiators)}")
    strays = [n for n in others if n.split(":", 1)[-1] != PORT_LAND]
    if strays:
        fail("board: the model still carries " + ", ".join(strays) +
             " - a connector inside the model is part of the answer it gives, "
             "and its ground pads carry the port's return current")
    land = port_land(pcb)
    if land is None:
        fail(f"board: no {PORT_LAND} - RFsim attaches its port to a pad, so "
             "without one it falls back to the antenna's own feed pad, which "
             "has no ground plane under it")
        return
    if len(others) != 1:
        fail(f"board: {len(others)} non-antenna footprints; expected just the "
             "port land")

    # what makes it a port land and not a connector, and what makes MSL the
    # right port model: no coplanar ground beside the signal pad
    coplanar = [pad for pad in find_all(land, "pad")
                if str(pad[1]) != "1"
                and "F.Cu" in [str(l) for l in find(pad, "layers")[1:]]]
    if coplanar:
        fail(f"board: {PORT_LAND} has {len(coplanar)} ground pad(s) on F.Cu - "
             "that is a coplanar launch, so the line is no longer a plain "
             "microstrip and an MSL port no longer describes it")
    else:
        notes.append("board: the radiator plus a bare port land - no connector, "
                     "and no coplanar ground beside the line, so the launch is "
                     "microstrip (use an MSL port, not CPW)")


def check_exact_copy(pcb):
    """Same rule as the fabrication board: SWRA117D says copy it exactly."""
    from verify_against_swra117d import TABLE_1, TOL, measure

    fp, _poly, _pads = antenna(pcb)
    if fp is None:
        fail("board: no antenna footprint on the board")
        return
    name = str(fp[1]).split(":", 1)[-1]
    path = PRJ_DIR / "library" / "SWRA117D_RF.pretty" / f"{name}.kicad_mod"
    try:
        got, _info = measure(path)
    except SystemExit as exc:
        fail(f"board: {name} does not have the reference geometry ({exc})")
        return
    off = {k: got[k] - v for k, v in TABLE_1.items() if abs(got[k] - v) > TOL}
    if off:
        fail(f"board: {name} differs from SWRA117D Table 1: " +
             ", ".join(f"{k} by {v * 1000:+.0f} um" for k, v in sorted(off.items())))
    else:
        notes.append(f"board: {name} matches all {len(TABLE_1)} dimensions of "
                     f"SWRA117D Table 1 within {TOL * 1000:.0f} um (exact copy) - "
                     "the same footprint file the fabrication board uses")


def check_ground(pcb):
    """Ground on layer 2 and nowhere else, which is what Figure 3 draws.

    The absence of a top pour is not an omission here, it is the arrangement:
    it is what makes the feed unambiguously a microstrip (so MSL is the right
    port model), and it is why there is nothing to stitch.
    """
    zones = {str(find(z, "layer")[1]): z for z in find_all(pcb, "zone")
             if not find(z, "keepout") and find(z, "layer") is not None}
    if GROUND_LAYER not in zones:
        fail(f"board: no {GROUND_LAYER} ground pour - an inverted-F radiates "
             "against its ground plane, so a model without one answers a "
             "different question")
        return
    strays = [l for l in zones if l != GROUND_LAYER]
    if strays:
        fail(f"board: ground pour on {', '.join(strays)} as well as "
             f"{GROUND_LAYER} - Figure 3 puts the ground on layer 2 only, and "
             "top-side ground beside the feed makes the launch coplanar, so an "
             "MSL port would no longer describe it")
    if str(find(zones[GROUND_LAYER], "net_name")[1]) != "GND":
        fail(f"board: the {GROUND_LAYER} pour is not on GND")
    x0, y0, x1, y1 = zone_bbox(zones[GROUND_LAYER])
    notes.append(f"board: ground plane {x1 - x0:.1f} x {y1 - y0:.1f} mm on "
                 f"{GROUND_LAYER} only, as Figure 3 draws it - no ground copper "
                 "on F.Cu")

    keepout = zone_by_name(pcb, "ANTENNA_KEEPOUT")
    edge = plane_edge(pcb)
    if edge is None:
        return
    if keepout is None:
        fail("board: no ANTENNA_KEEPOUT zone")
    elif abs(zone_bbox(keepout)[3] - edge) > EPS:
        fail("board: the antenna keep-out does not end at the plane edge")
    else:
        notes.append(f"board: antenna keep-out runs down to the plane edge at "
                     f"y = {edge}, on F.Cu and B.Cu")


def check_port_reference(pcb):
    """The port pad must have B.Cu copper under it, fill or no fill.

    This is the error RFsim reports by name: "no copper on reference layer
    B.Cu under the pad".  A zone would satisfy it once filled, but zones ship
    unfilled, so the reference is a real pad in the file instead.
    """
    land = port_land(pcb)
    if land is None:
        return
    at = find(land, "at")
    origin = (float(at[1]), float(at[2]))
    rot = float(at[3]) if len(at) > 3 else 0.0

    def pad_rect(pad):
        pat, size = find(pad, "at"), find(pad, "size")
        rx, ry = rotate((float(pat[1]), float(pat[2])), -rot)
        cx, cy = origin[0] + rx, origin[1] + ry
        w, h = float(size[1]), float(size[2])
        if rot % 180:
            w, h = h, w
        return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)

    signal = [p for p in find_all(land, "pad") if str(p[1]) == "1"]
    ground = [p for p in find_all(land, "pad")
              if "B.Cu" in [str(l) for l in find(p, "layers")[1:]]]
    if not signal:
        fail(f"board: {PORT_LAND} has no pad 1 for the port to drive")
        return
    if not ground:
        fail(f"board: {PORT_LAND} has no B.Cu pad - the port would have no "
             "reference copper until someone remembers to fill the zones")
        return
    sig, gnd = pad_rect(signal[0]), pad_rect(ground[0])
    if str(find(signal[0], "net")[2]) != "ANT_FEED":
        fail("board: the port pad is not on ANT_FEED")
    if str(find(ground[0], "net")[2]) != "GND":
        fail("board: the port's reference pad is not on GND")
    if not (gnd[0] <= sig[0] and gnd[1] <= sig[1]
            and gnd[2] >= sig[2] and gnd[3] >= sig[3]):
        fail(f"board: the port pad {sig} is not fully inside its B.Cu ground "
             f"pad {gnd} - RFsim reports 'no copper on reference layer B.Cu "
             "under the pad' for exactly this")
    else:
        notes.append(f"port: pad 1 is {sig[2] - sig[0]:.2f} x {sig[3] - sig[1]:.2f} mm "
                     f"over a {gnd[2] - gnd[0]:.2f} x {gnd[3] - gnd[1]:.2f} mm B.Cu "
                     "ground pad, so the reference is real copper and does not "
                     "wait on a zone fill")
    return sig


def check_feed(pcb, port_pad):
    """One continuous feed line, from the port pad to the antenna's feed pad."""
    _fp, _poly, pads = antenna(pcb)
    if pads is None:
        return
    segs = feed_segments(pcb)
    if not segs:
        fail("board: no feed line - RFsim attaches port 1 to a track, and there "
             "is no track to attach it to")
        return

    ends = {}
    for a, b, _w in segs:
        for pt in (a, b):
            ends[q(pt)] = ends.get(q(pt), 0) + 1
    loose = [pt for pt, n in ends.items() if n == 1]
    if len(loose) != 2:
        fail(f"board: the feed line is not one unbranched run ({len(loose)} loose "
             "ends) - RFsim would launch into whichever it finds first")
        return

    feed_pad = pads["1"]["centre"]
    at_pad = [pt for pt in loose if math.dist(pt, feed_pad) < EPS]
    on_port = [pt for pt in loose if port_pad and
               port_pad[0] - EPS <= pt[0] <= port_pad[2] + EPS and
               port_pad[1] - EPS <= pt[1] <= port_pad[3] + EPS]
    if not at_pad:
        fail(f"board: no end of the feed line lands on the antenna feed pad at "
             f"{q(feed_pad)}")
    if port_pad and not on_port:
        fail("board: the feed line does not reach the port pad, so RFsim would "
             "drive a pad that is not connected to the antenna")
    if not (at_pad and on_port):
        return

    launch = on_port[0]
    width_at = {q(a): w for a, b, w in segs} | {q(b): w for a, b, w in segs}
    length = sum(math.dist(a, b) for a, b, _w in segs)
    notes.append(f"feed: {len(segs)} segments, {length:.1f} mm, from the port pad "
                 f"at {launch} ({width_at[launch]} mm wide) down to the "
                 f"{width_at[q(feed_pad)]} mm antenna pad")
    return launch


def check_the_only_via(pcb):
    """One via on the board, and it is the antenna's own.

    Figure 3 has exactly one: "Via to ground", the W1 = 0.90 mm pad that shorts
    the inverted-F.  With no top pour there is nothing else to stitch, so a
    stray via here means something has been added that the figure does not have.
    """
    _fp, _poly, pads = antenna(pcb)
    if pads is None:
        return
    extra = [(float(find(v, "at")[1]), float(find(v, "at")[2]))
             for v in find_all(pcb, "via")]
    if extra:
        fail(f"board: {len(extra)} stitching via(s) at {extra[:3]} - with ground "
             "on layer 2 only there is no top pour to tie down, and Figure 3 has "
             "one via in it: the antenna's")

    short = pads.get("2")
    if short is None:
        fail("board: the antenna has no pad 2 - an inverted-F has to be shorted "
             "to ground")
        return
    if short["type"] != "thru_hole" or short["drill"] is None:
        fail("board: the antenna's ground pad is not a plated through hole, so "
             "nothing carries the short down to layer 2 - Figure 3 calls it "
             "'Via to ground'")
    elif short["net"] != "GND":
        fail("board: the antenna's ground pad is not on GND")
    else:
        w = short["rect"][2] - short["rect"][0]
        notes.append(f"board: one via on the board - the antenna's own ground pad, "
                     f"{w:.2f} mm wide with a {short['drill']} mm drill, which is "
                     "Figure 3's 'Via to ground' (W1 = 0.90 mm)")


def check_keepout(pcb):
    """Nothing reaches above the ground plane edge except the antenna itself.

    The feed's neck stops exactly on the edge: its centre line ends on the
    antenna's feed pad 0.25 mm below it and it is 0.50 mm wide, so the neck's
    upper edge and the plane edge are the same line.  Widen that neck and its
    copper is inside the antenna's clear area.
    """
    edge = plane_edge(pcb)
    if edge is None:
        return
    for a, b, w in feed_segments(pcb):
        top = min(a[1], b[1]) - w / 2
        if top < edge - EPS:
            fail(f"board: feed copper reaches y = {top:.2f}, above the plane edge "
                 f"at {edge} - that is inside the antenna keep-out")
    for v in find_all(pcb, "via"):
        at = find(v, "at")
        radius = float(find(v, "size")[1]) / 2
        if float(at[2]) - radius < edge:
            fail(f"board: via at ({at[1]}, {at[2]}) reaches into the antenna "
                 f"keep-out above y = {edge}")
    notes.append(f"board: the feed is the only copper crossing the plane edge at "
                 f"y = {edge}, and its neck stops exactly on it")


def point_to_segment(p, a, b) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length2 = dx * dx + dy * dy
    if length2 < EPS:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / length2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def check_zones_unfilled(pcb):
    unfilled = [str(find(z, "layer")[1]) for z in find_all(pcb, "zone")
                if not find(z, "keepout") and not find_all(z, "filled_polygon")]
    if unfilled:
        notes.append(f"board: {len(unfilled)} copper zone(s) carry no fill yet - "
                     "open the board and press B before simulating, or the model "
                     "has no ground plane")


def check_schematic():
    """The sheet agrees with the board, and has no connector on it either."""
    if not SCH_PATH.exists():
        fail(f"schematic: {SCH_PATH.name} is missing - RFsim is run on a project, "
             "not a loose board file")
        return
    sch = parse(SCH_PATH.read_text())
    lib = {str(s[1]): s for s in find_all(parse(LIB_PATH.read_text()), "symbol")}
    embedded = find_all(find(sch, "lib_symbols"), "symbol")
    for sym in embedded:
        lib_id = str(sym[1])
        nickname, _, name = lib_id.partition(":")
        if nickname != "SWRA117D_RF":
            fail(f"schematic: {lib_id} comes from an external library, so KiCad "
                 "will compare it against whatever version is installed")
        elif name not in lib:
            fail(f"schematic: {lib_id} is not in library/SWRA117D_RF.kicad_sym")
        elif sym != [lib[name][0], lib_id] + lib[name][2:]:
            fail(f"schematic: embedded copy of {lib_id} differs from the library")

    wires = [[(float(p[1]), float(p[2])) for p in find(w, "pts")[1:]]
             for w in find_all(sch, "wire")]
    placed = []
    for sym in find_all(sch, "symbol"):
        if find(sym, "lib_id") is None:
            continue
        lib_id = str(find(sym, "lib_id")[1])
        at = find(sym, "at")
        pos = (float(at[1]), float(at[2]))
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = next(p[2] for p in find_all(sym, "property") if p[1] == "Reference")
        defn = next((s for s in embedded if str(s[1]) == lib_id), None)
        if defn is None:
            fail(f"schematic: {ref} uses {lib_id}, which is not in lib_symbols")
            continue
        for unit in find_all(defn, "symbol"):
            for pin in find_all(unit, "pin"):
                pat = find(pin, "at")
                rx, ry = rotate((float(pat[1]), float(pat[2])), rot)
                placed.append((ref, str(find(pin, "number")[1]),
                               (pos[0] + rx, pos[1] - ry), lib_id))
    for ref, number, pos, _lib in placed:
        if not any(on_segment(pos, a, b) for a, b in wires):
            fail(f"schematic: pin {ref}.{number} at {q(pos)} touches no wire")

    refs = {ref for ref, _n, _p, _l in placed}
    if any(lib_id.endswith(("Conn_Coaxial_SMA", ":C", ":L")) for *_r, lib_id in placed):
        fail("schematic: a connector or matching part is still on the sheet")
    if "P1" not in refs:
        fail("schematic: no P1 - nothing marks where the solver drives the line")
    for sym in find_all(sch, "symbol"):
        ref_node = [p for p in find_all(sym, "property") if p[1] == "Reference"]
        if not ref_node or ref_node[0][2] != "P1":
            continue
        fp = next(p[2] for p in find_all(sym, "property") if p[1] == "Footprint")
        if not fp.endswith(PORT_LAND):
            fail(f"schematic: P1 is footprinted {fp!r}, not {PORT_LAND} - the "
                 "port needs a pad on the board with ground under it")
        if str(find(sym, "on_board")[1]) != "yes":
            fail("schematic: P1 is not marked on_board, so its land never "
                 "reaches the PCB and RFsim has no pad to drive")
    notes.append(f"schematic: {len(embedded)} embedded symbols match the library, "
                 f"{len(placed)} pins all land on wires, {sorted(refs)} placed")


def main() -> int:
    if not PCB_PATH.exists():
        print(f"FAIL {PCB_PATH} does not exist - run tools/gen_sim_board.py")
        return 1
    pcb = parse(PCB_PATH.read_text())
    check_no_connector(pcb)
    check_exact_copy(pcb)
    check_ground(pcb)
    port_pad = check_port_reference(pcb)
    check_feed(pcb, port_pad)
    check_the_only_via(pcb)
    check_keepout(pcb)
    check_zones_unfilled(pcb)
    check_schematic()
    for note in notes:
        print(f"ok   {note}")
    for err in errors:
        print(f"FAIL {err}")
    print(f"\n{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
