#!/usr/bin/env python3
"""Static checks for the DN024 monopole project.

Same job as check_project.py does for the first antenna, against the things
that are specific to this one: the radiator is an exact copy of SWRA227E
Table 1, the ground plane is the size the published match belongs to, and the
pi network is wired and populated the way Table 3 says.

    python3 kicad/tools/check_dn024.py
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import find, find_all, parse  # noqa: E402

PRJ_DIR = pathlib.Path(__file__).resolve().parent.parent
PROJECT = "dn024_monopole_868_2440"
SCH = PRJ_DIR / "dn024" / f"{PROJECT}.kicad_sch"
PCB = PRJ_DIR / "dn024" / f"{PROJECT}.kicad_pcb"
LIB = PRJ_DIR / "library" / "TI_DN024.kicad_sym"
MIN_CLEARANCE = 0.15
EPS = 1e-6

# SWRA227E Table 3, the dual band build
TABLE_3 = {"Z61": "DNP", "Z62": "3.9pF", "Z63": "DNP"}
GND_SIZE = (43.0, 63.0)          # Table 2 and Table 3 both name it
TOP_BAND = 2.44e9                # the dual band build's upper band
ER = 4.5
EXPECTED = {
    ("J1", "1"): "RF_IN", ("J1", "2"): "GND",
    ("Z61", "1"): "RF_IN", ("Z61", "2"): "GND",
    ("Z62", "1"): "RF_IN", ("Z62", "2"): "ANT_FEED",
    ("Z63", "1"): "ANT_FEED", ("Z63", "2"): "GND",
    ("AE1", "1"): "ANT_FEED",
}

errors: list[str] = []
notes: list[str] = []


def fail(msg):
    errors.append(msg)


def q(pt):
    return (round(pt[0], 3), round(pt[1], 3))


def rotate(pt, deg):
    r = math.radians(deg)
    return (pt[0] * math.cos(r) - pt[1] * math.sin(r),
            pt[0] * math.sin(r) + pt[1] * math.cos(r))


def on_segment(pt, a, b):
    (px, py), (ax, ay), (bx, by) = pt, a, b
    if abs((bx - ax) * (py - ay) - (by - ay) * (px - ax)) > 1e-6:
        return False
    dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    return -1e-6 <= dot <= (bx - ax) ** 2 + (by - ay) ** 2 + 1e-6


class DSU:
    def __init__(self):
        self.parent = {}

    def find(self, a):
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def board_pads(pcb, nets):
    out = []
    for fp in find_all(pcb, "footprint"):
        at = find(fp, "at")
        origin = (float(at[1]), float(at[2]))
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = next(p[2] for p in find_all(fp, "property") if p[1] == "Reference")
        for pad in find_all(fp, "pad"):
            pat, size = find(pad, "at"), find(pad, "size")
            rx, ry = rotate((float(pat[1]), float(pat[2])), -rot)
            net = find(pad, "net")
            out.append(dict(ref=str(ref), number=str(pad[1]),
                            centre=(origin[0] + rx, origin[1] + ry),
                            size=(float(size[1]), float(size[2])),
                            net=nets[int(net[1])] if net else "",
                            layers=[str(x) for x in find(pad, "layers")[1:]]))
    return out


# ------------------------------------------------------------------ checks
def check_library():
    lib = {str(s[1]) for s in find_all(parse(LIB.read_text()), "symbol")}
    for want in ("ANT_DN024_Monopole", "C", "L", "Conn_Coaxial_SMA", "GND",
                 "PWR_FLAG"):
        if want not in lib:
            fail(f"library: TI_DN024.kicad_sym has no {want}")
    fps = sorted((PRJ_DIR / "library" / "TI_DN024.pretty").glob("*.kicad_mod"))
    for fp in fps:
        if parse(fp.read_text())[0] != "footprint":
            fail(f"library: {fp.name} is not in the modern footprint format")
    notes.append(f"library: TI_DN024 has {len(lib)} symbols and {len(fps)} "
                 "footprints, all parsing cleanly")


def check_exact_copy():
    """SWRA227E: 'it is important to make an exact copy of the antenna
    dimensions'.  A redrawn or rescaled radiator fails here, not quietly."""
    from verify_against_swra227e import TABLE_1, TOL, measure

    pcb = parse(PCB.read_text())
    name = None
    for fp in find_all(pcb, "footprint"):
        if find(fp, "fp_poly") is not None:
            name = str(fp[1]).split(":", 1)[-1]
    if name is None:
        fail("board: no antenna footprint on the board")
        return
    path = PRJ_DIR / "library" / "TI_DN024.pretty" / f"{name}.kicad_mod"
    try:
        got, info = measure(path)
    except SystemExit as exc:
        fail(f"board: {name} does not have the reference geometry ({exc})")
        return
    off = {k: got[k] - v for k, v in TABLE_1.items() if abs(got[k] - v) > TOL}
    if off:
        fail(f"board: {name} is not an exact copy of SWRA227E Table 1 - " +
             ", ".join(f"{k} by {v * 1000:+.0f} um" for k, v in sorted(off.items())))
    else:
        notes.append(f"board: {name} matches all {len(TABLE_1)} dimensions of "
                     f"SWRA227E Table 1 within {TOL * 1000:.0f} um (exact copy), "
                     f"on {' + '.join(info['layers'])}")


def check_ground_plane(pcb):
    """The published match belongs to a 43 x 63 mm plane, and only to it."""
    zones = {str(find(z, "layer")[1]): z for z in find_all(pcb, "zone")
             if not find(z, "keepout") and find(z, "layer") is not None}
    for layer in ("F.Cu", "B.Cu"):
        if layer not in zones:
            fail(f"board: no {layer} ground pour")
    if len(zones) < 2:
        return
    boxes = {}
    for layer, zone in zones.items():
        pts = [(float(xy[1]), float(xy[2]))
               for xy in find(find(zone, "polygon"), "pts")[1:]]
        boxes[layer] = (max(p[0] for p in pts) - min(p[0] for p in pts),
                        max(p[1] for p in pts) - min(p[1] for p in pts))
        if str(find(zone, "net_name")[1]) != "GND":
            fail(f"board: the {layer} pour is not on GND")
    if boxes["F.Cu"] != boxes["B.Cu"]:
        fail("board: the top and bottom pours do not cover the same area")
    w, h = boxes["B.Cu"]
    if abs(w - GND_SIZE[0]) > EPS or abs(h - GND_SIZE[1]) > EPS:
        fail(f"board: the ground plane is {w:.1f} x {h:.1f} mm, not the "
             f"{GND_SIZE[0]} x {GND_SIZE[1]} mm the published match belongs to - "
             "SWRA227E section 3: a larger plane needs L4 reduced or the match "
             "recalculated")
    else:
        notes.append(f"board: ground plane {w:.1f} x {h:.1f} mm on F.Cu and "
                     "B.Cu, the size SWRA227E Table 3 measured the match on")


def check_pi_network(pcb, pads):
    """Z62 in series, Z61 and Z63 shunt, populated as Table 3 says."""
    by_ref = {}
    for pad in pads:
        by_ref.setdefault(pad["ref"], {})[pad["number"]] = pad
    for ref, value in TABLE_3.items():
        if ref not in by_ref:
            fail(f"board: {ref} is not on the board - the note asks for a pi "
                 "network at the feed, including the positions left unfitted")
            continue
        fp = next(f for f in find_all(pcb, "footprint")
                  if any(p[2] == ref for p in find_all(f, "property")
                         if p[1] == "Reference"))
        got = next(p[2] for p in find_all(fp, "property") if p[1] == "Value")
        if got != value:
            fail(f"board: {ref} is {got!r}, SWRA227E Table 3 says {value!r}")
    if errors:
        return
    series = by_ref["Z62"]
    if {series["1"]["net"], series["2"]["net"]} != {"RF_IN", "ANT_FEED"}:
        fail("board: Z62 is not in series between the connector and the antenna")
    for ref in ("Z61", "Z63"):
        nets = {by_ref[ref]["1"]["net"], by_ref[ref]["2"]["net"]}
        if "GND" not in nets:
            fail(f"board: {ref} is not a shunt - neither pad is on GND")
    if by_ref["Z61"]["1"]["net"] != "RF_IN":
        fail("board: Z61 is not on the connector side of Z62")
    if by_ref["Z63"]["1"]["net"] != "ANT_FEED":
        fail("board: Z63 is not on the antenna side of Z62")
    if not errors:
        notes.append("pi network: Z62 series between RF_IN and ANT_FEED, Z61 "
                     "shunt on the connector side, Z63 shunt on the antenna "
                     "side; Z61 and Z63 laid out and unfitted, as Table 3 says")

    # the shunt pads' ground side has to reach the bottom plane, and the pour
    # is cut away around the network, so it has to be a via
    vias = [(float(find(v, "at")[1]), float(find(v, "at")[2]))
            for v in find_all(pcb, "via")]
    for ref in ("Z61", "Z63"):
        gnd = next(p for p in by_ref[ref].values() if p["net"] == "GND")
        near = min((math.dist(gnd["centre"], v) for v in vias), default=1e9)
        if near > 2.5:
            fail(f"board: {ref}'s ground pad is {near:.1f} mm from the nearest "
                 "via - inside the network's pour cut-out there is no top "
                 "ground for it to land on, so that is its only way to the plane")
    if not errors:
        notes.append("pi network: both shunt ground pads reach the bottom plane "
                     "through a via of their own")


def check_two_layer_radiator(pcb):
    """The radiator is on both layers, and they are stitched into one conductor.

    Section 3 of SWRA227E puts the layout on both layers "for lower resistive
    loss and slightly wider bandwidth".  Two sheets joined only at the feed are
    not that: they are a 150 mm parallel-plate line, open at the tip, with
    resonances inside the band the antenna works in.  So the stitching is
    checked the way ground stitching is - by pitch against the wavelength in
    the dielectric - and every via has to sit in the copper it is tying.
    """
    fp = next((f for f in find_all(pcb, "footprint")
               if find(f, "fp_poly") is not None), None)
    if fp is None:
        return
    layers = sorted({str(find(poly, "layer")[1]) for poly in find_all(fp, "fp_poly")})
    if layers != ["B.Cu", "F.Cu"]:
        fail(f"board: the radiator is on {layers}; SWRA227E puts it on both")
        return

    at = find(fp, "at")
    origin = (float(at[1]), float(at[2]))
    poly = [(origin[0] + float(xy[1]), origin[1] + float(xy[2]))
            for xy in find(find_all(fp, "fp_poly")[0], "pts")[1:]]
    # the feed is a rectangular plated pad straddling the end of the ribbon;
    # the stitches are round and sit on the centre line
    holes = [p for p in find_all(fp, "pad") if str(p[2]) == "thru_hole"]
    vias = [p for p in holes if str(p[3]) == "circle"]
    if len(holes) < 2 or not vias:
        fail("board: nothing stitches the radiator's two layers together except "
             "the feed, so they are a transmission line rather than one conductor")
        return

    centres = [(origin[0] + float(find(p, "at")[1]),
                origin[1] + float(find(p, "at")[2])) for p in holes]
    for pad in vias:
        pat = find(pad, "at")
        c = (origin[0] + float(pat[1]), origin[1] + float(pat[2]))
        radius = max(float(x) for x in find(pad, "size")[1:]) / 2
        if not inside(poly, c):
            fail(f"board: a stitching via at {q(c)} is not inside the radiator")
        elif edge_distance(poly, c) < radius:
            fail(f"board: a stitching via at {q(c)} is {edge_distance(poly, c):.2f} mm "
                 f"from the edge of a {radius * 2} mm trace - it would break out")
        if [str(l) for l in find(pad, "layers")[1:]] not in (["*.Cu"], ["*.Cu", "*.Mask"]):
            fail(f"board: the stitching via at {q(c)} does not reach both layers")

    worst = max(min(math.dist(a, b) for j, b in enumerate(centres) if j != i)
                for i, a in enumerate(centres))
    limit = 299792458.0 / (TOP_BAND * math.sqrt(ER)) * 1e3 / 20
    if worst > limit + EPS:
        fail(f"board: the radiator's two layers are stitched at {worst:.2f} mm, "
             f"over the {limit:.2f} mm that is lambda/20 in FR4 at "
             f"{TOP_BAND / 1e9:.2f} GHz")
    else:
        notes.append(f"board: the radiator is on F.Cu and B.Cu, stitched by "
                     f"{len(vias)} vias no more than {worst:.2f} mm apart "
                     f"(lambda/20 at {TOP_BAND / 1e9:.2f} GHz is {limit:.2f} mm), "
                     "so the two layers are one conductor")


def inside(poly, pt) -> bool:
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
    return hit


def edge_distance(poly, pt) -> float:
    return min(point_to_segment(pt, a, b)
               for a, b in zip(poly, poly[1:] + poly[:1]))


def check_board(pcb, pads, nets):
    for pad in pads:
        want = EXPECTED.get((pad["ref"], pad["number"]))
        if want is None:
            fail(f"board: pad {pad['ref']}.{pad['number']} has no counterpart "
                 "in the schematic")
        elif pad["net"] != want:
            fail(f"board: pad {pad['ref']}.{pad['number']} is on net "
                 f"{pad['net']!r}, expected {want!r}")

    segs = [((float(find(s, "start")[1]), float(find(s, "start")[2])),
             (float(find(s, "end")[1]), float(find(s, "end")[2])),
             float(find(s, "width")[1]), nets[int(find(s, "net")[1])])
            for s in find_all(pcb, "segment")]
    vias = {(q((float(find(v, "at")[1]), float(find(v, "at")[2]))),
             nets[int(find(v, "net")[1])]) for v in find_all(pcb, "via")}
    landing = {(q(p["centre"]), p["net"]) for p in pads} | vias
    counts = {}
    for a, b, _w, net in segs:
        for pt in (a, b):
            counts[(q(pt), net)] = counts.get((q(pt), net), 0) + 1
    loose = [k for k, c in counts.items() if c == 1 and k not in landing]
    if loose:
        fail(f"board: {len(loose)} track end(s) in mid air: {loose[:3]}")

    edge = min(float(xy[2]) for z in find_all(pcb, "zone")
               if not find(z, "keepout")
               for xy in find(find(z, "polygon"), "pts")[1:])
    # Above the plane edge, the only copper allowed is the antenna and the
    # stub that feeds it.  DN024's L5 = 1.0 mm puts the antenna's feed pad that
    # far above the edge, so the feed *has* to cross it - but only on ANT_FEED,
    # and only inside the width of the antenna's own feed pad.
    feed_pad = next((p for p in pads if p["ref"] == "AE1" and p["number"] == "1"),
                    None)
    for a, b, w, net in segs:
        top = min(a[1], b[1]) - w / 2
        if top >= edge - EPS:
            continue
        column = feed_pad and (
            net == "ANT_FEED"
            and min(a[0], b[0]) - w / 2 >= feed_pad["centre"][0]
            - feed_pad["size"][0] / 2 - EPS
            and max(a[0], b[0]) + w / 2 <= feed_pad["centre"][0]
            + feed_pad["size"][0] / 2 + EPS)
        if not column:
            fail(f"board: copper on {net} reaches y = {top:.2f}, above the plane "
                 f"edge at {edge}, outside the antenna's feed column - that is "
                 "inside the area the note requires kept clear")
    for v in find_all(pcb, "via"):
        at = find(v, "at")
        if float(at[2]) - float(find(v, "size")[1]) / 2 < edge:
            fail(f"board: via at ({at[1]}, {at[2]}) is in the antenna keep-out")

    worst = None
    for i, (a1, b1, w1, n1) in enumerate(segs):
        for a2, b2, w2, n2 in segs[i + 1:]:
            if n1 == n2:
                continue
            gap = seg_distance(a1, b1, a2, b2) - w1 / 2 - w2 / 2
            worst = gap if worst is None else min(worst, gap)
            if gap < MIN_CLEARANCE:
                fail(f"board: tracks on {n1} and {n2} are {gap:.3f} mm apart")
    notes.append(f"board: {len(pads)} pads, {len(segs)} tracks, "
                 f"{len(find_all(pcb, 'via'))} vias, every track end lands, "
                 f"keep-out above y = {edge} clean" +
                 (f", closest different-net tracks {worst:.2f} mm" if worst else ""))


def point_to_segment(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    l2 = dx * dx + dy * dy
    if l2 < EPS:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
    return math.dist(p, (a[0] + t * dx, a[1] + t * dy))


def seg_distance(a1, b1, a2, b2):
    return min(point_to_segment(a1, a2, b2), point_to_segment(b1, a2, b2),
               point_to_segment(a2, a1, b1), point_to_segment(b2, a1, b1))


def check_schematic():
    sch = parse(SCH.read_text())
    lib = {str(s[1]): s for s in find_all(parse(LIB.read_text()), "symbol")}
    other = {str(s[1]): s for s in
             find_all(parse((PRJ_DIR / "library" / "SWRA117D_RF.kicad_sym")
                            .read_text()), "symbol")}
    libs = {"TI_DN024": lib, "SWRA117D_RF": other}
    embedded = find_all(find(sch, "lib_symbols"), "symbol")
    for sym in embedded:
        lib_id = str(sym[1])
        nick, _, name = lib_id.partition(":")
        if nick not in libs:
            fail(f"schematic: {lib_id} comes from a library this project does "
                 "not carry, so KiCad compares it against whatever is installed")
        elif name not in libs[nick]:
            fail(f"schematic: {lib_id} is not in {nick}.kicad_sym")
        elif sym != [libs[nick][name][0], lib_id] + libs[nick][name][2:]:
            fail(f"schematic: embedded copy of {lib_id} differs from the library")

    wires = [[(float(p[1]), float(p[2])) for p in find(w, "pts")[1:]]
             for w in find_all(sch, "wire")]
    dsu = DSU()
    for a, b in wires:
        dsu.union(q(a), q(b))
    for label in find_all(sch, "label"):
        name = str(label[1])
        at = find(label, "at")
        pos = (float(at[1]), float(at[2]))
        hit = [(a, b) for a, b in wires if on_segment(pos, a, b)]
        if not hit:
            fail(f"schematic: label {name} at {q(pos)} is not on a wire")
        for a, b in hit:
            dsu.union(q(a), f"net:{name}")

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
            fail(f"schematic: {ref} uses {lib_id}, not in lib_symbols")
            continue
        for unit in find_all(defn, "symbol"):
            for pin in find_all(unit, "pin"):
                pat = find(pin, "at")
                rx, ry = rotate((float(pat[1]), float(pat[2])), rot)
                placed.append((str(ref), str(find(pin, "number")[1]),
                               (pos[0] + rx, pos[1] - ry), lib_id))
    for ref, number, pos, lib_id in placed:
        touching = [(a, b) for a, b in wires if on_segment(pos, a, b)]
        if not touching:
            fail(f"schematic: pin {ref}.{number} at {q(pos)} touches no wire")
            continue
        for a, b in touching:
            dsu.union(q(a), f"pin:{ref}.{number}")
    for ref, number, _pos, lib_id in placed:
        if lib_id.endswith((":GND", ":PWR_FLAG")):
            dsu.union(f"pin:{ref}.{number}", "net:GND")

    for (ref, number), want in EXPECTED.items():
        key = f"pin:{ref}.{number}"
        if key not in dsu.parent:
            fail(f"schematic: {ref}.{number} is not placed")
        elif dsu.find(key) != dsu.find(f"net:{want}"):
            fail(f"schematic: {ref}.{number} is not on {want}")
    notes.append(f"schematic: {len(embedded)} embedded symbols match their "
                 f"libraries, {len(placed)} pins on wires, netlist matches the "
                 "intended one")


def check_zones_unfilled(pcb):
    unfilled = [str(find(z, "layer")[1]) for z in find_all(pcb, "zone")
                if not find(z, "keepout") and not find_all(z, "filled_polygon")]
    if unfilled:
        notes.append(f"board: {len(unfilled)} copper zone(s) carry no fill yet - "
                     "press B in the PCB editor before DRC or any simulation")


def main() -> int:
    if not PCB.exists():
        print(f"FAIL {PCB} does not exist - run tools/gen_dn024_project.py")
        return 1
    pcb = parse(PCB.read_text())
    nets = {int(n[1]): str(n[2]) for n in find_all(pcb, "net")}
    pads = board_pads(pcb, nets)
    check_library()
    check_schematic()
    check_exact_copy()
    check_ground_plane(pcb)
    check_two_layer_radiator(pcb)
    check_board(pcb, pads, nets)
    check_pi_network(pcb, pads)
    check_zones_unfilled(pcb)
    for note in notes:
        print(f"ok   {note}")
    for err in errors:
        print(f"FAIL {err}")
    print(f"\n{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
