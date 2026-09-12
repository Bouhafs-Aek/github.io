#!/usr/bin/env python3
"""Check the antenna footprint against Table 1 of TI SWRA117D (AN043).

The note is unusually blunt about why this matters:

    "Small changes of the antenna dimensions may have large impact on the
     performance. Therefore it is strongly recommended to make an exact copy
     of the reference design to achieve optimum performance."

So the implementation is worth proving, not assuming. Every dimension below is
measured out of the footprint polygon and compared with the published value.
The library footprint is the left-handed variant, mirrored about x relative to
Figure 3, which this accounts for.

    python3 verify_against_swra117d.py [footprint.kicad_mod]
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import find, find_all, parse  # noqa: E402

DEFAULT = (pathlib.Path(__file__).resolve().parent.parent / "library"
           / "SWRA117D_RF.pretty" / "Texas_SWRA117D_2.4GHz_Left.kicad_mod")

# SWRA117D Table 1, in mm
TABLE_1 = {
    "L1": 3.94, "L2": 2.70, "L3": 5.00, "L4": 2.64, "L5": 2.00, "L6": 4.90,
    "W1": 0.90, "W2": 0.50,
    "D1": 0.50, "D2": 0.30, "D3": 0.30, "D4": 0.50, "D5": 1.40, "D6": 1.70,
}
WHAT = {
    "L1": "open-end leg, under the top strip",
    "L2": "meander top strips",
    "L3": "first top strip, ground leg to first finger",
    "L4": "meander finger depth",
    "L5": "meander bottom links",
    "L6": "feed and ground legs",
    "W1": "ground (shorting) leg width",
    "W2": "trace width everywhere else",
    "D1": "clearance beyond the ground leg",
    "D2": "clearance above the top strip",
    "D3": "clearance beyond the open end",
    "D4": "feed/ground pad height at the plane edge",
    "D5": "gap, feed leg to ground leg",
    "D6": "gap, feed leg to first meander finger",
}
TOL = 0.011   # mm; the table is quoted to 0.01


def collinear(a, b, c, tol=1e-6):
    """Is b redundant, sitting on the straight line from a to c?"""
    return abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) < tol


def drop_keyholes(points):
    pts = list(points)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts.pop()
    i = 0
    while i < len(pts):
        for j in range(i + 1, len(pts)):
            if pts[j] == pts[i]:
                del pts[i + 1:j + 1]
                break
        i += 1
    return pts


def measure(path: pathlib.Path) -> tuple[dict, dict]:
    fp = parse(path.read_text())
    poly = drop_keyholes([(float(p[1]), float(p[2]))
                          for p in find(find(fp, "fp_poly"), "pts")[1:]])
    pads = {str(p[1]): (float(find(p, "at")[1]), float(find(p, "at")[2]),
                        float(find(p, "size")[1]), float(find(p, "size")[2]))
            for p in find_all(fp, "pad")}
    keep = [(float(find(l, "start")[1]), float(find(l, "start")[2]),
             float(find(l, "end")[1]), float(find(l, "end")[2]))
            for l in find_all(fp, "fp_line") if str(find(l, "layer")[1]) == "Dwgs.User"]

    # Collapsing the drill-barrel ring leaves its slit entry behind, sitting
    # mid-edge on an otherwise straight side. Dropping collinear vertices
    # removes it without a magic distance, and leaves only real corners.
    poly = [pt for i, pt in enumerate(poly)
            if not collinear(poly[i - 1], pt, poly[(i + 1) % len(poly)])]

    # Figure 3 runs ground leg -> feed leg -> meander -> open end, left to
    # right. This footprint is the left-hand variant, mirrored about x.
    mirror = -1.0 if pads["2"][0] > pads["1"][0] else 1.0
    x = sorted({round(mirror * px, 3) for px, _ in poly})
    y = sorted({round(py, 3) for _, py in poly})
    kx = sorted(mirror * v for pair in keep for v in (pair[0], pair[2]))
    ky = sorted(v for pair in keep for v in (pair[1], pair[3]))

    if len(x) != 14 or len(y) != 6:
        raise SystemExit(f"unexpected geometry: {len(x)} x-coordinates and "
                         f"{len(y)} y-coordinates, expected 14 and 6")

    # x ladder: ground leg | gap | feed leg | gap | finger, link, finger, ...
    # y ladder: top of strip, under strip, finger ends, open-end tip, pad edge
    got = {
        "W1": x[1] - x[0],
        "D5": x[2] - x[1],
        "W2": x[3] - x[2],
        "D6": x[4] - x[3],
        "L3": x[5] - x[0],
        "L5": x[6] - x[5],
        "L2": x[9] - x[6],
        "L4": y[2] - y[0],
        "L6": y[5] - y[1],
        "L1": y[4] - y[1],
        "D1": x[0] - kx[0],        # kx is already in Figure 3 orientation
        "D2": y[0] - ky[0],
        "D3": kx[-1] - x[-1],
        "D4": pads["1"][3],
    }
    # the meander repeats: check the second instance of each repeated feature
    repeats = {"L5": x[10] - x[9], "L2": x[13] - x[10]}
    return got, {"vertices": len(poly), "mirrored": mirror < 0, "repeats": repeats}


def main() -> int:
    path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT
    got, info = measure(path)
    print(f"{path.name}: {info['vertices']} polygon vertices, "
          f"{'mirrored (left-hand variant)' if info['mirrored'] else 'as drawn in Figure 3'}\n")
    for name, value in info["repeats"].items():
        note = "matches" if abs(value - TABLE_1[name]) <= TOL else "DIFFERS"
        print(f"  second {name} in the meander: {value:.3f} mm ({note})")
    print()
    print(f"{'dim':4} {'SWRA117D':>10} {'measured':>10} {'error':>8}   what it is")
    bad = 0
    for name, want in TABLE_1.items():
        have = got[name]
        err = have - want
        ok = abs(err) <= TOL
        bad += 0 if ok else 1
        print(f"{name:4} {want:9.2f}  {have:9.3f}  {err:+8.3f} {'  ' if ok else ' !'} {WHAT[name]}")
    print()
    if bad:
        print(f"{bad} dimension(s) differ from the published reference by more than "
              f"{TOL * 1000:.0f} um")
    else:
        print(f"all {len(TABLE_1)} dimensions match SWRA117D Table 1 within "
              f"{TOL * 1000:.0f} um: this is an exact copy")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
