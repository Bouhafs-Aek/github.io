#!/usr/bin/env python3
"""Measure the DN024 footprint against SWRA227E Table 1, dimension by dimension.

The generator builds the polygon from the table; this reads the polygon back
out of the file and re-derives the table from it, without using the generator.
The two agreeing is what makes "exact copy" a checked claim rather than an
assertion - and DN024 is explicit that it has to be one: "To obtain optimum
performance it is important to make an exact copy of the antenna dimensions."

    python3 kicad/tools/verify_against_swra227e.py [footprint.kicad_mod]
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import find, find_all, parse  # noqa: E402

DEFAULT = (pathlib.Path(__file__).resolve().parent.parent / "library"
           / "TI_DN024.pretty" / "TI_DN024_Monopole_868_2440.kicad_mod")
TOL = 0.011      # 11 um, the same tolerance the SWRA117D check uses

TABLE_1 = {"L1": 9.0, "L2": 18.0, "L3": 3.0, "L4": 38.0, "L5": 1.0,
           "W": 2.0, "X2": 25.0}

WHAT = {
    "L1": "feed trace, foot to the top of the bottom arm",
    "L2": "bottom arm, feed trace's far edge to the right end",
    "L3": "gap between meander arms",
    "L4": "top arm, the full width of the antenna",
    "L5": "ground plane edge to the foot of the feed trace",
    "W": "trace width",
    "X2": "ground plane edge to the top of the antenna",
}


def spans(values, tol=1e-6):
    """Collapse a sorted list of coordinates into distinct values."""
    out = []
    for v in sorted(values):
        if not out or abs(v - out[-1]) > tol:
            out.append(v)
    return out


def measure(path: pathlib.Path) -> tuple[dict, dict]:
    fp = parse(path.read_text())
    polys = [p for p in find_all(fp, "fp_poly")]
    layers = sorted({str(find(p, "layer")[1]) for p in polys})
    pts = [(float(xy[1]), float(xy[2])) for xy in find(polys[0], "pts")[1:]]
    xs, ys = spans(p[0] for p in pts), spans(p[1] for p in pts)
    if len(polys) < 2 or layers != ["B.Cu", "F.Cu"]:
        raise SystemExit(f"expected the radiator on F.Cu and B.Cu, found {layers}")
    for other in polys[1:]:
        if find(other, "pts") != find(polys[0], "pts"):
            raise SystemExit("the two copper layers do not carry the same polygon")

    # the radiator's pads are all on net 1: the feed, and the vias that stitch
    # the two layers together.  The feed is the one at the origin.
    all_pads = [p for p in find_all(fp, "pad")]
    feed_pads = [p for p in all_pads
                 if (float(find(p, "at")[1]), float(find(p, "at")[2])) == (0.0, 0.0)]
    if not feed_pads:
        raise SystemExit("no feed pad at the footprint origin")
    pad = feed_pads[0]
    pad_size = find(pad, "size")
    stitches = [p for p in all_pads if p is not pad]
    if not stitches:
        raise SystemExit("the radiator is on two layers but nothing stitches "
                         "them together except the feed")

    # horizontal ladder: the copper's left and right edges, and the feed trace
    left, right = xs[0], xs[-1]
    # the feed trace is the only copper that reaches the bottom edge
    bottom = ys[-1]
    feed_xs = spans(p[0] for p in pts if abs(p[1] - bottom) < 1e-6)

    # vertical ladder: every distinct y above the feed foot is an arm edge, in
    # pairs - each arm contributes its far edge then its near one.  KiCad's y
    # runs down, so the bottom arm's *top* edge is the second from the end.
    arm_edges = [y for y in ys if y < bottom - 1e-6]
    top = ys[0]

    got = {
        "W": feed_xs[1] - feed_xs[0],
        "L4": right - left,
        "L2": right - feed_xs[1],
        "L3": arm_edges[2] - arm_edges[1],
        "L1": bottom - arm_edges[-2],
    }
    # L5 and X2 are measured against the ground plane edge, which the footprint
    # carries as the bottom of its Dwgs.User clear area
    clear = next(r for r in find_all(fp, "fp_rect")
                 if str(find(r, "layer")[1]) == "Dwgs.User")
    plane_edge = max(float(find(clear, "start")[2]), float(find(clear, "end")[2]))
    got["L5"] = plane_edge - bottom
    got["X2"] = plane_edge - top

    pitch = spans(arm_edges)
    arms = (len(pitch)) // 2
    gaps = []
    centres = [(float(find(p, "at")[1]), float(find(p, "at")[2]))
               for p in [pad] + stitches]
    for i, c in enumerate(centres):
        others = [d for j, d in enumerate(centres) if j != i]
        gaps.append(min((c[0] - d[0]) ** 2 + (c[1] - d[1]) ** 2 for d in others) ** 0.5)
    return got, dict(vertices=len(pts), layers=layers, arms=arms,
                     pad=(float(pad_size[1]), float(pad_size[2])),
                     drill=float(find(pad, "drill")[1]),
                     stitches=len(stitches), stitch_pitch=max(gaps),
                     envelope=(right - left, bottom - top))


def main() -> int:
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    got, info = measure(path)
    print(f"{path.name}: {info['vertices']} polygon vertices on "
          f"{' + '.join(info['layers'])}, {info['arms']} meander arms")
    print(f"  copper envelope {info['envelope'][0]:.2f} x {info['envelope'][1]:.2f} mm, "
          f"feed pad {info['pad'][0]} x {info['pad'][1]} mm with a "
          f"{info['drill']} mm plated hole")
    print(f"  {info['stitches']} vias tie the two layers together, no more than "
          f"{info['stitch_pitch']:.2f} mm apart\n")
    print(f"{'dim':4} {'SWRA227E':>10} {'measured':>10} {'error':>8}   what it is")
    bad = 0
    for name, want in TABLE_1.items():
        have = got[name]
        err = have - want
        ok = abs(err) <= TOL
        bad += 0 if ok else 1
        print(f"{name:4} {want:9.2f}  {have:9.3f}  {err:+8.3f} "
              f"{'  ' if ok else ' !'} {WHAT[name]}")
    print()
    if bad:
        print(f"{bad} dimension(s) differ from the published reference by more "
              f"than {TOL * 1000:.0f} um")
    else:
        print(f"all {len(TABLE_1)} dimensions match SWRA227E Table 1 within "
              f"{TOL * 1000:.0f} um: this is an exact copy")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
