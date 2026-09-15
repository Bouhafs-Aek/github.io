#!/usr/bin/env python3
"""Generate the TI DN024 (SWRA227E) meandering monopole from Table 1.

DN024 gives the antenna as a picture (Figure 2) and nine dimensions (Table 1),
and says the authoritative source is the CC-Antenna-DK board 6 Gerber - but
also that "If the CAD tool being used does not support import of Gerber files,
Figure 2 and Table 1 can be used."  This is that, done arithmetically rather
than by tracing pixels.

Table 1 turns out to close on itself, which is the check that the reading of
Figure 2 is right: four arms of W with three L3 gaps between them is 17.0 mm,
X2 - 17.0 leaves 8.0 mm below the bottom arm, and L1 + L5 - W is also 8.0 mm.
Two independent routes to the same number.  The envelope that falls out,
L4 x X2 = 38 x 25 mm, is the size the note quotes in its introduction.

The path, from the feed up (this is the whole antenna):

    feed --L1 up--> bottom arm --L2 right--> up --> arm 3 left -->
    up --> arm 2 right --> up --> arm 1 left, L4 long, open at the tip

Copper goes on F.Cu *and* B.Cu: section 3 says the layout is on both layers,
"this enables a lower resistive loss and gives a slightly wider bandwidth
compared to a single sided layout solution".

Two sheets of copper only count as one conductor if they are tied along their
length.  Joined at the feed alone, they are a 150 mm parallel-plate line -
1.6 mm apart, about 140 ohm - open at the tip, and it has resonances of its
own inside the band the antenna is meant to work in.  So the radiator is
stitched at VIA_PITCH along its centre line, which is inside lambda/20 in FR4
at 2.44 GHz - the same rule used for ground stitching on the other boards,
applied here to the top band of the dual band build.

DN024 does not dimension this - it says nothing about vias at all, and the
authoritative geometry is a Gerber we do not have.  The pitch is therefore an
engineering choice, and it is the one place in this footprint that is not
Table 1.

    python3 kicad/tools/gen_dn024_footprint.py
"""

from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import math  # noqa: E402

from sexpr import Sym, dumps, num  # noqa: E402

NAME = "TI_DN024_Monopole_868_2440"
DEST = (pathlib.Path(__file__).resolve().parent.parent / "library"
        / "TI_DN024.pretty" / f"{NAME}.kicad_mod")
UUID = "c4d9e17a-2b03-5e04-8a10-0000000000"

# SWRA227E Table 1, verbatim
TABLE_1 = {
    "L1": 9.0,    # feed trace, plane edge side to the top of the bottom arm
    "L2": 18.0,   # bottom arm, from the feed trace's far edge to the right end
    "L3": 3.0,    # gap between meander arms
    "L4": 38.0,   # top arm, the full width of the antenna
    "L5": 1.0,    # plane edge to the foot of the feed trace
    "W": 2.0,     # trace width, everywhere
    "X2": 25.0,   # plane edge to the top of the antenna
    "Y": 43.0,    # reference board ground plane width
    "X1": 63.0,   # reference board ground plane height
}
ARMS = 4
VIA_PITCH = 2.8      # lambda/20.7 in FR4 at 2.44 GHz
VIA_PAD, VIA_DRILL = 0.6, 0.3

# Observed, not invented: the reference board centres a 38 mm antenna on a
# 43 mm ground plane, so it leaves this much clear either side.
SIDE_CLEARANCE = (TABLE_1["Y"] - TABLE_1["L4"]) / 2


def centre_line() -> list[tuple[float, float]]:
    """The meander as a polyline through the middle of the trace.

    Origin is the feed point: the foot of the feed trace, L5 above the ground
    plane edge.  y is KiCad's, so the antenna runs to negative y.
    """
    t = TABLE_1
    half = t["W"] / 2
    pitch = t["W"] + t["L3"]

    # L2 is measured from the feed trace's far edge to the copper's right edge,
    # so the right edge is at half + L2 and the turns' centre line is half in
    # from that.  L4 is the top arm's full copper length, and its tip is a flat
    # cap, so the centre line runs all the way to it.
    right = t["L2"]                             # = (half + L2) - half
    tip = half + t["L2"] - t["L4"]              # open end of the top arm
    left = tip + half                           # centre of the left-hand turn

    # centre of each arm, bottom (index 0) to top
    below = t["L1"] - half          # feed foot to the bottom arm's centre line
    arm_y = [-(below + i * pitch) for i in range(ARMS)]

    path = [(0.0, 0.0), (0.0, arm_y[0])]
    x = right
    for i, y in enumerate(arm_y):
        path.append((x, y))                       # run along this arm
        if i + 1 < len(arm_y):
            path.append((x, arm_y[i + 1]))        # turn up into the next
            x = left if x == right else right
    path[-1] = (tip, arm_y[-1])                   # the top arm ends at its tip
    return path


def offset_outline(path, width) -> list[tuple[float, float]]:
    """Both sides of a constant-width ribbon, as one closed polygon.

    Every segment here is axis aligned and every turn is a right angle, so the
    mitre is exact: the offset corner is the intersection of the two offset
    lines, with no rounding to approximate.
    """
    half = width / 2

    def normals(pts):
        out = []
        for a, b in zip(pts, pts[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            length = (dx * dx + dy * dy) ** 0.5
            out.append((-dy / length, dx / length))
        return out

    def side(pts, sign):
        n = normals(pts)
        edge = []
        for i, (nx, ny) in enumerate(n):
            a, b = pts[i], pts[i + 1]
            edge.append(((a[0] + sign * half * nx, a[1] + sign * half * ny),
                         (b[0] + sign * half * nx, b[1] + sign * half * ny)))
        out = [edge[0][0]]
        for (p1, p2), (p3, p4) in zip(edge, edge[1:]):
            out.append(intersect(p1, p2, p3, p4))
        out.append(edge[-1][1])
        return out

    return side(path, 1) + list(reversed(side(path, -1)))


def stitch_points(path, pitch, end_margin):
    """Points every *pitch* along a polyline, from the feed onward.

    The feed itself is already a plated hole, so the walk starts one pitch in,
    and it stops *end_margin* short of the open tip: a via on the tip would sit
    on the flat end cap with no copper around it.  Everywhere else a point on
    the centre line is half the trace width from either edge - more at the
    corners, since a right-angle mitre puts its inner vertex further out.
    """
    total = sum(math.dist(a, b) for a, b in zip(path, path[1:]))
    out, carry, walked = [], pitch, 0.0
    for a, b in zip(path, path[1:]):
        length = math.dist(a, b)
        travelled = carry
        while travelled <= length + 1e-9:
            if walked + travelled <= total - end_margin:
                f = travelled / length
                out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
            travelled += pitch
        carry = travelled - length
        walked += length
    return out


def intersect(p1, p2, p3, p4):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < 1e-12:                      # collinear: no corner here
        return p2
    a = x1 * y2 - y1 * x2
    b = x3 * y4 - y3 * x4
    return ((a * (x3 - x4) - (x1 - x2) * b) / den,
            (a * (y3 - y4) - (y1 - y2) * b) / den)


def build() -> list:
    t = TABLE_1
    path = centre_line()
    poly = offset_outline(path, t["W"])
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    box = (min(xs), min(ys), max(xs), max(ys))
    keepout = (box[0] - SIDE_CLEARANCE, box[1],
               box[2] + SIDE_CLEARANCE, t["L5"])

    n = [0]

    def uid():
        n[0] += 1
        return [Sym("uuid"), f"{UUID}{n[0]:02d}"]

    def text(kind, value, y, layer, size, prop=True):
        head = [Sym("property"), kind.capitalize(), value] if prop else \
               [Sym("fp_text"), Sym(kind), value]
        return head + [
            [Sym("at"), num(0), num(y), Sym("0")],
            [Sym("layer"), layer], uid(),
            [Sym("effects"), [Sym("font"), [Sym("size"), num(size), num(size)],
                              [Sym("thickness"), num(size * 0.15)]]]]

    def rect(a, b, layer, width, style="solid"):
        return [Sym("fp_rect"),
                [Sym("start"), num(a[0]), num(a[1])],
                [Sym("end"), num(b[0]), num(b[1])],
                [Sym("stroke"), [Sym("width"), num(width)], [Sym("type"), Sym(style)]],
                [Sym("fill"), Sym("no")], [Sym("layer"), layer], uid()]

    fp = [Sym("footprint"), NAME,
          [Sym("version"), Sym("20241229")],
          [Sym("generator"), "gen_dn024_footprint.py"],
          [Sym("generator_version"), "9.0"],
          [Sym("layer"), "F.Cu"],
          [Sym("descr"),
           "TI DN024 (SWRA227E) meandering monopole, exact copy of Table 1: "
           "868/915/920 MHz single band, or 868 + 2440 MHz dual band. "
           f"{t['L4']} x {t['X2']} mm envelope, {t['W']} mm trace, on 1.6 mm FR4. "
           "Copper on both layers, tied at the plated feed hole. The note "
           "requires a pi matching network at the feed and gives its values; "
           "the antenna itself is not a 50 ohm part."],
          [Sym("tags"), "antenna monopole meander 868 915 920 2440 MHz TI DN024"],
          [Sym("attr"), Sym("exclude_from_pos_files"), Sym("exclude_from_bom")],
          text("reference", "REF**", t["L5"] + 2.2, "F.SilkS", 1.0),
          text("value", NAME, t["L5"] + 3.8, "F.Fab", 0.8)]

    pts = [Sym("pts")] + [[Sym("xy"), num(round(x, 4)), num(round(y, 4))]
                          for x, y in poly]
    for layer in ("F.Cu", "B.Cu"):
        fp.append([Sym("fp_poly"), pts,
                   [Sym("stroke"), [Sym("width"), num(0)], [Sym("type"), Sym("solid")]],
                   [Sym("fill"), Sym("yes")],
                   [Sym("layer"), layer], uid()])

    # the clear area: the antenna's own envelope, plus the 2.5 mm either side
    # that the reference board leaves by centring 38 mm of antenna on 43 mm of
    # ground.  Nothing above it is dimensioned by the note.
    fp.append(rect((keepout[0], keepout[1]), (keepout[2], keepout[3]),
                   "Dwgs.User", 0.1, "dash"))
    fp.append(rect((keepout[0] - 0.25, keepout[1] - 0.25),
                   (keepout[2] + 0.25, keepout[3] + 0.25), "F.CrtYd", 0.05))
    fp.append(rect((box[0], box[1]), (box[2], box[3]), "F.Fab", 0.1))

    # Feed: a plated hole, so the two sides of the antenna meet at the port.
    fp.append([Sym("pad"), "1", Sym("thru_hole"), Sym("rect"),
               [Sym("at"), num(0), num(0)],
               [Sym("size"), num(t["W"]), num(t["W"])],
               [Sym("drill"), num(0.6)],
               [Sym("layers"), "*.Cu", "*.Mask"],
               [Sym("remove_unused_layers"), Sym("no")], uid()])

    # ... and stitched along its length, so the two sides are one conductor
    # rather than a transmission line with the antenna's own current on it.
    stitches = stitch_points(path, VIA_PITCH, VIA_PAD / 2 + 0.2)
    for x, y in stitches:
        fp.append([Sym("pad"), "1", Sym("thru_hole"), Sym("circle"),
                   [Sym("at"), num(round(x, 4)), num(round(y, 4))],
                   [Sym("size"), num(VIA_PAD), num(VIA_PAD)],
                   [Sym("drill"), num(VIA_DRILL)],
                   [Sym("layers"), "*.Cu"],
                   [Sym("remove_unused_layers"), Sym("no")], uid()])
    fp.append([Sym("embedded_fonts"), Sym("no")])
    return fp, box, keepout, stitches


def main() -> None:
    fp, box, keepout, stitches = build()
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(dumps(fp) + "\n")
    print(f"wrote {DEST.relative_to(DEST.parents[2])}")
    print(f"  copper envelope  {box[2] - box[0]:.2f} x {box[3] - box[1]:.2f} mm "
          f"(note: {TABLE_1['L4']} x {TABLE_1['X2'] - TABLE_1['L5']} above the feed)")
    print(f"  clear area       {keepout[2] - keepout[0]:.2f} x "
          f"{keepout[3] - keepout[1]:.2f} mm, {SIDE_CLEARANCE} mm either side")
    print(f"  copper on F.Cu and B.Cu, stitched by {len(stitches)} vias at "
          f"{VIA_PITCH} mm plus the plated feed hole")


if __name__ == "__main__":
    main()
