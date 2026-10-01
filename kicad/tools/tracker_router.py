"""Ground fan-out and power routing for the football tracker's board.

Two jobs the generator hands over, so the person routing in KiCad starts
with the tedious part done:

  * **GND fan-out**: a via beside every top-layer GND pad, joined to it by a
    short track, so each ground pin reaches the In1/In2 planes directly
    instead of through whatever the top pour happens to leave.
  * **Power nets**: VBUS, VBAT, VSYS and +3V3, every pad, as tracks.

The router is a plain A* maze router on a 0.1 mm grid over F.Cu and B.Cu,
with vias between them.  Obstacles are the board's own copper - pads,
tracks, vias, holes - inflated by the net classes' clearance plus half the
track width plus a discretisation margin, and the keep-outs.  The two inner
layers are never routed: they are the GND planes the RF feed relies on.

``check_tracker.py`` re-checks everything this writes, with its own geometry.
Needs numpy.
"""

from __future__ import annotations

import heapq
import math

import numpy as np

GRID = 0.1
# a segment between two free cell centres strays up to half a diagonal step
# from both of them
MARGIN = GRID * math.sqrt(2) / 2 + 0.005
VIA_SIZE, VIA_DRILL = 0.6, 0.3
HOLE_CLEARANCE = 0.15
EDGE_CLEARANCE = 0.2
LAYERS = ("F.Cu", "B.Cu")


class Copper:
    """Everything on the board that a new track or via must keep clear of."""

    def __init__(self, width, height, clearance, default_clearance):
        self.w, self.h = width, height
        self.clearance = clearance            # net -> netclass clearance
        self.default = default_clearance
        self.pads = []                        # (box, layers, net)
        self.holes = []                       # (centre, radius)
        self.segs = []                        # (a, b, width, layer, net)
        self.vias = []                        # (centre, net)
        self.keepouts = []                    # (box, layers, no_tracks, no_vias)

    def clr(self, a, b):
        return max(self.clearance.get(a, self.default), self.clearance.get(b, self.default))

    # ------------------------------------------------------------ queries
    def point_clear(self, p, radius, net, layer):
        """Is a disc of *radius* at *p* on *layer* clear of other nets?"""
        for box, layers, n in self.pads:
            if n == net and n is not None:
                continue
            if layer in layers and rect_dist(p, box) < radius + self.clr(net, n):
                return False
        for a, b, w, lay, n in self.segs:
            if n != net and lay == layer and seg_dist(p, a, b) < radius + w / 2 + self.clr(net, n):
                return False
        for c, n in self.vias:
            if n != net and math.dist(p, c) < radius + VIA_SIZE / 2 + self.clr(net, n):
                return False
        for c, r in self.holes:
            if math.dist(p, c) < radius + r + HOLE_CLEARANCE:
                return False
        return True

    def seg_clear(self, a, b, width, net, layer, steps=None):
        n = steps or max(2, int(math.dist(a, b) / 0.02) + 1)
        for i in range(n + 1):
            t = i / n
            p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            if not self.point_clear(p, width / 2, net, layer) or self.in_keepout(p, width / 2, layer):
                return False
            if not (EDGE_CLEARANCE + width / 2 <= p[0] <= self.w - EDGE_CLEARANCE - width / 2
                    and EDGE_CLEARANCE + width / 2 <= p[1] <= self.h - EDGE_CLEARANCE - width / 2):
                return False
        return True

    def via_clear(self, p, net):
        r = VIA_SIZE / 2
        if not (EDGE_CLEARANCE + r <= p[0] <= self.w - EDGE_CLEARANCE - r
                and EDGE_CLEARANCE + r <= p[1] <= self.h - EDGE_CLEARANCE - r):
            return False
        for c, n in self.vias:            # same net too: drills need room
            if math.dist(p, c) < VIA_SIZE + (0.25 if n == net else self.clr(net, n)):
                return False
        for box, layers, no_tracks, no_vias in self.keepouts:
            if no_vias and rect_dist(p, box) < r:
                return False
        return all(self.point_clear(p, r, net, layer) for layer in LAYERS)

    def via_clear_ignoring_keepouts(self, p, net):
        """For stitching: the caller decides where vias may go."""
        saved, self.keepouts = self.keepouts, []
        try:
            return self.via_clear(p, net)
        finally:
            self.keepouts = saved

    def in_keepout(self, p, radius, layer):
        return any(no_tracks and layer in layers and rect_dist(p, box) < radius
                   for box, layers, no_tracks, _ in self.keepouts)

    # ------------------------------------------------------------- raster
    def blocked(self, net, width, layer):
        """Grid of cells a track centre of *width* on *layer* may not occupy."""
        nx, ny = int(round(self.w / GRID)) + 1, int(round(self.h / GRID)) + 1
        xs = np.arange(nx) * GRID
        ys = np.arange(ny) * GRID
        out = np.zeros((nx, ny), dtype=bool)
        half = width / 2
        edge = EDGE_CLEARANCE + half + MARGIN
        out[xs < edge, :] = True
        out[xs > self.w - edge, :] = True
        out[:, ys < edge] = True
        out[:, ys > self.h - edge] = True

        def window(x0, y0, x1, y1):
            i0, i1 = max(0, int((x0) / GRID)), min(nx, int(x1 / GRID) + 2)
            j0, j1 = max(0, int((y0) / GRID)), min(ny, int(y1 / GRID) + 2)
            return i0, i1, j0, j1

        def mark_rect(box, grow):
            i0, i1, j0, j1 = window(box[0] - grow, box[1] - grow, box[2] + grow, box[3] + grow)
            if i0 >= i1 or j0 >= j1:
                return
            gx = xs[i0:i1, None]
            gy = ys[None, j0:j1]
            dx = np.maximum(np.maximum(box[0] - gx, gx - box[2]), 0)
            dy = np.maximum(np.maximum(box[1] - gy, gy - box[3]), 0)
            out[i0:i1, j0:j1] |= np.hypot(dx, dy) < grow

        def mark_seg(a, b, grow):
            i0, i1, j0, j1 = window(min(a[0], b[0]) - grow, min(a[1], b[1]) - grow,
                                    max(a[0], b[0]) + grow, max(a[1], b[1]) + grow)
            if i0 >= i1 or j0 >= j1:
                return
            gx = xs[i0:i1, None]
            gy = ys[None, j0:j1]
            vx, vy = b[0] - a[0], b[1] - a[1]
            ll = vx * vx + vy * vy
            t = np.zeros_like(gx * gy) if ll == 0 else np.clip(
                ((gx - a[0]) * vx + (gy - a[1]) * vy) / ll, 0, 1)
            out[i0:i1, j0:j1] |= np.hypot(gx - (a[0] + t * vx), gy - (a[1] + t * vy)) < grow

        for box, layers, n in self.pads:
            if (n != net or n is None) and layer in layers:
                mark_rect(box, half + self.clr(net, n) + MARGIN)
        for a, b, w, lay, n in self.segs:
            if n != net and lay == layer:
                mark_seg(a, b, half + w / 2 + self.clr(net, n) + MARGIN)
        for c, n in self.vias:
            if n != net:
                mark_seg(c, c, half + VIA_SIZE / 2 + self.clr(net, n) + MARGIN)
        for c, r in self.holes:
            mark_seg(c, c, half + r + HOLE_CLEARANCE + MARGIN)
        for box, layers, no_tracks, _ in self.keepouts:
            if no_tracks and layer in layers:
                mark_rect(box, half + MARGIN)
        return out


def rect_dist(p, box):
    dx = max(box[0] - p[0], p[0] - box[2], 0.0)
    dy = max(box[1] - p[1], p[1] - box[3], 0.0)
    return math.hypot(dx, dy)


def seg_dist(p, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    ll = vx * vx + vy * vy
    t = 0.0 if ll == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / ll))
    return math.dist(p, (a[0] + t * vx, a[1] + t * vy))


# ------------------------------------------------------------------ fan-out
def fanout(copper, gnd_pads, centre_of):
    """A via beside each GND pad, and the track to it.

    *gnd_pads* are (ref, box, layers); *centre_of* maps a ref to its
    footprint centre, so the first direction tried is away from the part.
    Returns (tracks, vias) and records both in *copper*.
    """
    tracks, vias = [], []
    for ref, box, layers in gnd_pads:
        if "F.Cu" not in layers:
            continue
        pc = ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)
        # a via already standing in this pad serves it.  Merely overlapping
        # the pad does not: KiCad joins a via to a pad only when the via's
        # centre lies inside the pad.
        if any(rect_dist(c, box) == 0.0 for c, n in copper.vias if n == "GND"):
            continue
        cx, cy = centre_of[ref]
        away = math.atan2(pc[1] - cy, pc[0] - cx)
        width = min(0.3, box[2] - box[0], box[3] - box[1])
        done = False
        # a GND via already within reach: a track to it is enough
        for c, n in sorted(copper.vias, key=lambda v: math.dist(v[0], pc)):
            if n != "GND" or math.dist(c, pc) > 2.0:
                continue
            if copper.seg_clear(pc, c, width, "GND", "F.Cu"):
                tracks.append((pc, c, width, "F.Cu", "GND"))
                copper.segs.append((pc, c, width, "F.Cu", "GND"))
                done = True
                break
        if done:
            continue
        for k in range(16):
            ang = away + (k + 1) // 2 * (math.pi / 8) * (1 if k % 2 else -1)
            ux, uy = math.cos(ang), math.sin(ang)
            reach = abs(ux) * (box[2] - box[0]) / 2 + abs(uy) * (box[3] - box[1]) / 2
            for extra in np.arange(0.0, 2.6, 0.1):
                d = reach + VIA_SIZE / 2 + 0.2 + extra
                v = (round(pc[0] + ux * d, 3), round(pc[1] + uy * d, 3))
                if not copper.via_clear(v, "GND"):
                    continue
                if not copper.seg_clear(pc, v, width, "GND", "F.Cu"):
                    continue
                tracks.append((pc, v, width, "F.Cu", "GND"))
                vias.append(v)
                copper.segs.append((pc, v, width, "F.Cu", "GND"))
                copper.vias.append((v, "GND"))
                done = True
                break
            if done:
                break
    return tracks, vias


# ------------------------------------------------------------------- router
def _cells_in(box, nx, ny):
    i0, i1 = max(0, math.ceil(box[0] / GRID)), min(nx - 1, math.floor(box[2] / GRID))
    j0, j1 = max(0, math.ceil(box[1] / GRID)), min(ny - 1, math.floor(box[3] / GRID))
    return [(i, j) for i in range(i0, i1 + 1) for j in range(j0, j1 + 1)]


def route_net(copper, net, pads, widths=(0.4, 0.25, 0.2), via_cost=25,
              layer_cost=(1.25, 1.0)):
    """Connect every pad of *net* into one tree.  Returns (tracks, vias, failed).

    *pads* are (name, box, layers).  Bottom copper costs less than top, so
    the long runs go underneath and leave the top for signals; a via costs
    *via_cost* grid steps.
    """
    nx, ny = int(round(copper.w / GRID)) + 1, int(round(copper.h / GRID)) + 1
    tracks, vias, failed = [], [], []
    masks = {}

    def mask(width, layer):
        key = (width, layer)
        if key not in masks:
            masks[key] = copper.blocked(net, width, layer)
        return masks[key]

    via_ok_cache = {}

    def via_ok(i, j):
        if (i, j) not in via_ok_cache:
            via_ok_cache[(i, j)] = copper.via_clear((i * GRID, j * GRID), net)
        return via_ok_cache[(i, j)]

    # tree: pad cells of the first pad
    order = sorted(pads, key=lambda p: (p[1][0], p[1][1]))
    tree = {}                               # (layer_index, i, j) -> True
    remaining = list(order)

    def add_pad(p):
        for li, layer in enumerate(LAYERS):
            if layer in p[2] or "*.Cu" in p[2]:
                for c in _cells_in(p[1], nx, ny):
                    tree[(li,) + c] = True

    add_pad(remaining.pop(0))
    while remaining:
        # nearest unconnected pad to the tree
        tpts = list(tree)
        def gap(p):
            cx, cy = (p[1][0] + p[1][2]) / 2 / GRID, (p[1][1] + p[1][3]) / 2 / GRID
            return min((t[1] - cx) ** 2 + (t[2] - cy) ** 2 for t in tpts[::7] or tpts)
        remaining.sort(key=gap)
        target = remaining.pop(0)
        path = None
        for width in widths:
            path = _astar(tree, target, width, mask, via_ok, nx, ny, via_cost, layer_cost)
            if path:
                break
        if not path:
            failed.append(target[0])
            add_pad(target)                 # keep going for the others
            continue
        segs, new_vias = _smooth(path, [mask(width, l) for l in LAYERS])
        for a, b, layer in segs:
            tracks.append((a, b, width, layer, net))
            copper.segs.append((a, b, width, layer, net))
        for v in new_vias:
            vias.append(v)
            copper.vias.append((v, net))
        # branch points: cells on the copper actually laid, not on the A* path
        for a, b, layer in segs:
            li = LAYERS.index(layer)
            n = max(1, int(math.dist(a, b) / GRID))
            for k in range(n + 1):
                x = a[0] + (b[0] - a[0]) * k / n
                y = a[1] + (b[1] - a[1]) * k / n
                tree[(li, int(round(x / GRID)), int(round(y / GRID)))] = True
        for v in new_vias:
            for li in range(len(LAYERS)):
                tree[(li, int(round(v[0] / GRID)), int(round(v[1] / GRID)))] = True
        add_pad(target)
        # this net's own copper does not block it; other nets are unchanged
    return tracks, vias, failed


def _astar(tree, target, width, mask, via_ok, nx, ny, via_cost, layer_cost):
    goal = set()
    for li, layer in enumerate(LAYERS):
        if layer in target[2] or "*.Cu" in target[2]:
            m = mask(width, layer)
            for c in _cells_in(target[1], nx, ny):
                if not m[c]:
                    goal.add((li,) + c)
    if not goal:
        return None
    gx = sum(g[1] for g in goal) / len(goal)
    gy = sum(g[2] for g in goal) / len(goal)
    masks = [mask(width, layer) for layer in LAYERS]

    def h(s):
        return math.hypot(s[1] - gx, s[2] - gy) * min(layer_cost)

    openq, came, cost = [], {}, {}
    for s in tree:
        if not masks[s[0]][s[1], s[2]]:
            cost[s] = 0.0
            came[s] = None
            heapq.heappush(openq, (h(s), 0.0, s))
    steps = [(1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
             (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)),
             (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2))]
    expanded = 0
    while openq:
        f, g, s = heapq.heappop(openq)
        if g > cost.get(s, math.inf):
            continue
        if s in goal:
            path = []
            while s is not None:
                path.append(s)
                s = came[s]
            return path[::-1]
        expanded += 1
        if expanded > 400000:
            return None
        li, i, j = s
        m = masks[li]
        for di, dj, step in steps:
            a, b = i + di, j + dj
            if not (0 <= a < nx and 0 <= b < ny) or m[a, b]:
                continue
            if di and dj and (m[i + di, j] or m[i, j + dj]):
                continue                    # no corner cutting
            n = (li, a, b)
            ng = g + step * layer_cost[li]
            if ng < cost.get(n, math.inf):
                cost[n], came[n] = ng, s
                heapq.heappush(openq, (ng + h(n), ng, n))
        o = 1 - li
        n = (o, i, j)
        if not masks[o][i, j] and via_ok(i, j):
            ng = g + via_cost
            if ng < cost.get(n, math.inf):
                cost[n], came[n] = ng, s
                heapq.heappush(openq, (ng + h(n), ng, n))
    return None


def _to_segments(path, width):
    segs, vias = [], []
    run = [path[0]]
    for s in path[1:]:
        prev = run[-1]
        if s[0] != prev[0]:
            _flush(run, segs)
            vias.append((round(s[1] * GRID, 3), round(s[2] * GRID, 3)))
            run = [s]
            continue
        if len(run) >= 2:
            d0 = (run[-1][1] - run[-2][1], run[-1][2] - run[-2][2])
            d1 = (s[1] - prev[1], s[2] - prev[2])
            if d0 != d1:
                _flush(run, segs)
                run = [prev]
        run.append(s)
    _flush(run, segs)
    return segs, vias


def _flush(run, segs):
    if len(run) < 2:
        return
    a, b = run[0], run[-1]
    segs.append(((round(a[1] * GRID, 3), round(a[2] * GRID, 3)),
                 (round(b[1] * GRID, 3), round(b[2] * GRID, 3)), LAYERS[a[0]]))


# ---------------------------------------------------------------- smoothing
def _free_line(m, a, b):
    """Every point of a->b sits on a free cell (cells already carry the margin)."""
    n = max(1, int(math.dist(a, b) / (GRID / 2)))
    for k in range(n + 1):
        x = a[0] + (b[0] - a[0]) * k / n
        y = a[1] + (b[1] - a[1]) * k / n
        if m[int(round(x)), int(round(y))]:
            return False
    return True


def _dogleg(m, a, b):
    """a->b as one straight or 45-degree run plus one straight run, if clear."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 or dy == 0 or abs(dx) == abs(dy):
        return [a, b]
    d = min(abs(dx), abs(dy))
    sx, sy = (1 if dx > 0 else -1), (1 if dy > 0 else -1)
    for knee in ((a[0] + sx * d, a[1] + sy * d), (b[0] - sx * d, b[1] - sy * d)):
        if _free_line(m, a, knee) and _free_line(m, knee, b):
            return [a, knee, b]
    return [a, b]


def _smooth(path, masks):
    """String-pull each single-layer run of the A* path, then make it 45-degree."""
    segs, vias = [], []
    runs, run = [], [path[0]]
    for s in path[1:]:
        if s[0] != run[-1][0]:
            runs.append(run)
            vias.append((round(s[1] * GRID, 3), round(s[2] * GRID, 3)))
            run = [s]
        else:
            run.append(s)
    runs.append(run)
    for run in runs:
        li = run[0][0]
        m = masks[li]
        pts = [(s[1], s[2]) for s in run]
        if len(pts) < 2:
            continue
        keep = [pts[0]]
        i = 0
        while i < len(pts) - 1:
            j = i + 1
            while j + 1 < len(pts) and _free_line(m, pts[i], pts[j + 1]):
                j += 1
            keep.append(pts[j])
            i = j
        corners = [keep[0]]
        for a, b in zip(keep, keep[1:]):
            corners += _dogleg(m, a, b)[1:]
        for a, b in zip(corners, corners[1:]):
            if a != b:
                segs.append(((round(a[0] * GRID, 3), round(a[1] * GRID, 3)),
                             (round(b[0] * GRID, 3), round(b[1] * GRID, 3)), LAYERS[li]))
    return segs, vias
