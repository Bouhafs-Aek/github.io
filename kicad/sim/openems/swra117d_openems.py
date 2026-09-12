#!/usr/bin/env python3
"""Full-wave (FDTD) model of the SWRA117D 2.45 GHz radiator for openEMS.

The geometry is read out of ``swra117d_2g4_antenna.kicad_pcb`` - board
outline, stackup, ground plane edge, antenna copper, the routed 50 ohm feed
and the pour keep-away corridors - so the simulation always matches the board
that gets fabricated.  The board carries no matching network: the port looks
straight into the feed line and the radiator, which is what a VNA at the SMA
connector would see.

Simplifications: copper is modelled as a zero thickness sheet, the connector
itself is not in the model (the port launches at the board edge in its place),
and the SMA ground pads are left to the surrounding pour.

Usage:
    python3 swra117d_openems.py --dry-run        # geometry summary, no solver
    python3 swra117d_openems.py                  # run FDTD, print S11 + gain
    python3 swra117d_openems.py --plot           # ... and show the plots

Needs openEMS with its python bindings (CSXCAD, openEMS) for anything but
--dry-run:  https://docs.openems.de/python/install.html
"""

from __future__ import annotations

import argparse
import math
import os
import pathlib
import sys
import tempfile

TOOLS = pathlib.Path(__file__).resolve().parents[2] / "tools"
sys.path.insert(0, str(TOOLS))
from sexpr import find, find_all, parse  # noqa: E402

PCB = pathlib.Path(__file__).resolve().parents[2] / "swra117d_2g4_antenna.kicad_pcb"

F0 = 2.45e9      # band centre
FC = 1.0e9       # gaussian excitation half width -> 1.45 .. 3.45 GHz
C0 = 299792458.0
EPS0 = 8.8541878128e-12


# --------------------------------------------------------------- board input
def rotate(pt, deg):
    rad = math.radians(deg)
    return (pt[0] * math.cos(rad) - pt[1] * math.sin(rad),
            pt[0] * math.sin(rad) + pt[1] * math.cos(rad))


def drop_keyholes(points):
    """Collapse the zero width slits KiCad uses to punch holes in a polygon.

    A hole is drawn as a slit that runs from the outline to the hole, around
    it, and back along itself, which shows up as a vertex repeating later in
    the list.  FDTD meshing does not like those degenerate slivers and the
    holes here (a clearance ring around the ground pin) are far smaller than
    the mesh, so the enclosed run is dropped and the outline is kept.
    """
    pts = list(points)
    if len(pts) > 1 and pts[0] == pts[-1]:   # closing vertex, not a keyhole
        pts.pop()
    i = 0
    while i < len(pts):
        for j in range(i + 1, len(pts)):
            if pts[j] == pts[i]:
                del pts[i + 1:j + 1]
                break
        i += 1
    return pts


def order_path(segments, start):
    """Chain feed line segments into a path that starts at *start*."""
    remaining = list(segments)
    path, point = [], start
    while remaining:
        for i, (a, b, width) in enumerate(remaining):
            if math.dist(a, point) < 1e-6:
                path.append((a, b, width))
                point = b
            elif math.dist(b, point) < 1e-6:
                path.append((b, a, width))
                point = a
            else:
                continue
            remaining.pop(i)
            break
        else:
            raise SystemExit("the feed line on the board is not one contiguous path")
    return path


def load_board(path: pathlib.Path) -> dict:
    pcb = parse(path.read_text())
    nets = {int(n[1]): str(n[2]) for n in find_all(pcb, "net")}

    edges = [((float(find(g, "start")[1]), float(find(g, "start")[2])),
              (float(find(g, "end")[1]), float(find(g, "end")[2])))
             for g in find_all(pcb, "gr_line")
             if str(find(g, "layer")[1]) == "Edge.Cuts"]
    xs = [p[0] for e in edges for p in e]
    ys = [p[1] for e in edges for p in e]
    outline = (min(xs), min(ys), max(xs), max(ys))

    stack = find(find(pcb, "setup"), "stackup")
    core = next(l for l in find_all(stack, "layer") if str(l[1]).startswith("dielectric"))
    substrate = dict(h=float(find(core, "thickness")[1]),
                     er=float(find(core, "epsilon_r")[1]),
                     tand=float(find(core, "loss_tangent")[1]))

    gnd_top = min(float(xy[2])
                  for zone in find_all(pcb, "zone") if not find(zone, "keepout")
                  for xy in find(find(zone, "polygon"), "pts")[1:])

    # rule areas that keep the top pour off the feed line
    corridors = []
    for zone in find_all(pcb, "zone"):
        keepout = find(zone, "keepout")
        if keepout is None or str(find(keepout, "copperpour")[1]) != "not_allowed":
            continue
        pts = [(float(xy[1]), float(xy[2])) for xy in find(find(zone, "polygon"), "pts")[1:]]
        cx = [p[0] for p in pts]
        cy = [p[1] for p in pts]
        if min(cy) < gnd_top:       # the antenna keep-out, already handled
            continue
        corridors.append((min(cx), min(cy), max(cx), max(cy)))

    antenna = None
    for fp in find_all(pcb, "footprint"):
        poly = find(fp, "fp_poly")
        if poly is None:
            continue
        at = find(fp, "at")
        origin = (float(at[1]), float(at[2]))
        rot = float(at[3]) if len(at) > 3 else 0.0
        pts = []
        for xy in find(poly, "pts")[1:]:
            rx, ry = rotate((float(xy[1]), float(xy[2])), -rot)
            pts.append((origin[0] + rx, origin[1] + ry))
        feed_pad = next(p for p in find_all(fp, "pad") if str(p[1]) == "1")
        pad_at = find(feed_pad, "at")
        frx, fry = rotate((float(pad_at[1]), float(pad_at[2])), -rot)
        antenna = dict(points=drop_keyholes(pts),
                       feed=(origin[0] + frx, origin[1] + fry),
                       net=nets[int(find(feed_pad, "net")[1])])
    if antenna is None:
        raise SystemExit("no antenna footprint (one with an fp_poly) found on the board")

    feed = [((float(find(s, "start")[1]), float(find(s, "start")[2])),
             (float(find(s, "end")[1]), float(find(s, "end")[2])),
             float(find(s, "width")[1]))
            for s in find_all(pcb, "segment")
            if nets[int(find(s, "net")[1])] == antenna["net"]
            and str(find(s, "layer")[1]) == "F.Cu"]
    launch = min((p for seg in feed for p in seg[:2]), key=lambda p: p[0])
    return dict(outline=outline, substrate=substrate, gnd_top=gnd_top,
                corridors=corridors, antenna=antenna,
                feed=order_path(feed, launch), launch=launch)


def to_sim(board: dict) -> dict:
    """KiCad board coordinates (y down) -> simulation coordinates (y up)."""
    x0, y0, x1, y1 = board["outline"]

    def conv(pt):
        return (pt[0] - x0, y1 - pt[1])

    def conv_rect(rect):
        ax, ay = conv((rect[0], rect[1]))
        bx, by = conv((rect[2], rect[3]))
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))

    feed = [(conv(a), conv(b), w) for a, b, w in board["feed"]]
    # the port replaces the connector, so start the line at the board edge it
    # launches from, whichever edge and direction that is
    (ax, ay), (bx, by), w = feed[0]
    span_x, span_y = x1 - x0, y1 - y0
    if abs(ay - by) < 1e-6:                                  # launches along x
        feed[0] = ((0.0 if ax < span_x / 2 else span_x, ay), (bx, by), w)
    elif abs(ax - bx) < 1e-6:                                # launches along y
        feed[0] = ((ax, 0.0 if ay < span_y / 2 else span_y), (bx, by), w)
    return dict(width=x1 - x0, height=y1 - y0,
                substrate=board["substrate"],
                gnd_height=y1 - board["gnd_top"],
                corridors=[conv_rect(r) for r in board["corridors"]],
                antenna=[conv(p) for p in board["antenna"]["points"]],
                feed_point=conv(board["antenna"]["feed"]), feed=feed)


def pour_boxes(rect, corridors):
    """The pour rectangle cut into boxes that avoid the keep-away corridors."""
    x0, y0, x1, y1 = rect
    xs = sorted({x0, x1} | {v for c in corridors for v in (c[0], c[2]) if x0 < v < x1})
    ys = sorted({y0, y1} | {v for c in corridors for v in (c[1], c[3]) if y0 < v < y1})
    out = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            cx, cy = (xs[i] + xs[i + 1]) / 2, (ys[j] + ys[j + 1]) / 2
            if not any(c[0] <= cx <= c[2] and c[1] <= cy <= c[3] for c in corridors):
                out.append((xs[i], ys[j], xs[i + 1], ys[j + 1]))
    return out


def track_polygon(a, b, width):
    """A track as a rectangle; the mesher staircases the 45 degree corner."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    return [(a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny),
            (b[0] - nx, b[1] - ny), (a[0] - nx, a[1] - ny)]


# ----------------------------------------------------------------- the model
def build(geo: dict, resolution: float, air: float):
    from CSXCAD import ContinuousStructure
    from openEMS import openEMS

    h = geo["substrate"]["h"]
    er, tand = geo["substrate"]["er"], geo["substrate"]["tand"]
    w, d = geo["width"], geo["height"]

    fdtd = openEMS(NrTS=120000, EndCriteria=1e-4)
    fdtd.SetGaussExcite(F0, FC)
    fdtd.SetBoundaryCond(["MUR"] * 6)

    csx = ContinuousStructure()
    fdtd.SetCSX(csx)
    mesh = csx.GetGrid()
    mesh.SetDeltaUnit(1e-3)

    metal = csx.AddMetal("copper")
    sub = csx.AddMaterial("FR4", epsilon=er,
                          kappa=2 * math.pi * F0 * EPS0 * er * tand)
    sub.AddBox([0, 0, 0], [w, d, h], priority=0)

    # bottom side: the reference plane, stopping at the antenna keep-out
    metal.AddBox([0, 0, 0], [w, geo["gnd_height"], 0], priority=10)

    # top side: the same pour, minus the keep-away corridors round the feed
    for x0, y0, x1, y1 in pour_boxes((0, 0, w, geo["gnd_height"]), geo["corridors"]):
        metal.AddBox([x0, y0, h], [x1, y1, h], priority=10)

    # the routed 50 ohm feed; the first millimetres are the port
    (ax, ay), (bx, by), line_w = geo["feed"][0]
    port_len = max(4.0, 5 * h)
    if abs(ay - by) < 1e-6:                                  # launches along x
        step = port_len if bx > ax else -port_len
        start = [ax, ay - line_w / 2, h]
        stop = [ax + step, ay + line_w / 2, 0]
        axis, hand_off = "x", (ax + step, ay)
    else:                                                    # launches along y
        step = port_len if by > ay else -port_len
        start = [ax - line_w / 2, ay, h]
        stop = [ax + line_w / 2, ay + step, 0]
        axis, hand_off = "y", (ax, ay + step)
    port = fdtd.AddMSLPort(1, metal, start, stop, axis, "z", excite=-1,
                           FeedShift=10 * resolution,
                           MeasPlaneShift=port_len / 2,
                           priority=15)
    rest = [(hand_off, (bx, by), line_w)] + geo["feed"][1:]
    for a, b, width in rest:
        poly = [c for pt in track_polygon(a, b, width) for c in pt]
        metal.AddPolygon(poly, "z", h, priority=15)

    # antenna copper
    metal.AddPolygon([c for pt in geo["antenna"] for c in pt], "z", h, priority=15)

    # mesh: thirds rule at every copper edge, coarse out in the air box
    xs, ys = {0.0, w}, {0.0, d, geo["gnd_height"]}
    for a, b, width in geo["feed"]:
        for pt, other in ((a, b), (b, a)):
            xs |= {pt[0], pt[0] - width / 2, pt[0] + width / 2}
            ys |= {pt[1], pt[1] - width / 2, pt[1] + width / 2}
    for x0, y0, x1, y1 in geo["corridors"]:
        xs |= {x0, x1}
        ys |= {y0, y1}
    for px, py in geo["antenna"]:
        xs.add(px)
        ys.add(py)
    for edge in sorted(xs):
        mesh.AddLine("x", [edge - resolution / 3, edge + 2 * resolution / 3])
    for edge in sorted(ys):
        mesh.AddLine("y", [edge - resolution / 3, edge + 2 * resolution / 3])
    mesh.AddLine("x", [-air, w + air])
    mesh.AddLine("y", [-air, d + air])
    mesh.AddLine("z", [-air, 0, h / 2, h, h + air])
    coarse = C0 / (F0 + FC) / math.sqrt(er) * 1e3 / 20
    for axis in "xyz":
        mesh.SmoothMeshLines(axis, coarse)

    nf2ff = fdtd.CreateNF2FFBox()
    return fdtd, port, nf2ff


def report(port, nf2ff, sim_path, freq, plot=False):
    import numpy as np

    port.CalcPort(sim_path, freq, ref_impedance=50)
    s11 = port.uf_ref / port.uf_inc
    s11_db = 20 * np.log10(np.abs(s11))
    zin = port.uf_tot / port.if_tot

    best = int(np.argmin(s11_db))
    print(f"\nresonance      : {freq[best] / 1e9:.3f} GHz at {s11_db[best]:.1f} dB")
    for f_mark in (2.400e9, 2.442e9, 2.4835e9):
        i = int(np.argmin(np.abs(freq - f_mark)))
        print(f"  {freq[i] / 1e9:.4f} GHz : S11 {s11_db[i]:6.1f} dB   "
              f"Zin {zin[i].real:5.1f} {zin[i].imag:+5.1f}j ohm")
    band = freq[s11_db <= -10]
    if band.size:
        print(f"-10 dB band    : {band.min() / 1e9:.3f} - {band.max() / 1e9:.3f} GHz "
              f"({(band.max() - band.min()) / 1e6:.0f} MHz)")
    else:
        print("-10 dB band    : none - check the plane edge and the keep-out")

    theta = np.arange(-180, 180.1, 2.0)
    ff = nf2ff.CalcNF2FF(sim_path, freq[best], theta, [0, 90], center=[0, 0, 0])
    print(f"directivity    : {10 * np.log10(ff.Dmax[0]):.1f} dBi at "
          f"{freq[best] / 1e9:.3f} GHz")

    out = pathlib.Path("s11_openems.csv")
    out.write_text("freq_Hz,s11_dB,Rin_ohm,Xin_ohm\n" + "".join(
        f"{f:.0f},{s:.3f},{z.real:.3f},{z.imag:.3f}\n"
        for f, s, z in zip(freq, s11_db, zin)))
    print(f"wrote          : {out}")

    if plot:
        import matplotlib.pyplot as plt
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7, 7))
        ax1.plot(freq / 1e9, s11_db)
        ax1.axhline(-10, ls="--", lw=0.8)
        ax1.set(xlabel="f [GHz]", ylabel="S11 [dB]", title="SWRA117D 2.45 GHz IFA")
        ax1.grid(True)
        ax2.plot(freq / 1e9, zin.real, label="R")
        ax2.plot(freq / 1e9, zin.imag, label="X")
        ax2.set(xlabel="f [GHz]", ylabel="Zin [ohm]")
        ax2.grid(True)
        ax2.legend()
        fig.tight_layout()
        plt.show()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the geometry taken from the board and stop")
    ap.add_argument("--plot", action="store_true", help="show S11 and impedance plots")
    ap.add_argument("--resolution", type=float, default=0.25,
                    help="mesh resolution on the copper [mm]")
    ap.add_argument("--air", type=float, default=30.0,
                    help="air box around the board [mm]")
    ap.add_argument("--sim-path", default=os.path.join(tempfile.gettempdir(), "swra117d_fdtd"))
    args = ap.parse_args()

    geo = to_sim(load_board(PCB))
    sub = geo["substrate"]
    print(f"board          : {geo['width']:.1f} x {geo['height']:.1f} mm, "
          f"{sub['h']} mm FR4 (er {sub['er']}, tan d {sub['tand']})")
    print(f"ground plane   : y = 0 .. {geo['gnd_height']:.2f} mm "
          f"(antenna region {geo['gnd_height']:.2f} .. {geo['height']:.1f} mm is clear)")
    length = sum(math.dist(a, b) for a, b, _w in geo["feed"])
    (ax, ay), (bx, by), _w = geo["feed"][0]
    axis = "x" if abs(ay - by) < 1e-6 else "y"
    print(f"feed line      : {len(geo['feed'])} segments, {length:.1f} mm total, "
          f"port launches along {axis} from ({ax:.2f}, {ay:.2f}) mm, "
          f"feed pad at ({geo['feed_point'][0]:.2f}, {geo['feed_point'][1]:.2f}) mm")
    for a, b, width in geo["feed"]:
        print(f"                 ({a[0]:6.2f},{a[1]:6.2f}) -> "
              f"({b[0]:6.2f},{b[1]:6.2f})  w = {width} mm")
    boxes = pour_boxes((0, 0, geo["width"], geo["gnd_height"]), geo["corridors"])
    print(f"top pour       : {len(boxes)} boxes around "
          f"{len(geo['corridors'])} keep-away corridors")
    ax = [p[0] for p in geo["antenna"]]
    ay = [p[1] for p in geo["antenna"]]
    print(f"antenna copper : {len(geo['antenna'])} vertices, "
          f"x {min(ax):.2f}..{max(ax):.2f} mm, y {min(ay):.2f}..{max(ay):.2f} mm")
    if args.dry_run:
        return

    import numpy as np
    fdtd, port, nf2ff = build(geo, args.resolution, args.air)
    os.makedirs(args.sim_path, exist_ok=True)
    fdtd.Run(args.sim_path, verbose=3, cleanup=True)
    report(port, nf2ff, args.sim_path, np.linspace(F0 - FC, F0 + FC, 401), args.plot)


if __name__ == "__main__":
    main()
