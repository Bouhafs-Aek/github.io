#!/usr/bin/env python3
"""Static checks for the simulation-only board.

The fabrication board has its own checker.  This one asks a different
question: is what the solver will see actually the antenna alone?  A model
quietly containing a connector, a stray track or a missing bottom ground is
the single most common reason a published antenna "does not resonate where
the datasheet says".

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
MIN_CLEARANCE = 0.15
MIN_PORT_GAP = 0.3          # below this the gap is thinner than the mesh
PORT_VIA_RADIUS = 2.0       # "at the port" means this close to the feed pad

errors: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def plane_edge(pcb) -> float:
    return min(float(xy[2])
               for zone in find_all(pcb, "zone") if not find(zone, "keepout")
               for xy in find(find(zone, "polygon"), "pts")[1:])


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
    """The antenna footprint, its two pads and its radiator polygon."""
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
            cx = origin[0] + float(pat[1])
            cy = origin[1] + float(pat[2])
            w, h = float(size[1]), float(size[2])
            net = find(pad, "net")
            pads[str(pad[1])] = dict(
                rect=(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2),
                net=str(net[2]) if net is not None else "")
        poly = [(origin[0] + float(xy[1]), origin[1] + float(xy[2]))
                for xy in find(find(fp, "fp_poly"), "pts")[1:]]
        return fp, poly, pads
    return None, None, None


def rect_distance(rect, pt):
    x0, y0, x1, y1 = rect
    dx = max(x0 - pt[0], 0.0, pt[0] - x1)
    dy = max(y0 - pt[1], 0.0, pt[1] - y1)
    return math.hypot(dx, dy)


# ------------------------------------------------------------------- checks
def check_only_the_antenna(pcb):
    """Nothing on this board but the radiator: no connector, no feed line."""
    fps = find_all(pcb, "footprint")
    radiators = [fp for fp in fps if find(fp, "fp_poly") is not None]
    others = [str(fp[1]) for fp in fps if find(fp, "fp_poly") is None]
    if len(radiators) != 1:
        fail(f"board: expected exactly one antenna footprint, found {len(radiators)}")
    if others:
        fail("board: the simulation model still carries " + ", ".join(others) +
             " - a connector inside the model is part of the answer it gives")
    tracks = find_all(pcb, "segment") + find_all(pcb, "arc")
    if tracks:
        fail(f"board: {len(tracks)} track segment(s) on a board that is supposed to "
             "be fed directly at the antenna pad - the line would be simulated too")
    if not errors:
        notes.append("board: one footprint (the radiator), no connector, no tracks - "
                     "the model is the antenna and the ground plane, nothing else")


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


def check_bottom_ground(pcb):
    """A bottom ground plane, congruent with the top pour and on the GND net."""
    zones = {str(find(z, "layer")[1]): z for z in find_all(pcb, "zone")
             if not find(z, "keepout") and find(z, "layer") is not None}
    for layer in ("F.Cu", "B.Cu"):
        if layer not in zones:
            fail(f"board: no {layer} ground pour - an inverted-F radiates against "
                 "its ground plane, so a model without one answers a different question")
    if len(zones) < 2:
        return
    if zone_bbox(zones["F.Cu"]) != zone_bbox(zones["B.Cu"]):
        fail("board: the top and bottom pours do not cover the same area")
    for layer, zone in zones.items():
        if str(find(zone, "net_name")[1]) != "GND":
            fail(f"board: the {layer} pour is not on GND")
    x0, y0, x1, y1 = zone_bbox(zones["B.Cu"])
    notes.append(f"board: bottom ground plane {x1 - x0:.1f} x {y1 - y0:.1f} mm, "
                 f"same outline as the top pour, both on GND")


def check_port_gap(pcb):
    """The port is a gap of known size, held open by a keep-out.

    KiCad's pour clearance would also leave a gap, but it is a design setting:
    someone re-fills the zones with a different clearance and the port they
    simulated is no longer the port on the board.  The keep-out is geometry.
    """
    _fp, poly, pads = antenna(pcb)
    if pads is None:
        return
    pad = pads.get("1")
    if pad is None or pad["net"] != "ANT_FEED":
        fail("board: the antenna's feed pad is not on ANT_FEED")
        return
    zone = zone_by_name(pcb, "RF_PORT_GAP")
    if zone is None:
        fail("board: no RF_PORT_GAP keep-out - nothing holds the port gap open "
             "when the zones are re-filled")
        return
    layers = [str(l) for l in find(zone, "layers")[1:]]
    if layers != ["F.Cu"]:
        fail(f"board: RF_PORT_GAP is on {layers}; it must be F.Cu only, so the "
             "bottom ground stays solid under the port")
    nx0, ny0, nx1, ny1 = zone_bbox(zone)
    edge = plane_edge(pcb)
    if abs(ny0 - edge) > 1e-6:
        fail(f"board: RF_PORT_GAP starts at y = {ny0}, not at the plane edge {edge}")

    # the radiator's bottom bar: the only copper that reaches past the plane edge
    bar = [p for p in poly if p[1] >= edge - 1e-9]
    bar_left = min(p[0] for p in bar)
    bar_bottom = max(p[1] for p in bar)
    gap = ny1 - bar_bottom
    if gap < MIN_PORT_GAP:
        fail(f"board: the port gap is {gap:.2f} mm, under {MIN_PORT_GAP} mm - "
             "thinner than the mesh cell the solver will put across it")
    if nx0 > bar_left - MIN_PORT_GAP:
        fail("board: RF_PORT_GAP does not reach past the left end of the radiator "
             "bar, so the pour still touches it there")
    if abs(nx1 - pads["2"]["rect"][0]) > 1e-6:
        fail(f"board: RF_PORT_GAP ends at x = {nx1:.3f}, not at the short pad's "
             f"left edge {pads['2']['rect'][0]:.3f} - the pour would then short "
             "the bar at the wrong place and D5 would not be the feed-to-short "
             "distance any more")
    elif gap >= MIN_PORT_GAP:
        d5 = pads["2"]["rect"][0] - pad["rect"][2]
        notes.append(f"port: {gap:.2f} mm gap between the radiator and the ground "
                     f"pour, held open by RF_PORT_GAP; the pour meets the radiator "
                     f"at the short pad only, so D5 is {d5:.2f} mm")


def check_port_vias(pcb):
    """Ground vias at the port, not just somewhere on the board.

    Everything between the port and the nearest via is series inductance in
    front of the antenna: 0.54 nH per via, but several millimetres of top pour
    detour is worth considerably more than that at 2.45 GHz.
    """
    _fp, _poly, pads = antenna(pcb)
    if pads is None:
        return
    vias = [(float(find(v, "at")[1]), float(find(v, "at")[2]))
            for v in find_all(pcb, "via")]
    if not vias:
        fail("board: no ground vias at all - the top pour is not a ground plane, "
             "it is a floating sheet")
        return
    for v in find_all(pcb, "via"):
        at = find(v, "at")
        pos = (float(at[1]), float(at[2]))
        if str(find(v, "net")[1]) != "1":
            fail(f"board: via at {pos} is not on GND")
        if [str(l) for l in find(v, "layers")[1:]] != ["F.Cu", "B.Cu"]:
            fail(f"board: via at {pos} does not go F.Cu -> B.Cu - it ties the top "
                 "pour to nothing")

    pad = pads["1"]["rect"]
    near = [v for v in vias if rect_distance(pad, v) <= PORT_VIA_RADIUS]
    if len(near) < 4:
        fail(f"board: only {len(near)} ground via(s) within {PORT_VIA_RADIUS} mm of "
             "the port - the return current has to detour before it reaches the "
             "bottom plane, and that detour is in series with the antenna")
    else:
        closest = min(rect_distance(pad, v) for v in near)
        notes.append(f"port: {len(near)} ground vias within {PORT_VIA_RADIUS} mm of "
                     f"the feed pad, nearest at {closest:.2f} mm")
    notes.append(f"board: {len(vias)} ground vias total, all F.Cu -> B.Cu")


def check_clearances(pcb):
    """Nothing shorts the port, and nothing sits in the antenna keep-out."""
    _fp, _poly, pads = antenna(pcb)
    if pads is None:
        return
    pad = pads["1"]["rect"]
    edge = plane_edge(pcb)
    gap_zone = zone_by_name(pcb, "RF_PORT_GAP")
    gap = zone_bbox(gap_zone) if gap_zone is not None else None
    worst = None
    for v in find_all(pcb, "via"):
        at = find(v, "at")
        pos = (float(at[1]), float(at[2]))
        radius = float(find(v, "size")[1]) / 2
        clear = rect_distance(pad, pos) - radius
        if clear < MIN_CLEARANCE:
            fail(f"board: via at {pos} is {clear:.3f} mm from the ANT_FEED pad")
        worst = clear if worst is None else min(worst, clear)
        if pos[1] - radius < edge:
            fail(f"board: via at {pos} reaches into the antenna keep-out above "
                 f"y = {edge}")
        if gap and gap[0] - radius < pos[0] < gap[2] + radius \
                and gap[1] - radius < pos[1] < gap[3] + radius:
            fail(f"board: via at {pos} sits in the port gap")
    if worst is not None:
        notes.append(f"board: every via clears the port pad by at least "
                     f"{worst:.2f} mm (minimum {MIN_CLEARANCE} mm)")

    keepout = zone_by_name(pcb, "ANTENNA_KEEPOUT")
    if keepout is None:
        fail("board: no ANTENNA_KEEPOUT zone")
    elif abs(zone_bbox(keepout)[3] - edge) > 1e-6:
        fail("board: the antenna keep-out does not end at the plane edge")
    else:
        notes.append(f"board: antenna keep-out runs down to the plane edge at "
                     f"y = {edge}, on F.Cu and B.Cu")


def check_zones_unfilled(pcb):
    """Generated zones carry no fill: an unfilled pour is not a ground plane."""
    unfilled = [str(find(z, "layer")[1]) for z in find_all(pcb, "zone")
                if not find(z, "keepout") and not find_all(z, "filled_polygon")]
    if unfilled:
        notes.append(f"board: {len(unfilled)} copper zone(s) carry no fill yet - "
                     "open the board and press B before simulating, or the model "
                     "has no ground plane")


def main() -> int:
    if not PCB_PATH.exists():
        print(f"FAIL {PCB_PATH} does not exist - run tools/gen_sim_board.py")
        return 1
    pcb = parse(PCB_PATH.read_text())
    check_only_the_antenna(pcb)
    check_exact_copy(pcb)
    check_bottom_ground(pcb)
    check_port_gap(pcb)
    check_port_vias(pcb)
    check_clearances(pcb)
    check_zones_unfilled(pcb)
    for note in notes:
        print(f"ok   {note}")
    for err in errors:
        print(f"FAIL {err}")
    print(f"\n{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
