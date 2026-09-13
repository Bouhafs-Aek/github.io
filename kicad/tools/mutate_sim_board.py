#!/usr/bin/env python3
"""Mutation test for check_sim_board.py.

Break the simulation board one way at a time, in a scratch copy, and check
that the checker reports it.  A checker that has never failed is a checker
nobody has tested - and every rule below exists because the corresponding
mistake is easy to make and invisible in a plot.

    python3 kicad/tools/mutate_sim_board.py [scratch.kicad_pcb]
"""

from __future__ import annotations

import copy
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from sexpr import Sym, dumps, find, find_all, num, parse  # noqa: E402

PRJ_DIR = HERE.parent
CHECKER = HERE / "check_sim_board.py"
SRC = PRJ_DIR / "sim" / "board" / "swra117d_2g4_sim.kicad_pcb"
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
    pathlib.Path(tempfile.gettempdir()) / "swra117d_sim_mutant.kicad_pcb"
base = parse(SRC.read_text())

def zone(pcb, name):
    for z in find_all(pcb, 'zone'):
        n = find(z, 'name')
        if n is not None and str(n[1]) == name:
            return z

def zone_by_layer(pcb, layer):
    for z in find_all(pcb, 'zone'):
        l = find(z, 'layer')
        if l is not None and str(l[1]) == layer and not find(z, 'keepout'):
            return z

def add_connector(p):
    p.insert(-1, [Sym('footprint'), 'X:SMA',
                  [Sym('layer'), 'F.Cu'], [Sym('uuid'), 'x'],
                  [Sym('at'), num(124.0), num(89.0)]])

def add_track(p):
    p.insert(-1, [Sym('segment'), [Sym('start'), num(124.0), num(70.0)],
                  [Sym('end'), num(124.0), num(80.0)], [Sym('width'), num(2.95)],
                  [Sym('layer'), 'F.Cu'], [Sym('net'), Sym('2')], [Sym('uuid'), 'y']])

def drop_bottom_ground(p):
    p.remove(zone_by_layer(p, 'B.Cu'))

def shrink_bottom_ground(p):
    z = zone_by_layer(p, 'B.Cu')
    for xy in find(find(z, 'polygon'), 'pts')[1:]:
        xy[1] = num(float(xy[1]) - 3.0)

def drop_port_gap(p):
    p.remove(zone(p, 'RF_PORT_GAP'))

def close_port_gap(p):
    z = zone(p, 'RF_PORT_GAP')
    for xy in find(find(z, 'polygon'), 'pts')[1:]:
        if float(xy[2]) > 67.0:
            xy[2] = num(66.95)          # 0.2 mm gap: what KiCad's pour clearance leaves

def notch_stops_early(p):
    """Pour left touching the bar before the short pad: D5 is no longer 1.40 mm."""
    z = zone(p, 'RF_PORT_GAP')
    for xy in find(find(z, 'polygon'), 'pts')[1:]:
        if float(xy[1]) > 125.0:
            xy[1] = num(124.8)

def notch_misses_bar_end(p):
    z = zone(p, 'RF_PORT_GAP')
    for xy in find(find(z, 'polygon'), 'pts')[1:]:
        if float(xy[1]) < 124.0:
            xy[1] = num(123.7)

def port_gap_both_layers(p):
    find(zone(p, 'RF_PORT_GAP'), 'layers').append('B.Cu')

def strip_port_vias(p):
    for v in list(find_all(p, 'via')):
        at = find(v, 'at')
        if float(at[2]) < 68.0:
            p.remove(v)

def via_on_the_pad(p):
    """Move the via under the port up until it violates the pad clearance."""
    feed = next(pad for fp in find_all(p, 'footprint') if find(fp, 'fp_poly')
                for pad in find_all(fp, 'pad') if str(pad[1]) == '1')
    origin = find(next(fp for fp in find_all(p, 'footprint')
                       if find(fp, 'fp_poly')), 'at')
    fx = float(origin[1]) + float(find(feed, 'at')[1])
    fy = float(origin[2]) + float(find(feed, 'at')[2])
    v = min(find_all(p, 'via'),
            key=lambda v: abs(float(find(v, 'at')[1]) - fx))
    find(v, 'at')[2] = num(fy + 0.5)

def via_not_grounded(p):
    find(next(iter(find_all(p, 'via'))), 'net')[1] = Sym('0')

def via_top_layer_only(p):
    find(next(iter(find_all(p, 'via'))), 'layers')[2] = 'F.Cu'

def keepout_short(p):
    z = zone(p, 'ANTENNA_KEEPOUT')
    for xy in find(find(z, 'polygon'), 'pts')[1:]:
        if abs(float(xy[2]) - 66.25) < 1e-9:
            xy[2] = num(64.0)

MUTATIONS = [
    ('a connector footprint back in the model', add_connector),
    ('a feed track back in the model', add_track),
    ('the bottom ground plane deleted', drop_bottom_ground),
    ('the bottom ground plane smaller than the top pour', shrink_bottom_ground),
    ('the RF_PORT_GAP keep-out deleted', drop_port_gap),
    ('the port gap closed down to 0.2 mm', close_port_gap),
    ('the cut stopping short of the short pad (D5 broken)', notch_stops_early),
    ('the cut not clearing the left end of the bar', notch_misses_bar_end),
    ('RF_PORT_GAP cutting the bottom ground too', port_gap_both_layers),
    ('the vias at the port removed', strip_port_vias),
    ('a via moved onto the port pad', via_on_the_pad),
    ('a via left off the GND net', via_not_grounded),
    ('a via that does not reach B.Cu', via_top_layer_only),
    ('the antenna keep-out stopping short of the plane edge', keepout_short),
]

bad = 0
for label, mutate in MUTATIONS:
    p = copy.deepcopy(base)
    mutate(p)
    OUT.write_text(dumps(p) + '\n')
    r = subprocess.run([sys.executable, str(CHECKER), str(OUT)],
                       capture_output=True, text=True)
    caught = [l for l in r.stdout.splitlines() if l.startswith('FAIL')]
    if r.returncode == 0:
        bad += 1
        print(f'NOT CAUGHT  {label}')
    else:
        print(f'caught      {label}\n              {caught[0][5:][:110]}')
print(f'\n{len(MUTATIONS) - bad}/{len(MUTATIONS)} mutations caught')
sys.exit(1 if bad else 0)
