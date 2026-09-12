#!/usr/bin/env python3
"""Static checks for the generated KiCad files.

KiCad itself is the final judge, but these checks catch the mistakes that are
easy to make when files are generated: a pin that does not sit on a wire, a
track that ends in mid air, a pad wired to the wrong net, copper inside the
antenna keep-out, or a clearance violation.

    python3 kicad/tools/check_project.py
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import find, find_all, parse  # noqa: E402

PRJ_DIR = pathlib.Path(__file__).resolve().parent.parent
PROJECT = "swra117d_2g4_antenna"
MIN_CLEARANCE = 0.15
EPS = 1e-6

errors: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def q(pt):
    return (round(pt[0], 3), round(pt[1], 3))


def plane_edge(pcb) -> float:
    """Top edge of the ground plane, read from the board's own copper zones.

    Never hardcode this: the antenna footprint's keep-out box sets it, so it
    moves when the antenna is repositioned or rescaled, and a checker holding
    a stale value reports the board as broken when it is the checker that is.
    """
    return min(float(xy[2])
               for zone in find_all(pcb, "zone") if not find(zone, "keepout")
               for xy in find(find(zone, "polygon"), "pts")[1:])


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


def on_segment(pt, a, b) -> bool:
    (px, py), (ax, ay), (bx, by) = pt, a, b
    cross = (bx - ax) * (py - ay) - (by - ay) * (px - ax)
    if abs(cross) > 1e-6:
        return False
    dot = (px - ax) * (bx - ax) + (py - ay) * (by - ay)
    length2 = (bx - ax) ** 2 + (by - ay) ** 2
    return -1e-6 <= dot <= length2 + 1e-6


def rotate(pt, deg):
    rad = math.radians(deg)
    return (pt[0] * math.cos(rad) - pt[1] * math.sin(rad),
            pt[0] * math.sin(rad) + pt[1] * math.cos(rad))


# --------------------------------------------------------------- schematic
def symbol_pins(defn):
    """(number, (x, y)) for every pin of a lib_symbols entry."""
    out = []
    for unit in find_all(defn, "symbol"):
        for pin in find_all(unit, "pin"):
            at = find(pin, "at")
            number = find(pin, "number")[1]
            out.append((str(number), (float(at[1]), float(at[2]))))
    return out


def check_schematic(expected_nets):
    sch = parse((PRJ_DIR / f"{PROJECT}.kicad_sch").read_text())
    lib = {str(s[1]): s for s in find_all(find(sch, "lib_symbols"), "symbol")}
    wires = [[(float(p[1]), float(p[2])) for p in find(w, "pts")[1:]]
             for w in find_all(sch, "wire")]
    labels = [(str(l[1]), (float(find(l, "at")[1]), float(find(l, "at")[2])))
              for l in find_all(sch, "label")]

    dsu = DSU()
    for a, b in wires:
        dsu.union(q(a), q(b))
    for name, pos in labels:
        hit = any(on_segment(pos, a, b) for a, b in wires)
        if not hit:
            fail(f"schematic: label {name} at {pos} is not on a wire")
        for a, b in wires:
            if on_segment(pos, a, b):
                dsu.union(q(a), f"label:{name}")

    placed = []
    for sym in find_all(sch, "symbol"):
        lib_id = str(find(sym, "lib_id")[1])
        at = find(sym, "at")
        pos = (float(at[1]), float(at[2]))
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = next(p[2] for p in find_all(sym, "property") if p[1] == "Reference")
        if lib_id not in lib:
            fail(f"schematic: {ref} uses {lib_id}, which is not in lib_symbols")
            continue
        for number, local in symbol_pins(lib[lib_id]):
            rx, ry = rotate(local, rot)
            abs_pos = (pos[0] + rx, pos[1] - ry)
            placed.append((str(ref), number, abs_pos, lib_id))
    for ref, number, pos, _lib in placed:
        touching = [(a, b) for a, b in wires if on_segment(pos, a, b)]
        if not touching:
            fail(f"schematic: pin {ref}.{number} at {q(pos)} touches no wire")
            continue
        for a, b in touching:
            dsu.union(q(a), f"pin:{ref}.{number}")

    # power symbols are global: tie every GND pin, and the ERC flag, together
    for ref, number, _pos, lib_id in placed:
        if lib_id.endswith(":GND") or lib_id.endswith(":PWR_FLAG"):
            dsu.union(f"pin:{ref}.{number}", "label:GND")

    got = {}
    for ref, number, _pos, lib_id in placed:
        if lib_id.endswith(":GND") or lib_id.endswith(":PWR_FLAG"):
            continue
        root = dsu.find(f"pin:{ref}.{number}")
        name = next((str(k)[6:] for k in dsu.parent
                     if str(k).startswith("label:") and dsu.find(k) == root), None)
        got[(ref, number)] = name
    for (ref, number), want in expected_nets.items():
        have = got.get((ref, number))
        if have != want:
            fail(f"schematic: {ref}.{number} is on net {have!r}, expected {want!r}")
    notes.append(f"schematic: {len(placed)} pins placed, "
                 f"{len(wires)} wires, netlist matches the intended one")
    return got


# -------------------------------------------------------------------- board
class Pad:
    def __init__(self, ref, number, center, size, angle, net, layers):
        self.ref, self.number = ref, number
        self.center, self.size, self.angle = center, size, angle
        self.net, self.layers = net, layers

    def to_local(self, pt):
        dx, dy = pt[0] - self.center[0], pt[1] - self.center[1]
        return rotate((dx, dy), self.angle)  # board angle is CCW on screen

    def contains(self, pt) -> bool:
        lx, ly = self.to_local(pt)
        return abs(lx) <= self.size[0] / 2 + EPS and abs(ly) <= self.size[1] / 2 + EPS

    def distance(self, pt) -> float:
        lx, ly = self.to_local(pt)
        dx = max(abs(lx) - self.size[0] / 2, 0.0)
        dy = max(abs(ly) - self.size[1] / 2, 0.0)
        return math.hypot(dx, dy)

    def distance_to_segment(self, a, b, steps=400) -> float:
        return min(self.distance((a[0] + (b[0] - a[0]) * i / steps,
                                  a[1] + (b[1] - a[1]) * i / steps))
                   for i in range(steps + 1))

    def copper_layers(self):
        out = set()
        for layer in self.layers:
            if layer == "*.Cu":
                out |= {"F.Cu", "B.Cu"}
            elif layer.endswith(".Cu"):
                out.add(layer)
        return out


def check_board(expected_nets):
    pcb = parse((PRJ_DIR / f"{PROJECT}.kicad_pcb").read_text())
    nets = {int(n[1]): str(n[2]) for n in find_all(pcb, "net")}
    gnd_edge_y = plane_edge(pcb)
    pads: list[Pad] = []
    poly_points = []

    for fp in find_all(pcb, "footprint"):
        at = find(fp, "at")
        origin = (float(at[1]), float(at[2]))
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = next(p[2] for p in find_all(fp, "property") if p[1] == "Reference")
        for pad in find_all(fp, "pad"):
            pad_at = find(pad, "at")
            local = (float(pad_at[1]), float(pad_at[2]))
            angle = float(pad_at[3]) if len(pad_at) > 3 else 0.0
            rx, ry = rotate(local, -rot)  # board y grows downwards
            center = (origin[0] + rx, origin[1] + ry)
            size = find(pad, "size")
            net = find(pad, "net")
            pads.append(Pad(str(ref), str(pad[1]), center,
                            (float(size[1]), float(size[2])), -angle,
                            nets[int(net[1])] if net else "",
                            [str(x) for x in find(pad, "layers")[1:]]))
        for poly in find_all(fp, "fp_poly"):
            if str(find(poly, "layer")[1]) != "F.Cu":
                continue
            for xy in find(poly, "pts")[1:]:
                px, py = float(xy[1]), float(xy[2])
                rx, ry = rotate((px, py), -rot)
                poly_points.append((ref, (origin[0] + rx, origin[1] + ry)))

    for pad in pads:
        want = expected_nets.get((pad.ref, pad.number))
        if want is None:
            fail(f"board: pad {pad.ref}.{pad.number} has no counterpart in the schematic")
        elif pad.net != want:
            fail(f"board: pad {pad.ref}.{pad.number} is on net {pad.net!r}, expected {want!r}")

    vias = [((float(find(v, "at")[1]), float(find(v, "at")[2])),
             float(find(v, "size")[1]), nets[int(find(v, "net")[1])])
            for v in find_all(pcb, "via")]
    segments = []
    for seg in find_all(pcb, "segment"):
        a = (float(find(seg, "start")[1]), float(find(seg, "start")[2]))
        b = (float(find(seg, "end")[1]), float(find(seg, "end")[2]))
        segments.append((a, b, float(find(seg, "width")[1]),
                         nets[int(find(seg, "net")[1])], str(find(seg, "layer")[1])))

    # every track end must land on a pad or on another track of the same net
    for a, b, _w, net, layer in segments:
        for end in (a, b):
            on_pad = any(p.contains(end) and p.net == net and layer in p.copper_layers()
                         for p in pads)
            on_track = any(other_net == net and on_segment(end, oa, ob)
                           for oa, ob, _ow, other_net, _ol in segments
                           if (oa, ob) != (a, b))
            on_via = any(via_net == net
                         and math.hypot(end[0] - vp[0], end[1] - vp[1]) <= vsize / 2 + EPS
                         for vp, vsize, via_net in vias)
            if not (on_pad or on_track or on_via):
                fail(f"board: track end {q(end)} on net {net} connects to nothing")

    # copper of one net must keep its distance from pads of another net
    for a, b, width, net, layer in segments:
        for pad in pads:
            if pad.net == net or layer not in pad.copper_layers():
                continue
            gap = pad.distance_to_segment(a, b) - width / 2
            if gap < MIN_CLEARANCE:
                fail(f"board: track {q(a)}-{q(b)} ({net}) is {gap:.3f} mm from "
                     f"pad {pad.ref}.{pad.number} ({pad.net})")
    for pos, size, net in vias:
        for pad in pads:
            if pad.net == net:
                continue
            gap = pad.distance(pos) - size / 2
            if gap < MIN_CLEARANCE:
                fail(f"board: via {q(pos)} ({net}) is {gap:.3f} mm from "
                     f"pad {pad.ref}.{pad.number} ({pad.net})")
        for a, b, width, seg_net, _layer in segments:
            if seg_net == net:
                continue
            gap = min(math.hypot(pos[0] - (a[0] + (b[0] - a[0]) * i / 200),
                                 pos[1] - (a[1] + (b[1] - a[1]) * i / 200))
                      for i in range(201)) - size / 2 - width / 2
            if gap < MIN_CLEARANCE:
                fail(f"board: via {q(pos)} ({net}) is {gap:.3f} mm from a {seg_net} track")

    # nothing but the antenna may live above the ground plane edge
    for a, b, _w, net, _layer in segments:
        for end in (a, b):
            if end[1] < gnd_edge_y - EPS and net != "ANT_FEED":
                fail(f"board: {net} track reaches {q(end)}, inside the antenna keep-out")
    for pos, _size, _net in vias:
        if pos[1] < gnd_edge_y - EPS:
            fail(f"board: via {q(pos)} sits inside the antenna keep-out")
    for zone in find_all(pcb, "zone"):
        if find(zone, "keepout"):
            continue
        ys = [float(xy[2]) for xy in find(find(zone, "polygon"), "pts")[1:]]
        if min(ys) < gnd_edge_y - EPS:
            fail(f"board: copper zone {find(zone, 'name')[1]} crosses the keep-out edge")

    intruding = [(ref, pt) for ref, pt in poly_points if pt[1] > gnd_edge_y + EPS]
    covered = [(ref, pt) for ref, pt in intruding
               if any(p.ref == ref and p.contains(pt) for p in pads)]
    if len(intruding) != len(covered):
        fail("board: antenna copper reaches into the ground plane outside its own pads")
    notes.append(f"board: {len(pads)} pads, {len(segments)} tracks, {len(vias)} vias, "
                 f"clearances >= {MIN_CLEARANCE} mm, keep-out above y = {gnd_edge_y} clean")
    notes.append(f"board: {len(intruding)} antenna polygon vertices overlap the plane edge, "
                 "all of them inside the antenna's own pads")


def point_in_polygon(pt, polygon) -> bool:
    x, y = pt
    inside = False
    for i in range(len(polygon)):
        (x0, y0), (x1, y1) = polygon[i - 1], polygon[i]
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) / (y1 - y0) * (x1 - x0):
            inside = not inside
    return inside


def check_reference_plane():
    """A microstrip needs its plane: every bit of the feed line, and the port
    pad the RF simulator launches from, must sit over a ground pour on the
    opposite layer.  The pour is stored unfilled - KiCad fills it on B - so
    this checks the zone outline, which is what the design actually promises."""
    pcb = parse((PRJ_DIR / f"{PROJECT}.kicad_pcb").read_text())
    nets = {int(n[1]): str(n[2]) for n in find_all(pcb, "net")}
    planes, unfilled = [], 0
    for zone in find_all(pcb, "zone"):
        if find(zone, "keepout"):
            continue
        layers = find(zone, "layer") or find(zone, "layers")
        names = [str(x) for x in layers[1:]]
        polygon = [(float(xy[1]), float(xy[2]))
                   for xy in find(find(zone, "polygon"), "pts")[1:]]
        if not find(zone, "filled_polygon"):
            unfilled += 1
        if nets[int(find(zone, "net")[1])] == "GND":
            planes.append((names, polygon))

    feed_points = []
    for seg in find_all(pcb, "segment"):
        if str(find(seg, "layer")[1]) != "F.Cu":
            continue
        net = nets[int(find(seg, "net")[1])]
        if net == "GND":
            continue
        for end in ("start", "end"):
            node = find(seg, end)
            feed_points.append((net, (float(node[1]), float(node[2]))))
    for net, pt in feed_points:
        over_plane = any("B.Cu" in names and point_in_polygon(pt, polygon)
                         for names, polygon in planes)
        if not over_plane:
            fail(f"board: the {net} line reaches {q(pt)}, which has no B.Cu ground "
                 "pour over it - a microstrip there has no return path")
    notes.append(f"board: all {len(feed_points)} feed line ends sit over the B.Cu "
                 "ground pour (reference plane present)")
    if unfilled:
        notes.append(f"board: {unfilled} copper zones carry no fill yet - press B in "
                     "the PCB editor before running DRC or an RF simulation, or "
                     "tools that look for the reference layer will find it empty")

def check_exact_copy():
    """The antenna on the board must be an exact copy of SWRA117D Table 1.

    The note is explicit that this is not a nicety: "Small changes of the
    antenna dimensions may have large impact on the performance. Therefore it
    is strongly recommended to make an exact copy of the reference design."
    So a scaled or redrawn radiator has to fail here rather than pass quietly.
    """
    from verify_against_swra117d import TABLE_1, TOL, measure

    pcb = parse((PRJ_DIR / f"{PROJECT}.kicad_pcb").read_text())
    name = None
    for fp in find_all(pcb, "footprint"):
        if find(fp, "fp_poly") is not None:
            name = str(fp[1]).split(":", 1)[-1]
    if name is None:
        fail("board: no antenna footprint on the board")
        return
    path = PRJ_DIR / "library" / "SWRA117D_RF.pretty" / f"{name}.kicad_mod"
    try:
        got, _info = measure(path)
    except SystemExit as exc:
        fail(f"board: {name} does not have the reference geometry ({exc})")
        return
    off = {k: got[k] - v for k, v in TABLE_1.items() if abs(got[k] - v) > TOL}
    if off:
        worst = max(off.items(), key=lambda kv: abs(kv[1]))
        fail(f"board: {name} is not an exact copy of SWRA117D Table 1 - "
             f"{len(off)} dimension(s) differ, worst {worst[0]} by "
             f"{worst[1] * 1000:+.0f} um")
    else:
        notes.append(f"board: {name} matches all {len(TABLE_1)} dimensions of "
                     f"SWRA117D Table 1 within {TOL * 1000:.0f} um (exact copy)")


def check_feed_width():
    """The port pad and the feed line must be the same width.

    The feed width is derived from the stackup, so changing the stackup moves
    it - and the connector footprint does not follow automatically.  This is
    the guard that says so instead of letting a 50 ohm line run into a pad
    built for a different board.
    """
    pcb = parse((PRJ_DIR / f"{PROJECT}.kicad_pcb").read_text())
    nets = {int(n[1]): str(n[2]) for n in find_all(pcb, "net")}
    widths = {float(find(s, "width")[1]) for s in find_all(pcb, "segment")
              if nets[int(find(s, "net")[1])] != "GND"}
    if not widths:
        return
    line = max(widths)
    port = None
    for fp in find_all(pcb, "footprint"):
        if find(fp, "fp_poly") is not None:
            continue                      # the antenna: its feed pad is the neck, not the port
        for pad in find_all(fp, "pad"):
            net = find(pad, "net")
            layers = [str(x) for x in find(pad, "layers")[1:]]
            if net and nets[int(net[1])] not in ("", "GND") and "F.Cu" in layers:
                size = find(pad, "size")
                port = min(float(size[1]), float(size[2]))
    if port is None:
        return
    if abs(port - line) > 0.2:
        fail(f"board: the feed line is {line} mm wide but the port pad is {port} mm - "
             "the stackup changed and the connector footprint did not follow")
    else:
        notes.append(f"board: feed line {line} mm matches the {port} mm port pad, "
                     "and the width is derived from the stackup")


def check_pour_islands():
    """Every island of copper pour must contain a stitching via.

    A pour keep-away rule area can cut a pour into pieces, and a piece with no
    via is a floating patch of copper: it resonates, couples, and radiates,
    and nothing in KiCad complains about it.
    """
    pcb = parse((PRJ_DIR / f"{PROJECT}.kicad_pcb").read_text())
    nets = {int(n[1]): str(n[2]) for n in find_all(pcb, "net")}
    vias = [((float(find(v, "at")[1]), float(find(v, "at")[2])),
             [str(x) for x in find(v, "layers")[1:]])
            for v in find_all(pcb, "via")
            if nets[int(find(v, "net")[1])] == "GND"]

    pours, cuts = [], []
    for zone in find_all(pcb, "zone"):
        layers = [str(x) for x in (find(zone, "layer") or find(zone, "layers"))[1:]]
        pts = [(float(xy[1]), float(xy[2]))
               for xy in find(find(zone, "polygon"), "pts")[1:]]
        box = (min(p[0] for p in pts), min(p[1] for p in pts),
               max(p[0] for p in pts), max(p[1] for p in pts))
        keepout = find(zone, "keepout")
        if keepout is not None:
            if str(find(keepout, "copperpour")[1]) == "not_allowed":
                cuts.append((layers, box))
        elif nets[int(find(zone, "net")[1])] == "GND":
            pours.append((layers, box))

    total = 0
    for layers, box in pours:
        layer = layers[0]
        mine = [b for ls, b in cuts if layer in ls]
        xs = sorted({box[0], box[2]}
                    | {v for c in mine for v in (c[0], c[2]) if box[0] < v < box[2]})
        ys = sorted({box[1], box[3]}
                    | {v for c in mine for v in (c[1], c[3]) if box[1] < v < box[3]})
        cells = [(xs[i], ys[j], xs[i + 1], ys[j + 1])
                 for i in range(len(xs) - 1) for j in range(len(ys) - 1)
                 if not any(c[0] <= (xs[i] + xs[i + 1]) / 2 <= c[2]
                            and c[1] <= (ys[j] + ys[j + 1]) / 2 <= c[3] for c in mine)]
        groups = []
        for cell in cells:
            touching = [g for g in groups if any(
                not (cell[2] < o[0] - EPS or o[2] < cell[0] - EPS
                     or cell[3] < o[1] - EPS or o[3] < cell[1] - EPS) for o in g)]
            groups = [g for g in groups if g not in touching] + \
                     [[cell] + [c for g in touching for c in g]]
        for group in groups:
            x0, y0 = min(c[0] for c in group), min(c[1] for c in group)
            x1, y1 = max(c[2] for c in group), max(c[3] for c in group)
            stitched = [pos for pos, ls in vias
                        if layer in ls and x0 <= pos[0] <= x1 and y0 <= pos[1] <= y1]
            if not stitched:
                fail(f"board: the {layer} pour island at x {x0:.1f}..{x1:.1f}, "
                     f"y {y0:.1f}..{y1:.1f} has no stitching via - it would float")
            total += 1
    notes.append(f"board: all {total} pour islands across {len(pours)} layers carry "
                 "stitching vias (top and bottom ground tied together everywhere)")


def check_launch_and_radiator():
    """Two things an RF simulator needs that a netlist check cannot see.

    1. The port pad needs copper on the reference layer directly beneath it.
       A zone outline is a promise; only a pad or a fill is copper in the
       file, so the SMA footprint carries a solid B.Cu ground pad under the
       launch and this check keeps it there.
    2. An inverted-F is fed at one point and shorted to ground at another, so
       its radiator must be one piece of copper touching pad 1 and pad 2.
       That DC short is the antenna working, not a fault - and it is why a
       circuit level extraction of this board reports VSWR -> infinity.
    """
    pcb = parse((PRJ_DIR / f"{PROJECT}.kicad_pcb").read_text())
    nets = {int(n[1]): str(n[2]) for n in find_all(pcb, "net")}

    launch = ground = None
    radiator = pads = None
    for fp in find_all(pcb, "footprint"):
        ref = next(p[2] for p in find_all(fp, "property") if p[1] == "Reference")
        at = find(fp, "at")
        origin = (float(at[1]), float(at[2]))
        rot = float(at[3]) if len(at) > 3 else 0.0
        for pad in find_all(fp, "pad"):
            pad_at = find(pad, "at")
            rx, ry = rotate((float(pad_at[1]), float(pad_at[2])), -rot)
            centre = (origin[0] + rx, origin[1] + ry)
            size = find(pad, "size")
            box = (centre, (float(size[1]), float(size[2])))
            layers = [str(x) for x in find(pad, "layers")[1:]]
            net = nets[int(find(pad, "net")[1])] if find(pad, "net") else ""
            if "F.Cu" in layers and net not in ("", "GND"):
                launch = launch or box
            if "B.Cu" in layers and net == "GND":
                ground = ground or box
        poly = find(fp, "fp_poly")
        if poly is not None:
            radiator = [(origin[0] + rotate((float(xy[1]), float(xy[2])), -rot)[0],
                         origin[1] + rotate((float(xy[1]), float(xy[2])), -rot)[1])
                        for xy in find(poly, "pts")[1:]]
            pads = {str(pad[1]): (origin[0] + rotate((float(find(pad, "at")[1]),
                                                     float(find(pad, "at")[2])), -rot)[0],
                                  origin[1] + rotate((float(find(pad, "at")[1]),
                                                      float(find(pad, "at")[2])), -rot)[1])
                    for pad in find_all(fp, "pad")}

    if launch is None or ground is None:
        fail("board: no port pad / bottom side ground pad pair found at the launch")
    else:
        (lx, ly), (lw, lh) = launch
        (gx, gy), (gw, gh) = ground
        covered = (abs(lx - gx) * 2 <= gw - lw + 1e-6
                   and abs(ly - gy) * 2 <= gh - lh + 1e-6)
        if not covered:
            fail(f"board: the port pad at {q((lx, ly))} is not fully over the "
                 "bottom side ground pad, so the launch has no reference copper "
                 "unless the zones happen to be filled")
        else:
            notes.append(f"board: port pad {lw} x {lh} mm sits inside a {gw} x {gh} mm "
                         "B.Cu ground pad, so the launch is referenced without a zone fill")

    if radiator and pads:
        # probe just off each pad centre: pad 2's centre falls in its drill barrel,
        # which the polygon punches out with a keyhole
        touching = {}
        for number, centre in pads.items():
            touching[number] = any(
                point_in_polygon((centre[0] + dx, centre[1] + dy), radiator)
                for dx, dy in ((0, 0), (0.2, 0), (-0.2, 0), (0, 0.2), (0, -0.2)))
        if not all(touching.values()):
            fail(f"board: the radiator does not reach every antenna pad ({touching}) - "
                 "an inverted-F must be fed at pad 1 and shorted to ground at pad 2")
        else:
            notes.append("board: the radiator is one piece of copper touching both "
                         "antenna pads (inverted-F short: the port is a DC short to GND)")

def library_symbols():
    lib = parse((PRJ_DIR / "library" / "SWRA117D_RF.kicad_sym").read_text())
    return {str(s[1]): s for s in find_all(lib, "symbol")}


def check_libraries():
    symbols = library_symbols()
    if "ANT_SWRA117D_2G4_Left" not in symbols:
        fail("library: the antenna symbol is missing")
    footprints = sorted((PRJ_DIR / "library" / "SWRA117D_RF.pretty").glob("*.kicad_mod"))
    for fp in footprints:
        if parse(fp.read_text())[0] != "footprint":
            fail(f"library: {fp.name} is not in the modern footprint format")
    notes.append(f"library: {len(symbols)} symbols, {len(footprints)} footprints "
                 "parse cleanly")


def check_embedded_symbols():
    """KiCad reports lib_symbol_mismatch when a schematic's embedded copy of a
    symbol differs from the library it came from, so every embedded symbol has
    to resolve to this project's library and be identical to it."""
    sch = parse((PRJ_DIR / f"{PROJECT}.kicad_sch").read_text())
    lib = library_symbols()
    embedded = find_all(find(sch, "lib_symbols"), "symbol")
    for sym in embedded:
        lib_id = str(sym[1])
        nickname, _, name = lib_id.partition(":")
        if nickname != "SWRA117D_RF":
            fail(f"schematic: {lib_id} comes from an external library, so KiCad "
                 "will compare it against whatever version is installed")
            continue
        if name not in lib:
            fail(f"schematic: {lib_id} is not in library/SWRA117D_RF.kicad_sym")
            continue
        expected = [lib[name][0], lib_id] + lib[name][2:]
        if sym != expected:
            fail(f"schematic: embedded copy of {lib_id} differs from the library")
    notes.append(f"schematic: {len(embedded)} embedded symbols all match "
                 "library/SWRA117D_RF.kicad_sym (no lib_symbol_mismatch)")


def main() -> int:
    expected = {
        ("J1", "1"): "ANT_FEED", ("J1", "2"): "GND",
        ("AE1", "1"): "ANT_FEED", ("AE1", "2"): "GND",
    }
    check_libraries()
    check_embedded_symbols()
    check_schematic(expected)
    check_board(expected)
    check_reference_plane()
    check_launch_and_radiator()
    check_pour_islands()
    check_feed_width()
    check_exact_copy()
    for note in notes:
        print(f"ok   {note}")
    for err in errors:
        print(f"FAIL {err}")
    print(f"\n{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
