#!/usr/bin/env python3
"""Static checks for the RFsim project (schematic + board).

The fabrication project has its own checker.  This one asks a different
question: is what the solver sees the antenna and its feed, and nothing else?
A model quietly containing a connector, or missing a ground plane, is the
commonest reason a published antenna "does not resonate where the datasheet
says".

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
LAUNCH_VIA_RADIUS = 6.0     # "at the launch" means this close to the track end
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


def plane_edge(pcb) -> float:
    return min(float(xy[2])
               for zone in find_all(pcb, "zone") if not find(zone, "keepout")
               for xy in find(find(zone, "polygon"), "pts")[1:])


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
            pads[str(pad[1])] = dict(
                centre=(cx, cy),
                rect=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
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
def check_no_connector(pcb):
    """Nothing on this board but the radiator and its line."""
    fps = find_all(pcb, "footprint")
    radiators = [fp for fp in fps if find(fp, "fp_poly") is not None]
    others = [str(fp[1]) for fp in fps if find(fp, "fp_poly") is None]
    if len(radiators) != 1:
        fail(f"board: expected exactly one antenna footprint, found {len(radiators)}")
    if others:
        fail("board: the model still carries " + ", ".join(others) +
             " - a connector inside the model is part of the answer it gives, "
             "and its ground pads carry the port's return current")
    else:
        notes.append("board: one footprint (the radiator) and no connector - "
                     "the port launches off the bare feed line")


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
    """A ground plane on both layers, congruent, on GND."""
    zones = {str(find(z, "layer")[1]): z for z in find_all(pcb, "zone")
             if not find(z, "keepout") and find(z, "layer") is not None}
    for layer in ("F.Cu", "B.Cu"):
        if layer not in zones:
            fail(f"board: no {layer} ground pour - an inverted-F radiates against "
                 "its ground plane, so a model without one answers a different "
                 "question")
    if len(zones) < 2:
        return
    if zone_bbox(zones["F.Cu"]) != zone_bbox(zones["B.Cu"]):
        fail("board: the top and bottom pours do not cover the same area")
    for layer, zone in zones.items():
        if str(find(zone, "net_name")[1]) != "GND":
            fail(f"board: the {layer} pour is not on GND")
    x0, y0, x1, y1 = zone_bbox(zones["B.Cu"])
    notes.append(f"board: ground plane {x1 - x0:.1f} x {y1 - y0:.1f} mm on F.Cu "
                 "and B.Cu, same outline, both on GND")

    keepout = zone_by_name(pcb, "ANTENNA_KEEPOUT")
    edge = plane_edge(pcb)
    if keepout is None:
        fail("board: no ANTENNA_KEEPOUT zone")
    elif abs(zone_bbox(keepout)[3] - edge) > EPS:
        fail("board: the antenna keep-out does not end at the plane edge")
    else:
        notes.append(f"board: antenna keep-out runs down to the plane edge at "
                     f"y = {edge}, on F.Cu and B.Cu")


def check_feed(pcb):
    """One continuous feed line, from the board edge to the antenna's feed pad."""
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

    x0, y0, x1, y1 = outline(pcb)
    feed_pad = pads["1"]["centre"]
    at_pad = [pt for pt in loose if math.dist(pt, feed_pad) < EPS]
    at_edge = [pt for pt in loose
               if min(abs(pt[0] - x0), abs(pt[0] - x1),
                      abs(pt[1] - y0), abs(pt[1] - y1)) < EPS]
    if not at_pad:
        fail(f"board: no end of the feed line lands on the antenna feed pad at "
             f"{q(feed_pad)}")
    if not at_edge:
        fail("board: the feed line does not reach the board edge, so there is "
             "nowhere at the edge for the port to launch from")
    if not (at_pad and at_edge):
        return

    launch = at_edge[0]
    width_at = {q(a): w for a, b, w in segs} | {q(b): w for a, b, w in segs}
    length = sum(math.dist(a, b) for a, b, _w in segs)
    notes.append(f"feed: {len(segs)} segments, {length:.1f} mm, from the board "
                 f"edge at {launch} ({width_at[launch]} mm wide) down to the "
                 f"{width_at[q(feed_pad)]} mm antenna pad - port 1 goes on the "
                 "edge end")
    return launch


def check_launch_vias(pcb, launch):
    """Ground vias at the launch, not just somewhere on the board."""
    if launch is None:
        return
    vias = []
    for v in find_all(pcb, "via"):
        at = find(v, "at")
        pos = (float(at[1]), float(at[2]))
        vias.append(pos)
        if str(find(v, "net")[1]) != "1":
            fail(f"board: via at {pos} is not on GND")
        if [str(l) for l in find(v, "layers")[1:]] != ["F.Cu", "B.Cu"]:
            fail(f"board: via at {pos} does not go F.Cu -> B.Cu - it ties the "
                 "top pour to nothing")
    if not vias:
        fail("board: no ground vias at all - the top pour is not a ground plane, "
             "it is a floating sheet")
        return
    near = [v for v in vias if math.dist(v, launch) <= LAUNCH_VIA_RADIUS]
    if len(near) < 4:
        fail(f"board: only {len(near)} ground via(s) within {LAUNCH_VIA_RADIUS} mm "
             "of the launch - the port's return current has to detour across the "
             "top pour before it reaches the bottom plane, and that detour is in "
             "series with everything downstream")
    else:
        notes.append(f"port: {len(near)} ground vias within {LAUNCH_VIA_RADIUS} mm "
                     f"of the launch, nearest at "
                     f"{min(math.dist(v, launch) for v in near):.2f} mm")
    notes.append(f"board: {len(vias)} ground vias total, all F.Cu -> B.Cu")


def check_clearances(pcb):
    """Ground copper keeps away from the feed line and out of the keep-out."""
    edge = plane_edge(pcb)
    segs = feed_segments(pcb)
    if not segs:
        return                    # check_feed has already said so
    worst = None
    for v in find_all(pcb, "via"):
        at = find(v, "at")
        pos = (float(at[1]), float(at[2]))
        radius = float(find(v, "size")[1]) / 2
        for a, b, w in segs:
            gap = point_to_segment(pos, a, b) - radius - w / 2
            if gap < MIN_CLEARANCE:
                fail(f"board: via at {pos} is {gap:.3f} mm from the feed line")
            worst = gap if worst is None else min(worst, gap)
        if pos[1] - radius < edge:
            fail(f"board: via at {pos} reaches into the antenna keep-out above "
                 f"y = {edge}")
    if worst is not None:
        notes.append(f"board: every via clears the feed line by at least "
                     f"{worst:.2f} mm (minimum {MIN_CLEARANCE} mm)")

    corridor = zone_by_name(pcb, "RF_POUR_KEEPAWAY")
    if corridor is None:
        fail("board: no RF_POUR_KEEPAWAY rule area - the top pour would come up "
             "to the feed line and turn the microstrip into a narrow-gap "
             "coplanar waveguide of a different impedance")
    else:
        cx0, _cy0, cx1, _cy1 = zone_bbox(corridor)
        line_w = max(w for _a, _b, w in segs)
        gap = (cx1 - cx0 - line_w) / 2
        notes.append(f"board: the top pour is held {gap:.2f} mm off the "
                     f"{line_w} mm line, so it stays a microstrip")


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
        if ref_node and ref_node[0][2] == "P1":
            if str(find(sym, "on_board")[1]) != "no":
                fail("schematic: P1 is marked on_board - it is the solver's "
                     "source, not a part, and has no footprint to place")
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
    launch = check_feed(pcb)
    check_launch_vias(pcb, launch)
    check_clearances(pcb)
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
