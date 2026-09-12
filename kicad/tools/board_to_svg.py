#!/usr/bin/env python3
"""Render the board to a dimensioned SVG drawing, for reviews and documents.

Reads the same .kicad_pcb everything else reads, so the drawing cannot drift
from the layout.  Shapes carry class names instead of colours, so the page
embedding the SVG can theme it:

    .board-edge .keepout .keepout-hatch .plane-edge
    .fcu .trace .bcu .pad .via .dim .dim-text .note

Footprint references are deliberately not drawn: at this scale they collide
with the copper.  Name them in the legend of whatever embeds the drawing.

    python3 board_to_svg.py [out.svg]
"""

from __future__ import annotations

import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import find, find_all, parse  # noqa: E402

PCB = pathlib.Path(__file__).resolve().parent.parent / "swra117d_2g4_antenna.kicad_pcb"


def rotate(pt, deg):
    rad = math.radians(deg)
    return (pt[0] * math.cos(rad) - pt[1] * math.sin(rad),
            pt[0] * math.sin(rad) + pt[1] * math.cos(rad))


def f(value: float) -> str:
    return f"{value:.3f}".rstrip("0").rstrip(".")


def dimension(a, b, offset, label, vertical=False):
    """A dimension line with end ticks and a label, drafting style."""
    out = []
    if vertical:
        x = a[0] + offset
        out.append(f'<path class="dim" d="M{f(x)},{f(a[1])} L{f(x)},{f(b[1])}"/>')
        for y in (a[1], b[1]):
            out.append(f'<path class="dim" d="M{f(x - 0.6)},{f(y)} L{f(x + 0.6)},{f(y)}"/>')
        out.append(f'<text class="dim-text" x="{f(x - 0.9)}" y="{f((a[1] + b[1]) / 2)}" '
                   f'text-anchor="middle" dominant-baseline="middle" '
                   f'transform="rotate(-90 {f(x - 0.9)} {f((a[1] + b[1]) / 2)})">{label}</text>')
    else:
        y = a[1] + offset
        out.append(f'<path class="dim" d="M{f(a[0])},{f(y)} L{f(b[0])},{f(y)}"/>')
        for x in (a[0], b[0]):
            out.append(f'<path class="dim" d="M{f(x)},{f(y - 0.6)} L{f(x)},{f(y + 0.6)}"/>')
        out.append(f'<text class="dim-text" x="{f((a[0] + b[0]) / 2)}" y="{f(y - 0.7)}" '
                   f'text-anchor="middle">{label}</text>')
    return out


def render(pcb_path: pathlib.Path) -> str:
    pcb = parse(pcb_path.read_text())
    nets = {int(n[1]): str(n[2]) for n in find_all(pcb, "net")}

    edges = [((float(find(g, "start")[1]), float(find(g, "start")[2])),
              (float(find(g, "end")[1]), float(find(g, "end")[2])))
             for g in find_all(pcb, "gr_line")
             if str(find(g, "layer")[1]) == "Edge.Cuts"]
    xs = [p[0] for e in edges for p in e]
    ys = [p[1] for e in edges for p in e]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

    plane = min(float(xy[2]) for z in find_all(pcb, "zone") if not find(z, "keepout")
                for xy in find(find(z, "polygon"), "pts")[1:])

    body, pads_f, pads_b, vias = [], [], [], []
    for fp in find_all(pcb, "footprint"):
        ref = next(p[2] for p in find_all(fp, "property") if p[1] == "Reference")
        at = find(fp, "at")
        origin = (float(at[1]), float(at[2]))
        rot = float(at[3]) if len(at) > 3 else 0.0
        for poly in find_all(fp, "fp_poly"):
            if str(find(poly, "layer")[1]) != "F.Cu":
                continue
            pts = []
            for xy in find(poly, "pts")[1:]:
                rx, ry = rotate((float(xy[1]), float(xy[2])), -rot)
                pts.append(f"{f(origin[0] + rx)},{f(origin[1] + ry)}")
            body.append(f'<polygon class="fcu" points="{" ".join(pts)}"/>')
        for pad in find_all(fp, "pad"):
            pad_at = find(pad, "at")
            rx, ry = rotate((float(pad_at[1]), float(pad_at[2])), -rot)
            cx, cy = origin[0] + rx, origin[1] + ry
            size = find(pad, "size")
            w, h = float(size[1]), float(size[2])
            angle = (float(pad_at[3]) if len(pad_at) > 3 else 0.0)
            layers = [str(x) for x in find(pad, "layers")[1:]]
            cls = "bcu" if "B.Cu" in layers and "F.Cu" not in layers else "fcu pad"
            rect = (f'<rect class="{cls}" x="{f(cx - w / 2)}" y="{f(cy - h / 2)}" '
                    f'width="{f(w)}" height="{f(h)}" '
                    f'transform="rotate({f(-angle)} {f(cx)} {f(cy)})"/>')
            (pads_b if cls == "bcu" else pads_f).append(rect)

    for seg in find_all(pcb, "segment"):
        a = (float(find(seg, "start")[1]), float(find(seg, "start")[2]))
        b = (float(find(seg, "end")[1]), float(find(seg, "end")[2]))
        body.append(f'<path class="trace" stroke-width="{f(float(find(seg, "width")[1]))}" '
                    f'stroke-linecap="round" fill="none" '
                    f'd="M{f(a[0])},{f(a[1])} L{f(b[0])},{f(b[1])}"/>')
    for v in find_all(pcb, "via"):
        at = find(v, "at")
        vias.append(f'<circle class="via" cx="{f(float(at[1]))}" cy="{f(float(at[2]))}" '
                    f'r="{f(float(find(v, "size")[1]) / 2)}"/>')

    pad = 7.0
    vb = (x0 - pad, y0 - pad, (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'viewBox="{f(vb[0])} {f(vb[1])} {f(vb[2])} {f(vb[3])}" '
        f'role="img" aria-label="Dimensioned layout of the 2.45 GHz antenna test board">',
        '<defs><pattern id="ko" width="1.9" height="1.9" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)">'
        '<line class="keepout-hatch" x1="0" y1="0" x2="0" y2="1.9"/></pattern></defs>',
        f'<rect class="keepout" x="{f(x0)}" y="{f(y0)}" width="{f(x1 - x0)}" '
        f'height="{f(plane - y0)}" fill="url(#ko)"/>',
        f'<rect class="board-edge" x="{f(x0)}" y="{f(y0)}" width="{f(x1 - x0)}" '
        f'height="{f(y1 - y0)}"/>',
    ]
    parts += pads_b + body + pads_f + vias
    parts.append(f'<path class="plane-edge" d="M{f(x0 - 3)},{f(plane)} L{f(x1 + 3)},{f(plane)}"/>')
    parts.append(f'<text class="note" x="{f(x0 + 1.0)}" y="{f(plane + 2.4)}">'
                 f'GND plane edge &#8212; no copper above, any layer</text>')
    parts += dimension((x0, y1), (x1, y1), 4.2, f"{f(x1 - x0)} mm")
    parts += dimension((x0, y0), (x0, y1), -3.0, f"{f(y1 - y0)} mm", vertical=True)
    parts += dimension((x1, y0), (x1, plane), 3.0, f"{f(plane - y0)}", vertical=True)
    parts.append('</svg>')
    return "\n".join(parts) + "\n"


if __name__ == "__main__":
    dest = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("board.svg")
    dest.write_text(render(PCB))
    print(f"wrote {dest} ({len(dest.read_text())} bytes)")
