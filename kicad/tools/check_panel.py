#!/usr/bin/env python3
"""Check the fabrication panel against the boards it was made from.

A panel is a merge, and merges go wrong quietly: a reference that appears
three times makes the pick-and-place file ambiguous, three ground nets merged
into one tells DRC the boards are connected, duplicated uuids make KiCad
behave strangely, and a board outline left on Edge.Cuts makes the fab cut the
panel up before shipping it.  None of that is visible at a glance.

Everything here is read back out of the written panel and compared against the
source boards, so the checks fail if the merge drifts.

    python3 kicad/tools/check_panel.py
"""

from __future__ import annotations

import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_kit as kit  # noqa: E402
import gen_panel as panel  # noqa: E402
from sexpr import find, find_all, find_deep, parse  # noqa: E402

PANEL = panel.OUT_DIR / f"{panel.PROJECT}.kicad_pcb"
MIN_VSCORE_CLEAR = 0.5       # copper to a V-score line, what fabs ask for

problems: list[str] = []
notes: list[str] = []


def fail(msg):
    problems.append(msg)


def ok(msg):
    notes.append(msg)


def copper_points(pcb):
    """Every absolute copper coordinate, with the object it belongs to."""
    out = []
    for fp in find_all(pcb, "footprint"):
        at = find(fp, "at")
        ox, oy = float(at[1]), float(at[2])
        ref = next((str(p[2]) for p in find_all(fp, "property")
                    if str(p[1]) == "Reference"), "?")
        for pad in find_all(fp, "pad"):
            pat, size = find(pad, "at"), find(pad, "size")
            w, h = float(size[1]), float(size[2])
            r = max(w, h) / 2
            out.append((ox + float(pat[1]), oy + float(pat[2]), r, ref))
        for poly in find_all(fp, "fp_poly"):
            if str(find(poly, "layer")[1]) not in ("F.Cu", "B.Cu"):
                continue
            for xy in find(poly, "pts")[1:]:
                out.append((ox + float(xy[1]), oy + float(xy[2]), 0.0, ref))
    for sg in find_all(pcb, "segment"):
        w = float(find(sg, "width")[1]) / 2
        for tag in ("start", "end"):
            p = find(sg, tag)
            out.append((float(p[1]), float(p[2]), w, "track"))
    for v in find_all(pcb, "via"):
        at = find(v, "at")
        out.append((float(at[1]), float(at[2]),
                    float(find(v, "size")[1]) / 2, "via"))
    for z in find_all(pcb, "zone"):
        if find(z, "keepout"):
            continue
        for xy in find(find(z, "polygon"), "pts")[1:]:
            out.append((float(xy[1]), float(xy[2]), 0.0, "pour"))
    return out


def main() -> int:
    if not PANEL.exists():
        print(f"missing {PANEL} - run tools/gen_panel.py")
        return 1
    pcb = parse(PANEL.read_text())
    specs = {s["key"]: s for s in kit.all_specs()}
    width = specs[panel.ORDER[0]]["board_w"]
    height = specs[panel.ORDER[0]]["board_h"]
    n = len(panel.ORDER)
    px, py = panel.PANEL_ORIGIN

    # --- the outline is the panel's, and only the panel's -------------------
    edges = [g for g in find_all(pcb, "gr_line")
             if str(find(g, "layer")[1]) == "Edge.Cuts"]
    pts = [(float(find(g, t)[1]), float(find(g, t)[2]))
           for g in edges for t in ("start", "end")]
    if len(edges) != 4:
        fail(f"panel: {len(edges)} Edge.Cuts lines, not 4 - a board outline "
             "was left in, and the fab will cut the panel apart")
    elif pts:
        w = max(p[0] for p in pts) - min(p[0] for p in pts)
        h = max(p[1] for p in pts) - min(p[1] for p in pts)
        if abs(w - n * width) > 0.01 or abs(h - height) > 0.01:
            fail(f"panel: outline is {w:.2f} x {h:.2f} mm, not "
                 f"{n * width:g} x {height:g}")
        else:
            ok(f"panel: one outline, {w:g} x {h:g} mm, {n} up")

    # --- the V-score lines --------------------------------------------------
    scores = [g for g in find_all(pcb, "gr_line")
              if str(find(g, "layer")[1]) == panel.VSCORE_LAYER
              and abs(float(find(g, "start")[1]) - float(find(g, "end")[1])) < 1e-6]
    want = [px + i * width for i in range(1, n)]
    got = sorted(float(find(g, "start")[1]) for g in scores)
    if len(got) != n - 1 or any(abs(a - b) > 0.01 for a, b in zip(got, want)):
        fail(f"panel: V-score lines at {got}, expected {want}")
    else:
        for g in scores:
            span = abs(float(find(g, "end")[2]) - float(find(g, "start")[2]))
            if abs(span - height) > 0.01:
                fail(f"panel: a V-score line spans {span:.2f} mm, not the "
                     f"full {height:g} mm - V-score must run edge to edge")
        ok(f"panel: {len(scores)} V-score lines, edge to edge, on "
           f"{panel.VSCORE_LAYER}")

    # --- references and uuids are unique ------------------------------------
    refs = [str(p[2]) for fp in find_all(pcb, "footprint")
            for p in find_all(fp, "property") if str(p[1]) == "Reference"]
    dupes = [r for r, c in collections.Counter(refs).items() if c > 1]
    if dupes:
        fail(f"panel: {len(dupes)} reference(s) appear more than once "
             f"({', '.join(sorted(dupes)[:4])}) - the position file cannot "
             "say which board a part is on")
    else:
        ok(f"panel: {len(refs)} references, all unique "
           f"({', '.join(sorted(refs)[:3])} ...)")
    # find_all searches direct children only, and every uuid in this file is
    # nested inside a footprint, a track or a zone.  Asking it for uuids at
    # the top level returns an empty list, and an empty list has no
    # duplicates - which is how this check passed while testing nothing.
    uids = [str(u[1]) for u in find_deep(pcb, "uuid")]
    dupes = [u for u, c in collections.Counter(uids).items() if c > 1]
    if dupes:
        fail(f"panel: {len(dupes)} duplicated uuid(s) - three copies of one "
             "board carry three copies of every identifier")
    else:
        ok(f"panel: {len(uids)} uuids, all unique")

    # --- nets stay separate -------------------------------------------------
    nets = {int(x[1]): str(x[2]) for x in pcb
            if isinstance(x, list) and str(x[0]) == "net"}
    per_board = collections.Counter(
        name.rsplit("_", 1)[-1] for num_, name in nets.items() if name)
    if sorted(per_board) != sorted(panel.PREFIX[k] for k in panel.ORDER):
        fail(f"panel: net suffixes are {sorted(per_board)}, expected one set "
             f"per board")
    elif len(set(per_board.values())) != 1:
        fail(f"panel: the boards do not have the same nets: {dict(per_board)}")
    else:
        ok(f"panel: {len(nets) - 1} nets in {len(per_board)} separate sets "
           f"({per_board[panel.PREFIX[panel.ORDER[0]]]} each), so no two "
           "boards share a net")

    # --- every board's content arrived, in its own slot ---------------------
    points = copper_points(pcb)
    worst = None
    for x, y, r, who in points:
        if x - r < px - 1e-6 or x + r > px + n * width + 1e-6 \
                or y - r < py - 1e-6 or y + r > py + height + 1e-6:
            fail(f"panel: copper of {who} at ({x:.2f}, {y:.2f}) is outside "
                 "the panel outline")
        for line in want:
            gap = abs(x - line) - r
            worst = gap if worst is None else min(worst, gap)
            if gap < MIN_VSCORE_CLEAR:
                fail(f"panel: copper of {who} is {gap:.2f} mm from a V-score "
                     f"line; {MIN_VSCORE_CLEAR} mm is the usual minimum")
    counts = collections.Counter()
    for fp in find_all(pcb, "footprint"):
        ox = float(find(fp, "at")[1])
        counts[min(int((ox - px) // width), n - 1)] += 1
    source = {}
    for key in panel.ORDER:
        src = parse((panel.PRJ_DIR / "kit" / key / f"kit_{key}.kicad_pcb").read_text())
        source[key] = len(find_all(src, "footprint"))
    for i, key in enumerate(panel.ORDER):
        if counts[i] != source[key]:
            fail(f"panel: slot {i} has {counts[i]} footprints, {key} has "
                 f"{source[key]}")
    if worst is not None:
        ok(f"panel: every board's footprints present and inside its slot, "
           f"closest copper to a V-score line {worst:.2f} mm")

    for line in notes:
        print(f"ok   {line}")
    for line in problems:
        print(f"FAIL {line}")
    print(f"\n{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
