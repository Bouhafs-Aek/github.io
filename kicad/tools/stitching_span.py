#!/usr/bin/env python3
"""How far any point on the ground pour is from a stitching via.

The pitch rule for stitching is quoted as a pitch, but a pitch only describes
a regular grid: what actually matters is the largest patch of pour with no via
in it, because that patch is a resonator.  This measures it directly - the
largest empty circle over the filled pour - and reports the half-wave
resonance of the span it implies.

Areas where the pour is deliberately absent (the feed line's keep-away
corridor, the port gap) are excluded: there is no copper there to resonate.

    python3 kicad/tools/stitching_span.py [board.kicad_pcb ...]
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import find, find_all, parse  # noqa: E402

PRJ_DIR = pathlib.Path(__file__).resolve().parent.parent
DEFAULTS = (PRJ_DIR / "swra117d_2g4_antenna.kicad_pcb",
            PRJ_DIR / "sim" / "board" / "swra117d_2g4_sim.kicad_pcb")
STEP = 0.25


def measure(path: pathlib.Path) -> dict:
    pcb = parse(path.read_text())
    vias = [(float(find(v, "at")[1]), float(find(v, "at")[2]))
            for v in find_all(pcb, "via")]
    pours = [z for z in find_all(pcb, "zone") if not find(z, "keepout")]
    top = [z for z in pours if str(find(z, "layer")[1]) == "F.Cu"]
    if not top:
        # nothing to stitch: the ground is on one layer, so there is no second
        # sheet of copper that has to be tied to it
        return None
    if not vias:
        raise SystemExit(f"{path.name}: has a top pour but no vias to stitch it")
    pts = [(float(xy[1]), float(xy[2])) for z in pours
           for xy in find(find(z, "polygon"), "pts")[1:]]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)

    cuts = []
    for zone in find_all(pcb, "zone"):
        keepout = find(zone, "keepout")
        if keepout is None or str(find(keepout, "copperpour")[1]) != "not_allowed":
            continue
        q = [(float(xy[1]), float(xy[2]))
             for xy in find(find(zone, "polygon"), "pts")[1:]]
        cuts.append((min(a for a, _ in q), min(b for _, b in q),
                     max(a for a, _ in q), max(b for _, b in q)))

    stack = find(find(pcb, "setup"), "stackup")
    core = next(l for l in find_all(stack, "layer")
                if str(l[1]).startswith("dielectric"))
    er = float(find(core, "epsilon_r")[1])

    worst, where = 0.0, None
    y = y0
    while y <= y1:
        x = x0
        while x <= x1:
            if not any(c[0] <= x <= c[2] and c[1] <= y <= c[3] for c in cuts):
                d = min(math.dist((x, y), v) for v in vias)
                if d > worst:
                    worst, where = d, (round(x, 2), round(y, 2))
            x += STEP
        y += STEP

    span = 2 * worst                       # a patch this wide is half a wave
    return dict(vias=len(vias), radius=worst, span=span, at=where, er=er,
                f_res=299792458.0 / ((2 * span / 1000) * math.sqrt(er)))


def main() -> int:
    paths = [pathlib.Path(a) for a in sys.argv[1:]] or list(DEFAULTS)
    for path in paths:
        m = measure(path)
        if m is None:
            print(f"{path.name}: ground on one layer only - no top pour to "
                  "stitch, so there is no unstitched span to measure")
            continue
        print(f"{path.name}: {m['vias']} vias; the worst-stitched point on the "
              f"pour is {m['radius']:.2f} mm from one, at {m['at']}\n"
              f"{' ' * len(path.name)}  -> unstitched span {m['span']:.2f} mm, "
              f"half-wave resonant at {m['f_res'] / 1e9:.1f} GHz "
              f"in FR4 (er {m['er']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
