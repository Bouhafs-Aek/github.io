#!/usr/bin/env python3
"""Scale a footprint's geometry uniformly, to retune a printed antenna.

Uniform in-plane scaling is the one retune whose physics needs no model of
the antenna: multiply every dimension and every gap by k and each current
path and coupling distance scales with it, so the resonance moves as 1/k.
That holds whatever the meander is doing internally - unlike a developed
length calculation, which over-predicts the electrical length of a meandered
arm because adjacent segments carry opposing currents.

It is first order only: the substrate thickness does not scale, so the
effective permittivity shifts slightly and the resonance moves a little more
than 1/k. Simulate, take the ratio, scale, simulate again.

    ./scale_footprint.py in.kicad_mod out.kicad_mod --scale 1.155 --name NEW_NAME

Scales positions, pad sizes, drills and outlines. Leaves text sizes, stroke
widths and layer assignments alone - those are drafting, not geometry.
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, dumps, find, num, parse  # noqa: E402

# node -> indices of the numeric children that are lengths
COORDS = {
    "xy": (1, 2), "start": (1, 2), "end": (1, 2), "mid": (1, 2),
    "center": (1, 2), "size": (1, 2), "at": (1, 2), "drill": (1,),
    "radius": (1,), "offset": (1, 2),
}
SKIP = {"effects", "font", "stroke", "thickness", "roundrect_rratio", "uuid"}


def scale_node(node, k: float):
    if not isinstance(node, list) or not node:
        return
    head = str(node[0])
    if head in SKIP:
        return
    if head in COORDS:
        for i in COORDS[head]:
            if i < len(node) and not isinstance(node[i], list):
                node[i] = num(float(node[i]) * k)
    for child in node:
        scale_node(child, k)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("source", type=pathlib.Path)
    ap.add_argument("dest", type=pathlib.Path)
    ap.add_argument("--scale", type=float, required=True)
    ap.add_argument("--name", help="name for the scaled footprint")
    ap.add_argument("--note", default="", help="sentence to add to the description")
    args = ap.parse_args()

    fp = parse(args.source.read_text())
    original = str(fp[1])
    for child in fp[2:]:
        scale_node(child, args.scale)
    if args.name:
        fp[1] = args.name
        for prop in fp:
            if isinstance(prop, list) and prop[0] == "property" and prop[1] == "Value":
                prop[2] = args.name
    descr = find(fp, "descr")
    if descr is not None:
        descr[1] = (f"{descr[1]} Geometry scaled x{args.scale:g} from "
                    f"{original} to retune the resonance by 1/{args.scale:g}."
                    + (f" {args.note}" if args.note else ""))
    for prop in fp:
        if isinstance(prop, list) and prop[0] == "generator":
            prop[1] = "scale_footprint.py"
    args.dest.write_text(dumps(fp) + "\n")

    poly = find(fp, "fp_poly")
    xs = [float(p[1]) for p in find(poly, "pts")[1:]]
    ys = [float(p[2]) for p in find(poly, "pts")[1:]]
    print(f"wrote {args.dest}")
    print(f"  scale x{args.scale:g}: copper now spans "
          f"{max(xs) - min(xs):.2f} x {max(ys) - min(ys):.2f} mm "
          f"(x {min(xs):.2f}..{max(xs):.2f}, y {min(ys):.2f}..{max(ys):.2f})")
    for pad in fp:
        if isinstance(pad, list) and pad[0] == "pad":
            at, size = find(pad, "at"), find(pad, "size")
            print(f"  pad {pad[1]}: at ({float(at[1]):.3f}, {float(at[2]):.3f}) "
                  f"size {float(size[1]):.3f} x {float(size[2]):.3f}")


if __name__ == "__main__":
    main()
