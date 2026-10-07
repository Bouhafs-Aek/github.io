#!/usr/bin/env python3
"""Generate the TI DN023 / SWRA228C printed inverted-F from its Table 1.

SWRA228C gives the antenna as Figure 2 and eleven numbers, and says the
authoritative source is the CC1110EM IIFA reference design Gerber - which we
do not have - but also that *"If the CAD tool being used does not support
import of Gerber files, Figure 2 and Table 1 can be used."*

The reading of Figure 2 is checkable rather than a guess, because Table 1
closes on itself.  Working left to right from the shorting leg:

    short leg   x 0 .. W                      = 0 .. 1.0
    gap L2                                    -> 6.0
    feed leg    x .. + W2                     = 6.0 .. 8.0
    gap L3                                    -> 12.0
    seven meander strokes at pitch L5 - W     = 12, 17, 22, 27, 32, 37, 42
    right edge  42 + W                        = 43.0  ==  L7

L7 falls out of the construction instead of being assumed, and the meander's
overall height, L4 + 2W = 12.0 mm, and the antenna height L1 = 20.0 mm both
match the raster to 0.10 mm.  AN058 Table 10 independently quotes the antenna
as 43 x 20 mm, which is L7 x L1.  Four agreements, none of them circular.

L6 IS A TRIM, NOT A FIXED DIMENSION.  SWRA228C gives it three different
values and its own revision history says Table 1 was corrected:

    Table 1              L6 = 17.0 mm   (as drawn, the untrimmed length)
    section 3.1 text     "approx. 9 mm for 868 MHz and 1 mm for 915 MHz"
    Figures 12 and 13    "L6 = 11 mm" at 868, "L6 = 3 mm" at 915

The two measured captions sit exactly 2 mm - one W2 - above the text, which
looks like the two are measured from different datums rather than one being
wrong.  Nothing here picks between them: the footprint is built at Table 1's
17.0 mm, which is the longest and therefore the only one you can still cut
back from, and ``--l6`` builds any of the others for comparison.  The note's
own instruction is that the antenna is tuned by trimming its length.

    python3 kicad/tools/gen_dn023_footprint.py
    python3 kicad/tools/gen_dn023_footprint.py --l6 11.0   # 868 MHz, Figure 12
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from gen_dn024_footprint import offset_outline  # noqa: E402
from sexpr import Sym, dumps, num  # noqa: E402

NAME = "TI_DN023_IFA_868"
LIB = pathlib.Path(__file__).resolve().parent.parent / "library" / "TI_DN023.pretty"
UUID = "a7f3b208-5c41-5d96-b273-0000000000"

# SWRA228C Table 1, verbatim.
TABLE_1 = {
    "L1": 20.0,   # top of the copper down to the ground plane edge
    "L2": 5.0,    # gap, shorting leg to feed leg
    "L3": 4.0,    # gap, feed leg to the first meander stroke
    "L4": 10.0,   # meander depth, inner
    "L5": 6.0,    # one meander U, outer edge to outer edge
    "L6": 17.0,   # the right-hand stub - THE TRIM, see the module docstring
    "L7": 43.0,   # overall antenna length
    "X": 31.0,    # reference ground plane, across
    "Y": 45.0,    # reference ground plane, along
    "W": 1.0,     # trace width
    "W2": 2.0,    # feed leg width
}
STROKES = 7                     # falls out of L7; asserted below
# The two tuned lengths the note measured, for the silkscreen trim scale.
TRIM_MARKS = ((11.0, "868"), (3.0, "915"))


def geometry(t: dict) -> dict:
    """Every x and y the antenna needs, derived from Table 1 alone."""
    w, w2 = t["W"], t["W2"]
    pitch = t["L5"] - w
    short_x = w / 2                                  # centre of the short leg
    feed_l = w + t["L2"]
    feed_x = feed_l + w2 / 2                         # centre of the feed leg
    first = feed_l + w2 + t["L3"] + w / 2            # centre of stroke 1
    strokes = [first + i * pitch for i in range(STROKES)]
    right = strokes[-1] + w / 2
    assert abs(right - t["L7"]) < 1e-9, (
        f"the construction gives {right} mm where Table 1 says L7 = {t['L7']}")
    return dict(pitch=pitch, short_x=short_x, feed_x=feed_x, strokes=strokes,
                top=w / 2,                            # centre line of the top
                bottom=t["L4"] + w + w / 2,           # centre line of a return
                # offset_outline caps a ribbon flat AT its last centre-line
                # point rather than half a width past it, so the stub's centre
                # line has to run the full L6 for the copper to measure L6.
                plane=t["L1"], stub_end=t["L6"])


def centre_line(t: dict) -> list[tuple[float, float]]:
    """Short leg -> top rail -> meander -> the L6 stub's open end.

    One continuous path at width W.  The feed leg is a separate branch, since
    it is wider: W2, not W.
    """
    g = geometry(t)
    top, bottom = g["top"], g["bottom"]
    path = [(g["short_x"], g["plane"]), (g["short_x"], top)]
    for i, x in enumerate(g["strokes"]):
        # strokes alternate: the odd ones dive to the return, the even ones
        # come back up to the rail
        path.append((x, top))
        if i < STROKES - 1:
            if i % 2 == 0:
                path.append((x, bottom))
                path.append((g["strokes"][i + 1], bottom))
            else:
                path.append((x, top))
    path.append((g["strokes"][-1], g["stub_end"]))
    return _dedupe(path)


def feed_line(t: dict) -> list[tuple[float, float]]:
    g = geometry(t)
    return [(g["feed_x"], g["plane"]), (g["feed_x"], 0.0)]


def _dedupe(path):
    out = [path[0]]
    for p in path[1:]:
        if abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    return out


def build(t: dict) -> list:
    g = geometry(t)
    origin = (g["feed_x"], g["plane"])        # local 0,0 is the feed point
    n = [0]

    def uid():
        n[0] += 1
        return [Sym("uuid"), f"{UUID}{n[0]:02d}"]

    def local(p):
        return (p[0] - origin[0], p[1] - origin[1])

    def poly(points, layer):
        pts = [Sym("pts")] + [[Sym("xy"), num(x), num(y)]
                              for x, y in (local(p) for p in points)]
        return [Sym("fp_poly"), pts,
                [Sym("stroke"), [Sym("width"), num(0)], [Sym("type"), Sym("solid")]],
                [Sym("fill"), Sym("yes")], [Sym("layer"), layer], uid()]

    def pad(number, at, size, name):
        return [Sym("pad"), number, Sym("smd"), Sym("rect"),
                [Sym("at"), num(at[0]), num(at[1])],
                [Sym("size"), num(size[0]), num(size[1])],
                [Sym("layers"), "F.Cu", "F.Mask"],
                [Sym("pinfunction"), name], uid()]

    def text(kind, value, at, layer, size):
        return [Sym("property"), kind.capitalize(), value,
                [Sym("at"), num(at[0]), num(at[1]), Sym("0")],
                [Sym("layer"), layer], uid(),
                [Sym("effects"), [Sym("font"), [Sym("size"), num(size), num(size)],
                                  [Sym("thickness"), num(size * 0.15)]]]]

    def line(a, b, layer, width=0.12):
        a, b = local(a), local(b)
        return [Sym("fp_line"), [Sym("start"), num(a[0]), num(a[1])],
                [Sym("end"), num(b[0]), num(b[1])],
                [Sym("stroke"), [Sym("width"), num(width)], [Sym("type"), Sym("solid")]],
                [Sym("layer"), layer], uid()]

    body = offset_outline(centre_line(t), t["W"])
    feed = offset_outline(feed_line(t), t["W2"])

    fp = [Sym("footprint"), NAME,
          [Sym("version"), Sym("20241229")],
          [Sym("generator"), "gen_dn023_footprint.py"],
          [Sym("generator_version"), "9.0"],
          [Sym("layer"), "F.Cu"],
          [Sym("descr"),
           f"TI DN023 / SWRA228C printed inverted-F for 868 / 915 / 955 MHz. "
           f"Exact copy of Table 1: L1={t['L1']} L2={t['L2']} L3={t['L3']} "
           f"L4={t['L4']} L5={t['L5']} L6={t['L6']} L7={t['L7']} W={t['W']} "
           f"W2={t['W2']} mm, {t['L7']} x {t['L1']} mm overall. One layer, no "
           f"ground beneath. L6 is the tuning trim: Table 1 draws {TABLE_1['L6']} mm, "
           f"the note measured 11 mm at 868 MHz and 3 mm at 915 MHz. Keep at "
           f"least 5 mm clear either side (SWRA228C 3.1), 15 mm if there is "
           f"ground plane beside it (4.2)."],
          [Sym("tags"), "antenna IFA inverted-F 868 915 955 MHz sub-GHz TI DN023"],
          [Sym("attr"), Sym("exclude_from_pos_files"), Sym("exclude_from_bom"),
           Sym("allow_missing_courtyard")],
          text("reference", "REF**", (2.0, 2.4), "F.SilkS", 1.0),
          text("value", NAME, (2.0, 4.0), "F.Fab", 0.8),
          poly(body, "F.Cu"), poly(body, "F.Mask"),
          poly(feed, "F.Cu"), poly(feed, "F.Mask"),
          pad("1", local((g["feed_x"], g["plane"] - t["W"] / 2)),
              (t["W2"], t["W"]), "FEED"),
          pad("2", local((g["short_x"], g["plane"] - t["W"] / 2)),
              (t["W"], t["W"]), "SHORT")]

    def fp_text(value, at, layer, size, justify=None):
        node = [Sym("fp_text"), Sym("user"), value,
                [Sym("at"), num(at[0]), num(at[1]), Sym("0")],
                [Sym("layer"), layer], uid()]
        effects = [Sym("effects"),
                   [Sym("font"), [Sym("size"), num(size), num(size)],
                    [Sym("thickness"), num(size * 0.15)]]]
        if justify:
            effects.append([Sym("justify"), Sym(justify)])
        node.append(effects)
        return node

    # The trim scale.  L6 is cut back to tune, so the board carries the two
    # lengths the note actually measured, marked off the stub's own tip.
    stub_x = g["strokes"][-1]
    for value, band in TRIM_MARKS:
        y = value                      # where the copper must end after the cut
        if y < g["top"] or value > t["L6"]:
            continue
        fp.append(line((stub_x + 0.9, y), (stub_x + 2.2, y), "F.SilkS", 0.1))
        fp.append(fp_text(f"{band} MHz  L6={value:g}",
                          local((stub_x + 2.5, y)), "F.SilkS", 0.7, "left"))

    fp.append([Sym("embedded_fonts"), Sym("no")])
    return fp


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--l6", type=float, default=TABLE_1["L6"],
                    help="the trim length (Table 1 draws 17.0; the note "
                         "measured 11.0 at 868 MHz and 3.0 at 915 MHz)")
    ap.add_argument("--name", default=None)
    args = ap.parse_args()

    t = dict(TABLE_1, L6=args.l6)
    g = geometry(t)
    global NAME
    if args.name:
        NAME = args.name
    elif args.l6 != TABLE_1["L6"]:
        NAME = f"TI_DN023_IFA_868_L6_{args.l6:g}".replace(".", "p")

    LIB.mkdir(parents=True, exist_ok=True)
    dest = LIB / f"{NAME}.kicad_mod"
    dest.write_text(dumps(build(t)) + "\n")
    print(f"wrote library/{LIB.name}/{dest.name}")
    print(f"  {t['L7']} x {t['L1']} mm, {STROKES} meander strokes at "
          f"{g['pitch']} mm pitch, trace {t['W']} mm, feed leg {t['W2']} mm")
    print(f"  L6 = {t['L6']} mm"
          + ("  (Table 1, untrimmed)" if t["L6"] == TABLE_1["L6"] else
             "  (trimmed from Table 1's 17.0)"))


if __name__ == "__main__":
    main()
