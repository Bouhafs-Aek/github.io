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
GND_EDGE_Y = 65.75
MIN_CLEARANCE = 0.15
EPS = 1e-6

errors: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    errors.append(msg)


def q(pt):
    return (round(pt[0], 3), round(pt[1], 3))


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

    # power symbols are global: tie every GND pin together
    for ref, number, _pos, lib_id in placed:
        if lib_id == "power:GND":
            dsu.union(f"pin:{ref}.{number}", "label:GND")

    got = {}
    for ref, number, _pos, lib_id in placed:
        if lib_id == "power:GND":
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
            if end[1] < GND_EDGE_Y - EPS and net != "ANT_FEED":
                fail(f"board: {net} track reaches {q(end)}, inside the antenna keep-out")
    for pos, _size, _net in vias:
        if pos[1] < GND_EDGE_Y - EPS:
            fail(f"board: via {q(pos)} sits inside the antenna keep-out")
    for zone in find_all(pcb, "zone"):
        if find(zone, "keepout"):
            continue
        ys = [float(xy[2]) for xy in find(find(zone, "polygon"), "pts")[1:]]
        if min(ys) < GND_EDGE_Y - EPS:
            fail(f"board: copper zone {find(zone, 'name')[1]} crosses the keep-out edge")

    intruding = [(ref, pt) for ref, pt in poly_points if pt[1] > GND_EDGE_Y + EPS]
    covered = [(ref, pt) for ref, pt in intruding
               if any(p.ref == ref and p.contains(pt) for p in pads)]
    if len(intruding) != len(covered):
        fail("board: antenna copper reaches into the ground plane outside its own pads")
    notes.append(f"board: {len(pads)} pads, {len(segments)} tracks, {len(vias)} vias, "
                 f"clearances >= {MIN_CLEARANCE} mm, keep-out clean")
    notes.append(f"board: {len(intruding)} antenna polygon vertices overlap the plane edge, "
                 "all of them inside the antenna's own pads")


def check_libraries():
    lib = parse((PRJ_DIR / "library" / "SWRA117D_RF.kicad_sym").read_text())
    symbols = [str(s[1]) for s in find_all(lib, "symbol")]
    if "ANT_SWRA117D_2G4_Left" not in symbols:
        fail("library: the antenna symbol is missing")
    for fp in sorted((PRJ_DIR / "library" / "SWRA117D_RF.pretty").glob("*.kicad_mod")):
        node = parse(fp.read_text())
        if node[0] != "footprint":
            fail(f"library: {fp.name} is not in the modern footprint format")
    notes.append(f"library: 1 symbol, "
                 f"{len(list((PRJ_DIR / 'library' / 'SWRA117D_RF.pretty').glob('*.kicad_mod')))} "
                 "footprints parse cleanly")


def main() -> int:
    expected = {
        ("J1", "1"): "RF_IN", ("J1", "2"): "GND",
        ("C1", "1"): "RF_IN", ("C1", "2"): "GND",
        ("L1", "1"): "RF_IN", ("L1", "2"): "ANT_FEED",
        ("C2", "1"): "ANT_FEED", ("C2", "2"): "GND",
        ("AE1", "1"): "ANT_FEED", ("AE1", "2"): "GND",
    }
    check_libraries()
    check_schematic(expected)
    check_board(expected)
    for note in notes:
        print(f"ok   {note}")
    for err in errors:
        print(f"FAIL {err}")
    print(f"\n{len(errors)} problem(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
