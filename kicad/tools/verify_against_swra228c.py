#!/usr/bin/env python3
"""Re-derive SWRA228C Table 1 from the written footprint, not from the generator.

The generator builds the antenna from Table 1.  Checking it against Table 1
with the generator's own arithmetic would prove nothing, so this reads the
polygons back out of the ``.kicad_mod`` and measures them the way a ruler
would: scanlines across the copper, runs and gaps, with no knowledge of how
the shape was built.

    python3 kicad/tools/verify_against_swra228c.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import parse, find, find_all  # noqa: E402

LIB = pathlib.Path(__file__).resolve().parent.parent / "library" / "TI_DN023.pretty"
FP = LIB / "TI_DN023_IFA_868.kicad_mod"
TOL = 0.011                      # 11 um, the tolerance used elsewhere here

TABLE_1 = {"L1": 20.0, "L2": 5.0, "L3": 4.0, "L4": 10.0, "L5": 6.0,
           "L6": 17.0, "L7": 43.0, "W": 1.0, "W2": 2.0}
MEANING = {
    "L1": "top of the copper down to the ground plane edge",
    "L2": "gap, shorting leg to feed leg",
    "L3": "gap, feed leg to the first meander stroke",
    "L4": "meander depth, inner",
    "L5": "one meander U, outer edge to outer edge",
    "L6": "the right-hand stub, the trim (Table 1 draws it untrimmed)",
    "L7": "overall antenna length",
    "W": "trace width",
    "W2": "feed leg width",
}


def polygons(path: pathlib.Path) -> list[list[tuple[float, float]]]:
    fp = parse(path.read_text())
    out = []
    for poly in find_all(fp, "fp_poly"):
        if str(find(poly, "layer")[1]) != "F.Cu":
            continue
        out.append([(float(xy[1]), float(xy[2]))
                    for xy in find(poly, "pts")[1:]])
    return out


def spans(polys, at, axis):
    """Merged intervals of copper along *axis* on the line at *at*.

    axis 0 scans in x at a given y; axis 1 scans in y at a given x.
    """
    other = 1 - axis
    cuts = []
    for poly in polys:
        for a, b in zip(poly, poly[1:] + poly[:1]):
            lo, hi = sorted((a[other], b[other]))
            if lo <= at < hi:
                f = (at - a[other]) / (b[other] - a[other])
                cuts.append((a[axis] + (b[axis] - a[axis]) * f, poly))
    out = []
    for poly in {id(p): p for _, p in cuts}.values():
        xs = sorted(c for c, p in cuts if p is poly)
        out += [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]
    out.sort()
    merged = []
    for lo, hi in out:
        if merged and lo <= merged[-1][1] + 1e-9:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def main() -> int:
    if not FP.exists():
        print(f"missing {FP} - run tools/gen_dn023_footprint.py")
        return 1
    polys = polygons(FP)
    xs = [p[0] for poly in polys for p in poly]
    ys = [p[1] for poly in polys for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    print(f"{FP.name}: {len(polys)} F.Cu polygons, "
          f"{sum(len(p) for p in polys)} vertices")
    print(f"  copper envelope {x1 - x0:.2f} x {y1 - y0:.2f} mm, "
          f"origin at the feed point\n")

    m = {}
    m["L7"] = x1 - x0
    m["L1"] = y1 - y0

    # just above the plane edge only the two legs are there
    legs = spans(polys, y1 - 0.5, axis=0)
    assert len(legs) == 2, f"expected 2 legs at the plane edge, found {len(legs)}"
    short, feed = legs
    m["W"] = short[1] - short[0]
    m["W2"] = feed[1] - feed[0]
    m["L2"] = feed[0] - short[1]

    # at mid meander depth: the legs plus one span per meander stroke
    bars = spans(polys, (y0 + y1) / 2 * 0 + y0 + 6.0, axis=0)
    strokes = [b for b in bars if b[0] > feed[1]]
    m["L3"] = strokes[0][0] - feed[1]
    m["L5"] = strokes[1][1] - strokes[0][0]

    # the meander's own height, down the middle of the second stroke
    col = spans(polys, (strokes[1][0] + strokes[1][1]) / 2, axis=1)
    m["L4"] = (col[0][1] - col[0][0]) - 2 * m["W"]

    # the stub: the deepest column at the far right
    col = spans(polys, (strokes[-1][0] + strokes[-1][1]) / 2, axis=1)
    m["L6"] = col[0][1] - col[0][0]

    print(f"{'dim':5} {'SWRA228C':>9} {'measured':>10} {'error':>8}   what it is")
    bad = 0
    for k in ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "W", "W2"):
        err = m[k] - TABLE_1[k]
        if abs(err) > TOL:
            bad += 1
        print(f"{k:5} {TABLE_1[k]:9.2f} {m[k]:10.3f} {err:+8.3f}   {MEANING[k]}")

    print(f"\n{len(strokes)} meander strokes at "
          f"{strokes[1][0] - strokes[0][0]:.2f} mm pitch "
          f"(L5 - W = {TABLE_1['L5'] - TABLE_1['W']:.2f})")
    print(f"construction check: {strokes[0][0] - x0:.2f} + "
          f"{len(strokes) - 1} x {strokes[1][0] - strokes[0][0]:.2f} + "
          f"{m['W']:.2f} = {x1 - x0:.2f} mm = L7")
    print(f"AN058 Table 10 quotes this antenna as 43 x 20 mm; "
          f"measured {m['L7']:.2f} x {m['L1']:.2f}")

    if bad:
        print(f"\n{bad} dimension(s) off by more than {TOL * 1000:.0f} um")
        return 1
    print(f"\nall 9 dimensions match SWRA228C Table 1 within "
          f"{TOL * 1000:.0f} um: this is an exact copy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
