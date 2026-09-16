#!/usr/bin/env python3
"""Check the DN024 RFsim board for the things that make a run meaningless.

The two faults this board exists to avoid are both invisible in the PCB
editor and both produce a plausible-looking, entirely wrong S11:

  * a ground plane stored as an unfilled zone, so the solver sees no plane;
  * a series matching land, so the solver sees a 0.40 mm gap where 3.9 pF
    belongs and the antenna is not connected to the port at all.

Everything here is read back out of the written file, never from the
generator, so the checks fail if the board drifts.

    python3 kicad/tools/check_dn024_sim.py
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import parse, find, find_all  # noqa: E402

PRJ_DIR = pathlib.Path(__file__).resolve().parent.parent
PCB_PATH = PRJ_DIR / "sim" / "board" / "dn024_monopole_sim.kicad_pcb"
MIN_CLEARANCE = 0.15
TARGETS = ((868.0, 2.9), (2440.0, 1.2))     # SWRA227E 4.3.1, Z62 = 0 ohm

problems: list[str] = []
notes: list[str] = []


def fail(msg: str) -> None:
    problems.append(msg)


def ok(msg: str) -> None:
    notes.append(msg)


def load(path: pathlib.Path):
    pcb = parse(path.read_text())
    nets = {str(n[1]): str(n[2]) for n in find_all(pcb, "net")}
    pads = []
    for fp in find_all(pcb, "footprint"):
        ref = next((str(p[2]) for p in find_all(fp, "property")
                    if str(p[1]) == "Reference"), "?")
        at = find(fp, "at")
        ox, oy = float(at[1]), float(at[2])
        rot = float(at[3]) if len(at) > 3 else 0.0
        for pad in find_all(fp, "pad"):
            a, sz = find(pad, "at"), find(pad, "size")
            lx, ly = float(a[1]), float(a[2])
            th = math.radians(-rot)
            w, h = float(sz[1]), float(sz[2])
            if abs(rot) in (90.0, 270.0):
                w, h = h, w
            net = find(pad, "net")
            pads.append(dict(
                ref=ref, num=str(pad[1]),
                cx=ox + lx * math.cos(th) - ly * math.sin(th),
                cy=oy + lx * math.sin(th) + ly * math.cos(th),
                w=w, h=h, net=str(net[2]) if net else "",
                layers=[str(x) for x in find(pad, "layers")[1:]]))
    segs = []
    for s in find_all(pcb, "segment"):
        a, b = find(s, "start"), find(s, "end")
        segs.append(((float(a[1]), float(a[2])), (float(b[1]), float(b[2])),
                     float(find(s, "width")[1]),
                     nets.get(str(find(s, "net")[1]), "?")))
    return pcb, nets, pads, segs


def covers(pad, x, y) -> bool:
    return (abs(x - pad["cx"]) <= pad["w"] / 2 + 1e-9
            and abs(y - pad["cy"]) <= pad["h"] / 2 + 1e-9)


def on(pad, layer) -> bool:
    return layer in pad["layers"] or "*.Cu" in pad["layers"]


def rect_seg_gap(pad, a, b, width) -> float:
    x0, x1 = pad["cx"] - pad["w"] / 2, pad["cx"] + pad["w"] / 2
    y0, y1 = pad["cy"] - pad["h"] / 2, pad["cy"] + pad["h"] / 2
    best = float("inf")
    for i in range(201):
        t = i / 200
        px, py = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
        dx, dy = max(x0 - px, 0, px - x1), max(y0 - py, 0, py - y1)
        best = min(best, math.hypot(dx, dy))
    return best - width / 2


def check_no_pours(pcb) -> None:
    """A copper pour here would be a fill step someone can forget."""
    pours = [z for z in find_all(pcb, "zone") if not find(z, "keepout")]
    if pours:
        fail(f"board: {len(pours)} copper pour(s) - this board must carry none. "
             "KiCad writes zones unfilled, a solver reads the file, and an "
             "unfilled pour is not a ground plane")
    else:
        ok("board: no copper pours, so there is no fill step to forget - "
           "the ground plane is pads, which are solid copper in the file")


def check_ground_plane(pads) -> None:
    """The plane is the monopole's other half. It has to be real, on B.Cu."""
    gnd = [p for p in pads if p["net"] == "GND" and p["w"] * p["h"] > 100]
    b = [p for p in gnd if on(p, "B.Cu")]
    f = [p for p in gnd if on(p, "F.Cu")]
    if not b:
        fail("board: no solid B.Cu ground copper - a monopole radiates "
             "against its plane, and without one there is nothing to resonate")
        return
    area_b = sum(p["w"] * p["h"] for p in b)
    x0 = min(p["cx"] - p["w"] / 2 for p in b)
    x1 = max(p["cx"] + p["w"] / 2 for p in b)
    y0 = min(p["cy"] - p["h"] / 2 for p in b)
    y1 = max(p["cy"] + p["h"] / 2 for p in b)
    if abs((x1 - x0) - 43.0) > 0.01 or abs((y1 - y0) - 63.0) > 0.01:
        fail(f"board: B.Cu ground is {x1 - x0:.2f} x {y1 - y0:.2f} mm, not the "
             "43 x 63 mm plane SWRA227E Table 3 measured the match on")
    else:
        ok(f"board: ground plane {x1 - x0:.1f} x {y1 - y0:.1f} mm as "
           f"{len(b)} B.Cu pad(s) ({area_b:.0f} mm2) and {len(f)} F.Cu pad(s), "
           "the size SWRA227E Table 3 measured the match on")


def check_port(pads) -> None:
    """RFsim attaches ports to pads and needs reference copper under them."""
    port = [p for p in pads if p["ref"] == "P1" and p["num"] == "1"]
    if len(port) != 1:
        fail(f"board: expected exactly one P1 pad 1 to drive, found {len(port)}")
        return
    port = port[0]
    if not on(port, "F.Cu"):
        fail("board: the port pad is not on F.Cu")
    under = [p for p in pads if p["net"] == "GND" and on(p, "B.Cu")
             and covers(p, port["cx"], port["cy"])]
    if not under:
        fail("board: no B.Cu copper under the port pad - this is the error "
             "RFsim reports as 'no copper on reference layer B.Cu under the pad'")
    else:
        ok(f"board: port pad {port['w']} x {port['h']} mm at "
           f"({port['cx']:.1f}, {port['cy']:.1f}) with solid B.Cu directly "
           "under it - attach RFsim port 1 here, as MSL")


def check_feed_is_continuous(nets, pads, segs) -> None:
    """The whole point: no series land, so no gap where 3.9 pF belongs."""
    if "RF_IN" in nets.values():
        fail("board: an RF_IN net exists, so the feed is still split by a "
             "series matching land. A solver meshes copper: that land is a "
             "0.40 mm gap, not 3.9 pF, and the antenna is left unconnected")
        return
    signal = [n for n in nets.values() if n not in ("", "GND")]
    if signal != ["ANT_FEED"]:
        fail(f"board: expected one signal net, found {signal}")
        return
    port = next(p for p in pads if p["ref"] == "P1" and p["num"] == "1")
    ant = [p for p in pads if p["ref"] == "AE1" and p["net"] == "ANT_FEED"]
    if not ant:
        fail("board: the antenna has no ANT_FEED pad")
        return
    # walk the ANT_FEED copper from the port and see whether it reaches AE1
    reach = [(port["cx"], port["cy"])]
    feed = [s for s in segs if s[3] == "ANT_FEED"]
    changed = True
    while changed:
        changed = False
        for a, b, w, _ in feed:
            for end, other in ((a, b), (b, a)):
                if any(math.dist(end, r) < w / 2 + 0.05 for r in reach):
                    if not any(math.dist(other, r) < 1e-6 for r in reach):
                        reach.append(other)
                        changed = True
    if not any(any(covers(p, x, y) for x, y in reach) for p in ant):
        fail("board: the ANT_FEED copper does not run from the port pad to "
             "the antenna - there is a break in the feed")
    else:
        ok(f"board: one continuous ANT_FEED run of {len(feed)} tracks from the "
           "port pad to the antenna, with copper where the fabrication board "
           "puts Z62 - this is SWRA227E 4.3.1's 'Z62: 0 ohm' case")


def check_clearance(pads, segs) -> None:
    worst = (float("inf"), "")
    for pad in pads:
        if pad["net"] != "GND" or not on(pad, "F.Cu"):
            continue
        for a, b, w, net in segs:
            if net == "GND":
                continue
            gap = rect_seg_gap(pad, a, b, w)
            if gap < worst[0]:
                worst = (gap, f"{pad['ref']}.{pad['num']} vs a {net} track")
    if worst[0] < MIN_CLEARANCE:
        fail(f"board: ground copper is {worst[0]:.3f} mm from a signal track "
             f"({worst[1]}), under the {MIN_CLEARANCE} mm rule")
    else:
        ok(f"board: closest ground copper to a signal track {worst[0]:.2f} mm "
           f"({worst[1]})")


def check_expectations() -> None:
    """A run you cannot check against a number is not a result."""
    for freq, swr in TARGETS:
        db = 20 * math.log10(abs((swr - 1) / (swr + 1)))
        ok(f"expect: {freq:6.0f} MHz  SWR {swr}  ->  S11 = {db:5.1f} dB  "
           "(SWRA227E 4.3.1, measured with Z62 = 0 ohm)")
    ok("expect: NOT Figure 13's matched bands - those include the 3.9 pF, "
       "and no copper-only model can produce them")


def main() -> int:
    if not PCB_PATH.exists():
        print(f"missing {PCB_PATH} - run tools/gen_dn024_sim_board.py")
        return 1
    pcb, nets, pads, segs = load(PCB_PATH)
    check_no_pours(pcb)
    check_ground_plane(pads)
    check_port(pads)
    check_feed_is_continuous(nets, pads, segs)
    check_clearance(pads, segs)
    check_expectations()
    for note in notes:
        print(f"ok   {note}")
    for problem in problems:
        print(f"FAIL {problem}")
    print(f"\n{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
