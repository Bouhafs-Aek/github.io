#!/usr/bin/env python3
"""Check every board in the antenna evaluation kit.

Almost nothing about these boards is written down twice - the outline, the
plane, where the antenna sits, where the connector goes and where the
schematic symbol is placed are all derived from the footprints and symbols at
generation time.  That is what keeps the six boards consistent, and it is also
why they need checking: a derivation that is wrong is wrong six times.

Everything here is read back out of the written files, never from the
generator, so the checks fail if a derivation drifts.

    python3 kicad/tools/check_kit.py
"""

from __future__ import annotations

import collections
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_kit as kit  # noqa: E402
from check_dn024 import DSU, on_segment, point_to_segment, q, rotate, seg_distance  # noqa: E402
from sexpr import find, find_all, find_deep, parse  # noqa: E402

PRJ_DIR = pathlib.Path(__file__).resolve().parent.parent
MIN_CLEARANCE = 0.15
SIDE_CLEAR = 5.0            # SWRA228C 3.1: 5 mm clear either side of the antenna

problems: list[str] = []
notes: list[str] = []


def fail(msg):
    problems.append(msg)


def ok(msg):
    notes.append(msg)


def board_data(path):
    pcb = parse(path.read_text())
    nets = {str(n[1]): str(n[2]) for n in find_all(pcb, "net")}
    pads, footprints = [], {}
    for fp in find_all(pcb, "footprint"):
        ref = next((str(p[2]) for p in find_all(fp, "property")
                    if str(p[1]) == "Reference"), "?")
        at = find(fp, "at")
        ox, oy = float(at[1]), float(at[2])
        rot = float(at[3]) if len(at) > 3 else 0.0
        footprints[ref] = dict(name=str(fp[1]), at=(ox, oy), rot=rot, node=fp)
        for pad in find_all(fp, "pad"):
            pat, size = find(pad, "at"), find(pad, "size")
            rx, ry = rotate((float(pat[1]), float(pat[2])), -rot)
            w, h = float(size[1]), float(size[2])
            if abs(rot) in (90.0, 270.0):
                w, h = h, w
            net = find(pad, "net")
            pads.append(dict(ref=ref, num=str(pad[1]), kind=str(pad[2]),
                             centre=(ox + rx, oy + ry), w=w, h=h,
                             net=str(net[2]) if net else "",
                             layers=[str(x) for x in find(pad, "layers")[1:]]))
    segs = []
    for sg in find_all(pcb, "segment"):
        a, b = find(sg, "start"), find(sg, "end")
        segs.append(((float(a[1]), float(a[2])), (float(b[1]), float(b[2])),
                     float(find(sg, "width")[1]),
                     nets.get(str(find(sg, "net")[1]), "?")))
    vias = [(float(find(v, "at")[1]), float(find(v, "at")[2]),
             float(find(v, "size")[1])) for v in find_all(pcb, "via")]
    edges = [((float(find(g, "start")[1]), float(find(g, "start")[2])),
              (float(find(g, "end")[1]), float(find(g, "end")[2])))
             for g in find_all(pcb, "gr_line")
             if str(find(g, "layer")[1]) == "Edge.Cuts"]
    zones = []
    for z in find_all(pcb, "zone"):
        pts = [(float(p[1]), float(p[2]))
               for p in find(find(z, "polygon"), "pts")[1:]]
        name = find(z, "name")
        zones.append(dict(name=str(name[1]) if name else "",
                          keepout=find(z, "keepout") is not None,
                          layers=[str(x) for x in (find(z, "layers") or
                                                   find(z, "layer"))[1:]],
                          pts=pts))
    return dict(pcb=pcb, nets=nets, pads=pads, fps=footprints, segs=segs,
                vias=vias, edges=edges, zones=zones)


def rect_seg_gap(pad, a, b) -> float:
    """Distance from a segment's centre line to a pad, as a rectangle.

    Treating a pad as a circle of its longest half-dimension is conservative
    for a square land and badly wrong for a long one: it reads a track that
    passes the short way as if it drove straight through.  Pads here are
    axis aligned once rotation has been folded into w and h, so the exact
    distance is cheap.
    """
    x0, x1 = pad["centre"][0] - pad["w"] / 2, pad["centre"][0] + pad["w"] / 2
    y0, y1 = pad["centre"][1] - pad["h"] / 2, pad["centre"][1] + pad["h"] / 2
    best = float("inf")
    for i in range(201):
        t = i / 200
        px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        best = min(best, math.hypot(max(x0 - px, 0, px - x1),
                                    max(y0 - py, 0, py - y1)))
    return best


def footprint_copper(d, ref):
    """Bounding box of one placed footprint's copper, in board coordinates."""
    fp = d["fps"][ref]
    ox, oy = fp["at"]
    rot = fp["rot"]
    xs, ys = [], []
    for poly in find_all(fp["node"], "fp_poly"):
        if str(find(poly, "layer")[1]) not in ("F.Cu", "B.Cu"):
            continue
        for xy in find(poly, "pts")[1:]:
            rx, ry = rotate((float(xy[1]), float(xy[2])), -rot)
            xs.append(ox + rx); ys.append(oy + ry)
    for pad in d["pads"]:
        if pad["ref"] != ref:
            continue
        xs += [pad["centre"][0] - pad["w"] / 2, pad["centre"][0] + pad["w"] / 2]
        ys += [pad["centre"][1] - pad["h"] / 2, pad["centre"][1] + pad["h"] / 2]
    return min(xs), min(ys), max(xs), max(ys)


def check_board(s, d):
    key = s["key"]
    x0, y0, x1, y1 = s["board"]
    ex = [p for e in d["edges"] for p in e]
    bx0, by0 = min(p[0] for p in ex), min(p[1] for p in ex)
    bx1, by1 = max(p[0] for p in ex), max(p[1] for p in ex)
    if abs(bx1 - bx0 - s["board_w"]) > 0.01 or abs(by1 - by0 - s["board_h"]) > 0.01:
        fail(f"{key}: outline is {bx1 - bx0:.2f} x {by1 - by0:.2f} mm, "
             f"not the {s['board_w']:g} x {s['board_h']:g} it should be")

    pours = [z for z in d["zones"] if not z["keepout"]]
    layers = {l for z in pours for l in z["layers"]}
    for z in pours:
        zx = [p[0] for p in z["pts"]]
        zy = [p[1] for p in z["pts"]]
        if (abs(max(zx) - min(zx) - s["plane_w"]) > 0.01
                or abs(max(zy) - min(zy) - s["plane_h"]) > 0.01):
            fail(f"{key}: a ground pour is {max(zx) - min(zx):.2f} x "
                 f"{max(zy) - min(zy):.2f} mm, not {s['plane_w']:g} x "
                 f"{s['plane_h']:g}")
    if layers != {"F.Cu", "B.Cu"}:
        fail(f"{key}: ground pours are on {sorted(layers)}, not both layers")
    else:
        ok(f"{key}: board {bx1 - bx0:g} x {by1 - by0:g} mm, ground plane "
           f"{s['plane_w']:g} x {s['plane_h']:g} mm on F.Cu and B.Cu")

    # the antenna: above the plane edge, centred, and with room either side
    ax0, ay0, ax1, ay1 = footprint_copper(d, "AE1")
    overlap = ay1 - s["plane_edge"]
    allowed = max(0.0, -s["antenna"]["origin_above_plane"]) + 0.3
    if overlap > allowed:
        fail(f"{key}: the antenna reaches {overlap:.2f} mm past the plane edge, "
             f"more than the {allowed:.2f} mm its feed is meant to")
    gap_l, gap_r = ax0 - bx0, bx1 - ax1
    if abs(gap_l - gap_r) > 0.02:
        fail(f"{key}: the antenna is not centred - {gap_l:.2f} mm of board on "
             f"the left, {gap_r:.2f} mm on the right")
    elif min(gap_l, gap_r) < SIDE_CLEAR - 1e-6:
        fail(f"{key}: only {min(gap_l, gap_r):.2f} mm of clear board beside the "
             f"antenna; SWRA228C 3.1 asks for {SIDE_CLEAR:g} mm")
    else:
        ok(f"{key}: antenna {ax1 - ax0:.2f} x {ay1 - ay0:.2f} mm, centred, "
           f"{gap_l:.2f} mm clear either side, {s['plane_edge'] - ay0:.2f} mm "
           "of it above the plane edge")

    # no pour above the plane edge, on any layer
    for z in pours:
        if min(p[1] for p in z["pts"]) < s["plane_edge"] - 1e-6:
            fail(f"{key}: a ground pour reaches above the plane edge")
    if not any(z["keepout"] and z["name"] == "ANTENNA_KEEPOUT" for z in d["zones"]):
        fail(f"{key}: no ANTENNA_KEEPOUT rule area")

    # the 50 ohm run really is 50 ohm wide
    widths = {round(w, 3) for _, _, w, net in d["segs"] if net == "RF_IN"}
    if kit.W50 not in widths:
        fail(f"{key}: no track at the 50 ohm width {kit.W50} mm on RF_IN")

    # every track end lands on something
    def lands(pt, width, me):
        for a, b, w, _ in d["segs"]:
            if (a, b, w) == me:
                continue
            if point_to_segment(pt, a, b) <= (w + width) / 2 + 1e-6:
                return True
        for pad in d["pads"]:
            if (abs(pt[0] - pad["centre"][0]) <= pad["w"] / 2 + width / 2
                    and abs(pt[1] - pad["centre"][1]) <= pad["h"] / 2 + width / 2):
                return True
        for vx, vy, vs in d["vias"]:
            if math.dist(pt, (vx, vy)) <= (vs + width) / 2 + 1e-6:
                return True
        return False

    loose = 0
    for a, b, w, net in d["segs"]:
        for pt in (a, b):
            if not lands(pt, w, (a, b, w)):
                loose += 1
                fail(f"{key}: a {net} track end at {q(pt)} lands on nothing")
    # clearances
    worst_t, worst_p = None, None
    for i, (a1, b1, w1, n1) in enumerate(d["segs"]):
        for a2, b2, w2, n2 in d["segs"][i + 1:]:
            if n1 == n2:
                continue
            gap = seg_distance(a1, b1, a2, b2) - w1 / 2 - w2 / 2
            worst_t = gap if worst_t is None else min(worst_t, gap)
            if gap < MIN_CLEARANCE:
                fail(f"{key}: tracks on {n1} and {n2} are {gap:.3f} mm apart")
    for a, b, w, net in d["segs"]:
        for pad in d["pads"]:
            if pad["net"] == net or not set(pad["layers"]) & {"F.Cu", "*.Cu"}:
                continue
            gap = rect_seg_gap(pad, a, b) - w / 2
            worst_p = gap if worst_p is None else min(worst_p, gap)
            if gap < MIN_CLEARANCE:
                fail(f"{key}: a {net} track is {gap:.3f} mm from pad "
                     f"{pad['ref']}.{pad['num']} ({pad['net']})")
    if not loose:
        ok(f"{key}: {len(d['pads'])} pads, {len(d['segs'])} tracks, "
           f"{len(d['vias'])} vias, every track end lands, closest "
           f"different-net tracks {worst_t:.2f} mm, closest track to a "
           f"foreign pad {worst_p:.2f} mm")


def inside(poly, pt) -> bool:
    x, y = pt
    hit = False
    for (x1, y1), (x2, y2) in zip(poly, poly[1:] + poly[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) / (y2 - y1) * (x2 - x1):
            hit = not hit
    return hit


def check_launch(s, d):
    """The U.FL launch: lands on the pad, necks to fit it, grounded locally.

    None of this is covered by the general rules.  A track and the pad it
    runs to are the same net, so the clearance check skips the pair - which
    means a 2.95 mm line driven straight onto a 1.05 mm pad reads as clean.
    """
    key = s["key"]
    sig = [p for p in d["pads"] if p["ref"] == "J1" and p["num"] == "1"]
    gnds = [p for p in d["pads"] if p["ref"] == "J1" and p["num"] == "2"]
    if len(sig) != 1 or len(gnds) != 2:
        fail(f"{key}: J1 should have one signal pad and two ground pads, "
             f"found {len(sig)} and {len(gnds)}")
        return
    sig = sig[0]

    arriving = [t for t in d["segs"] if t[3] == "RF_IN"
                and any(abs(pt[0] - sig["centre"][0]) <= sig["w"] / 2 + 1e-6
                        and abs(pt[1] - sig["centre"][1]) <= sig["h"] / 2 + 1e-6
                        for pt in (t[0], t[1]))]
    if not arriving:
        fail(f"{key}: no RF_IN track ends inside J1's signal pad - the launch "
             "runs past it, probably to the footprint origin")
        return
    widest = max(t[2] for t in arriving)
    across = min(sig["w"], sig["h"])
    if widest > across + 1e-6:
        fail(f"{key}: the launch reaches J1 pad 1 at {widest:.2f} mm wide on a "
             f"pad only {across:.2f} mm across - it has to taper, not butt on")

    keepaway = next((z for z in d["zones"]
                     if z["name"] == "RF_POUR_KEEPAWAY"), None)
    if keepaway is None:
        fail(f"{key}: no RF_POUR_KEEPAWAY around the feed")
    else:
        stranded = [g for g in gnds if inside(keepaway["pts"], g["centre"])]
        if stranded:
            fail(f"{key}: {len(stranded)} of J1's ground pads sit inside the "
                 "pour keep-away, so the pour never reaches them")
    near = [g for g in gnds
            if any(math.dist(g["centre"], (vx, vy)) < 3.0
                   for vx, vy, _ in d["vias"])]
    if len(near) != 2:
        fail(f"{key}: only {len(near)} of J1's 2 ground pads have a stitching "
             "via within 3 mm - the return current turns round at the launch")
    if s["run_50"] < kit.MIN_RUN_50 - 1e-9:
        fail(f"{key}: only {s['run_50']:.2f} mm of 50 ohm line between the "
             f"network and the launch")
    else:
        ok(f"{key}: launch tapers {kit.W50} -> {widest:g} mm into J1's "
           f"{across:g} mm signal pad, both ground pads on the pour and "
           f"via'd, {s['run_50']:.2f} mm of 50 ohm line behind it")


def check_matching(s, d):
    key = s["key"]
    by = {}
    for pad in d["pads"]:
        if pad["ref"] in ("Z1", "Z2", "Z3"):
            by.setdefault(pad["ref"], {})[pad["num"]] = pad
    for ref in ("Z1", "Z2", "Z3"):
        if ref not in by:
            fail(f"{key}: no {ref} matching site")
            return
    if {by["Z2"]["1"]["net"], by["Z2"]["2"]["net"]} != {"RF_IN", "ANT_FEED"}:
        fail(f"{key}: Z2 is not in series between RF_IN and ANT_FEED")
    for ref, side in (("Z1", "RF_IN"), ("Z3", "ANT_FEED")):
        if by[ref]["2"]["net"] != "GND" or by[ref]["1"]["net"] != side:
            fail(f"{key}: {ref} is not a shunt from {side} to GND")
    grounded = 0
    for ref in ("Z1", "Z3"):
        c = by[ref]["2"]["centre"]
        if any(math.dist(c, (vx, vy)) < 3.0 for vx, vy, _ in d["vias"]):
            grounded += 1
    if grounded != 2:
        fail(f"{key}: only {grounded} of the 2 shunt sites reach the bottom "
             "plane through a via of their own")
    want = dict(s["antenna"]["bom"])
    got = {}
    for fp in find_all(d["pcb"], "footprint"):
        ref = next((str(p[2]) for p in find_all(fp, "property")
                    if str(p[1]) == "Reference"), "")
        if ref in want:
            got[ref] = next(str(p[2]) for p in find_all(fp, "property")
                            if str(p[1]) == "Value")
    if got != want:
        fail(f"{key}: BOM on the board is {got}, the note says {want}")
    else:
        ok(f"{key}: Z2 series, Z1/Z3 shunt, both shunts via'd to the bottom "
           f"plane; Z1={want['Z1']} Z2={want['Z2']} Z3={want['Z3']}")


def check_short(s, d):
    """An inverted-F's shorting leg has to actually reach the plane."""
    key = s["key"]
    pads = [p for p in d["pads"] if p["ref"] == "AE1" and p["num"] == "2"]
    if not pads:
        ok(f"{key}: monopole - one terminal, the plane is the other")
        return
    pad = pads[0]
    if pad["kind"] != "smd":
        ok(f"{key}: the shorting leg is a plated hole, so it lands in the "
           "bottom plane by itself")
        return
    reach = [p for p in (pad["centre"],)]
    for a, b, w, net in d["segs"]:
        if net != "GND":
            continue
        for end, other in ((a, b), (b, a)):
            if any(math.dist(end, r) < w / 2 + 0.6 for r in reach):
                reach.append(other)
    if not any(y > s["plane_edge"] for _, y in reach):
        fail(f"{key}: the shorting leg does not reach past the plane edge, so "
             "it is shorted to nothing - both pours stop at that line")
        return
    deepest = max(y for _, y in reach)
    if not any(math.dist((x, y), (vx, vy)) < 1.0
               for x, y in reach for vx, vy, _ in d["vias"]):
        fail(f"{key}: the shorting leg reaches the plane on F.Cu but never "
             "reaches B.Cu - it needs a via")
    else:
        ok(f"{key}: the shorting leg runs {deepest - s['plane_edge']:.2f} mm "
           "into the plane and vias down to B.Cu")


def check_schematic(s):
    key = s["key"]
    path = kit.OUT_DIR / key / f"{s['project']}.kicad_sch"
    sch = parse(path.read_text())
    libs = {}
    for nick in {s["antenna"]["lib"], "SWRA117D_RF"}:
        libs[nick] = {str(x[1]): x for x in
                      find_all(parse((PRJ_DIR / "library" / f"{nick}.kicad_sym")
                                     .read_text()), "symbol")}
    embedded = find_all(find(sch, "lib_symbols"), "symbol")
    for sym in embedded:
        lib_id = str(sym[1])
        nick, _, name = lib_id.partition(":")
        if nick not in libs or name not in libs[nick]:
            fail(f"{key}: {lib_id} is not in a library this project carries")
        elif sym != [libs[nick][name][0], lib_id] + libs[nick][name][2:]:
            fail(f"{key}: the embedded copy of {lib_id} differs from the library")

    wires = [[(float(p[1]), float(p[2])) for p in find(w, "pts")[1:]]
             for w in find_all(sch, "wire")]
    dsu = DSU()
    for a, b in wires:
        dsu.union(q(a), q(b))
    for label in find_all(sch, "label"):
        at = find(label, "at")
        pos = (float(at[1]), float(at[2]))
        hit = [(a, b) for a, b in wires if on_segment(pos, a, b)]
        if not hit:
            fail(f"{key}: label {label[1]} at {q(pos)} is not on a wire")
        for a, b in hit:
            dsu.union(q(a), f"net:{label[1]}")

    placed = []
    for sym in find_all(sch, "symbol"):
        if find(sym, "lib_id") is None:
            continue
        lib_id = str(find(sym, "lib_id")[1])
        at = find(sym, "at")
        pos = (float(at[1]), float(at[2]))
        rot = float(at[3]) if len(at) > 3 else 0.0
        ref = next(p[2] for p in find_all(sym, "property") if p[1] == "Reference")
        defn = next((x for x in embedded if str(x[1]) == lib_id), None)
        if defn is None:
            fail(f"{key}: {ref} uses {lib_id}, which is not in lib_symbols")
            continue
        for unit in find_all(defn, "symbol"):
            for pin in find_all(unit, "pin"):
                pat = find(pin, "at")
                rx, ry = rotate((float(pat[1]), float(pat[2])), rot)
                placed.append((str(ref), str(find(pin, "number")[1]),
                               (pos[0] + rx, pos[1] - ry), lib_id))
    for ref, number, pos, _ in placed:
        if not [(a, b) for a, b in wires if on_segment(pos, a, b)]:
            fail(f"{key}: pin {ref}.{number} at {q(pos)} touches no wire")
            continue
        for a, b in wires:
            if on_segment(pos, a, b):
                dsu.union(q(a), f"pin:{ref}.{number}")
    for ref, number, _p, lib_id in placed:
        if lib_id.endswith((":GND", ":PWR_FLAG")):
            dsu.union(f"pin:{ref}.{number}", "net:GND")

    want = {("J1", "1"): "RF_IN", ("J1", "2"): "GND",
            ("Z1", "1"): "RF_IN", ("Z1", "2"): "GND",
            ("Z2", "1"): "RF_IN", ("Z2", "2"): "ANT_FEED",
            ("Z3", "1"): "ANT_FEED", ("Z3", "2"): "GND",
            ("AE1", "1"): "ANT_FEED"}
    if s["pin2"] is not None:
        want[("AE1", "2")] = "GND"
    for (ref, number), net in want.items():
        pin = f"pin:{ref}.{number}"
        if pin not in dsu.parent:
            fail(f"{key}: {ref}.{number} is not placed")
        elif dsu.find(pin) != dsu.find(f"net:{net}"):
            fail(f"{key}: {ref}.{number} is not on {net}")
    ok(f"{key}: {len(embedded)} embedded symbols match their libraries, "
       f"{len(placed)} pins on wires, netlist matches the intended one")


def check_uuids(s, d):
    """Two objects sharing one identifier is a bug KiCad will load anyway.

    A library footprint carries its own uuids and the three 0402 sites are
    placed from one file, so this fired the moment it was written: every
    board had nine identifiers used three times over.
    """
    uids = [str(u[1]) for u in find_deep(d["pcb"], "uuid")]
    dupes = [u for u, c in collections.Counter(uids).items() if c > 1]
    if dupes:
        fail(f"{s['key']}: {len(dupes)} uuid(s) used more than once - two "
             "objects on the board share an identifier")
    else:
        ok(f"{s['key']}: {len(uids)} uuids, all distinct")


def check_kit_invariants(specs, data):
    """What makes six boards a kit rather than six boards."""
    commons = [s for s in specs if s["plane_key"] == "common"]
    outlines = {(s["board_w"], s["board_h"]) for s in commons}
    planes = {(s["plane_w"], s["plane_h"]) for s in commons}
    if len(outlines) != 1 or len(planes) != 1:
        fail(f"the common-plane boards differ: outlines {outlines}, "
             f"planes {planes} - they are meant to be the same board with a "
             "different antenna")
    else:
        ok(f"the {len(commons)} common-plane boards share one "
           f"{commons[0]['board_w']:g} x {commons[0]['board_h']:g} mm outline "
           f"and one {commons[0]['plane_w']:g} x {commons[0]['plane_h']:g} mm "
           "plane, so only the antenna differs")
    conns = {d["fps"]["J1"]["name"] for d in data.values()}
    if len(conns) != 1:
        fail(f"the kit uses more than one connector: {conns}")
    thick = set()
    for d in data.values():
        thick.add(float(find(find(d["pcb"], "general"), "thickness")[1]))
    if len(thick) != 1:
        fail(f"the kit mixes board thicknesses: {sorted(thick)}")
    else:
        ok(f"all {len(data)} boards: one connector ({conns.pop()}), one "
           f"stackup ({sorted(thick)[0]:.2f} mm), one 50 ohm width "
           f"({kit.W50} mm) - only the antenna and the plane are variables")


def main() -> int:
    specs = kit.all_specs()
    data = {}
    for s in specs:
        path = kit.OUT_DIR / s["key"] / f"{s['project']}.kicad_pcb"
        if not path.exists():
            print(f"missing {path} - run tools/gen_kit.py")
            return 1
        d = board_data(path)
        data[s["key"]] = d
        check_board(s, d)
        check_launch(s, d)
        check_matching(s, d)
        check_short(s, d)
        check_schematic(s)
        check_uuids(s, d)
    check_kit_invariants(specs, data)
    for n in notes:
        print(f"ok   {n}")
    for p in problems:
        print(f"FAIL {p}")
    print(f"\n{len(problems)} problem(s) across {len(specs)} board(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
