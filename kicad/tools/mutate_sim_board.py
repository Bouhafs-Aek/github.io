#!/usr/bin/env python3
"""Mutation test for check_sim_board.py.

Break the RFsim project one way at a time, in a scratch copy, and check that
the checker reports it.  A checker that has never failed is a checker nobody
has tested - and every rule below exists because the corresponding mistake is
easy to make and invisible in a plot.

Both files are copied to the scratch name, so the schematic checks run against
a real sheet rather than trivially failing on a missing one.

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
SRC_PCB = PRJ_DIR / "sim" / "board" / "swra117d_2g4_sim.kicad_pcb"
SRC_SCH = SRC_PCB.with_suffix(".kicad_sch")
OUT = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else \
    pathlib.Path(tempfile.gettempdir()) / "swra117d_sim_mutant.kicad_pcb"

base_pcb = parse(SRC_PCB.read_text())
base_sch = parse(SRC_SCH.read_text())


def zone(pcb, name):
    for z in find_all(pcb, "zone"):
        n = find(z, "name")
        if n is not None and str(n[1]) == name:
            return z


def pour(pcb, layer):
    for z in find_all(pcb, "zone"):
        node = find(z, "layer")
        if node is not None and str(node[1]) == layer and not find(z, "keepout"):
            return z


def longest_segment(pcb):
    return max(find_all(pcb, "segment"),
               key=lambda s: abs(float(find(s, "end")[2]) - float(find(s, "start")[2])))


# --------------------------------------------------------------- mutations
def land(pcb):
    for fp in find_all(pcb, "footprint"):
        if str(fp[1]).endswith("RF_Port_Land"):
            return fp


def add_connector(pcb, _sch):
    pcb.insert(-1, [Sym("footprint"), "X:SMA", [Sym("layer"), "F.Cu"],
                    [Sym("uuid"), "x"], [Sym("at"), num(124.0), num(89.0)]])


def drop_port_land(pcb, _sch):
    """No pad for RFsim to drive: it falls back to the antenna's own feed pad."""
    pcb.remove(land(pcb))


def drop_reference_pad(pcb, _sch):
    """The B.Cu pad gone: exactly the error RFsim reports by name."""
    fp = land(pcb)
    for pad in list(find_all(fp, "pad")):
        if "B.Cu" in [str(l) for l in find(pad, "layers")[1:]]:
            fp.remove(pad)


def narrow_reference_pad(pcb, _sch):
    """Ground pad narrower than the signal pad: the port overhangs its reference."""
    fp = land(pcb)
    pad = next(p for p in find_all(fp, "pad")
               if "B.Cu" in [str(l) for l in find(p, "layers")[1:]])
    find(pad, "size")[2] = num(1.0)


def coplanar_ground_at_the_port(pcb, _sch):
    """Ground tabs beside the signal pad: the launch is CPW, not microstrip."""
    fp = land(pcb)
    fp.insert(-1, [Sym("pad"), "2", Sym("smd"), Sym("rect"),
                   [Sym("at"), num(1.75), num(-4.975), num(90)],
                   [Sym("size"), num(3.5), num(3.0)],
                   [Sym("layers"), "F.Cu", "F.Paste", "F.Mask"],
                   [Sym("uuid"), "cop"], [Sym("net"), Sym("1"), "GND"]])


def delete_feed(pcb, _sch):
    for seg in list(find_all(pcb, "segment")):
        pcb.remove(seg)


def feed_off_the_port_pad(pcb, _sch):
    """The line stops short of the port land: RFsim drives a disconnected pad."""
    find(longest_segment(pcb), "start")[2] = num(84.0)


def feed_misses_the_pad(pcb, _sch):
    shortest = min(find_all(pcb, "segment"),
                   key=lambda s: float(find(s, "width")[1]))
    find(shortest, "end")[2] = num(67.2)


def feed_branches(pcb, _sch):
    """A stub off the line: RFsim would launch into whichever end it finds."""
    pcb.insert(-1, [Sym("segment"), [Sym("start"), num(124.0), num(80.0)],
                    [Sym("end"), num(130.0), num(80.0)], [Sym("width"), num(2.95)],
                    [Sym("layer"), "F.Cu"], [Sym("net"), Sym("2")],
                    [Sym("uuid"), "stub"]])


def drop_bottom_ground(pcb, _sch):
    pcb.remove(pour(pcb, "B.Cu"))


def shrink_bottom_ground(pcb, _sch):
    for xy in find(find(pour(pcb, "B.Cu"), "polygon"), "pts")[1:]:
        xy[1] = num(float(xy[1]) - 3.0)


def drop_pour_keepaway(pcb, _sch):
    pcb.remove(zone(pcb, "RF_POUR_KEEPAWAY"))


def strip_launch_vias(pcb, _sch):
    for v in list(find_all(pcb, "via")):
        if float(find(v, "at")[2]) > 84.0:
            pcb.remove(v)


def via_on_the_antenna_pad(pcb, _sch):
    """A via in the keep-out, where no copper of any layer is allowed."""
    find(next(iter(find_all(pcb, "via"))), "at")[2] = num(66.0)


def via_on_the_line(pcb, _sch):
    find(next(iter(find_all(pcb, "via"))), "at")[1] = num(124.0)


def via_not_grounded(pcb, _sch):
    find(next(iter(find_all(pcb, "via"))), "net")[1] = Sym("0")


def via_top_layer_only(pcb, _sch):
    find(next(iter(find_all(pcb, "via"))), "layers")[2] = "F.Cu"


def keepout_short(pcb, _sch):
    for xy in find(find(zone(pcb, "ANTENNA_KEEPOUT"), "polygon"), "pts")[1:]:
        if abs(float(xy[2]) - 66.25) < 1e-9:
            xy[2] = num(64.0)


def port_left_off_the_board(_pcb, sch):
    """P1 marked sheet-only: its land never reaches the PCB, so there is no pad."""
    for sym in find_all(sch, "symbol"):
        refs = [p for p in find_all(sym, "property") if p[1] == "Reference"]
        if refs and refs[0][2] == "P1":
            find(sym, "on_board")[1] = Sym("no")


def symbol_edited_away_from_the_library(_pcb, sch):
    for sym in find_all(find(sch, "lib_symbols"), "symbol"):
        if str(sym[1]).endswith("RF_PORT"):
            sym.append([Sym("extra"), Sym("yes")])


def pin_off_the_wire(_pcb, sch):
    for sym in find_all(sch, "symbol"):
        refs = [p for p in find_all(sym, "property") if p[1] == "Reference"]
        if refs and refs[0][2] == "P1":
            find(sym, "at")[2] = num(90.17)


MUTATIONS = [
    ("a connector footprint back in the model", add_connector),
    ("the port land deleted", drop_port_land),
    ("the port's B.Cu reference pad deleted", drop_reference_pad),
    ("a reference pad narrower than the port pad", narrow_reference_pad),
    ("coplanar ground tabs added at the port", coplanar_ground_at_the_port),
    ("the feed line deleted", delete_feed),
    ("the feed line stopping short of the port pad", feed_off_the_port_pad),
    ("the feed line not landing on the antenna pad", feed_misses_the_pad),
    ("a stub branching off the feed line", feed_branches),
    ("the bottom ground plane deleted", drop_bottom_ground),
    ("the bottom ground plane smaller than the top pour", shrink_bottom_ground),
    ("the pour keep-away corridor deleted", drop_pour_keepaway),
    ("the vias at the launch removed", strip_launch_vias),
    ("a via moved onto the feed line", via_on_the_line),
    ("a via left off the GND net", via_not_grounded),
    ("a via that does not reach B.Cu", via_top_layer_only),
    ("the antenna keep-out stopping short of the plane edge", keepout_short),
    ("a via pushed up into the antenna keep-out", via_on_the_antenna_pad),
    ("P1 marked as sheet-only, so its land never reaches the PCB",
     port_left_off_the_board),
    ("an embedded symbol edited away from the library",
     symbol_edited_away_from_the_library),
    ("a symbol pin no longer on its wire", pin_off_the_wire),
]


def main() -> int:
    bad = 0
    for label, mutate in MUTATIONS:
        pcb, sch = copy.deepcopy(base_pcb), copy.deepcopy(base_sch)
        mutate(pcb, sch)
        OUT.write_text(dumps(pcb) + "\n")
        OUT.with_suffix(".kicad_sch").write_text(dumps(sch) + "\n")
        r = subprocess.run([sys.executable, str(CHECKER), str(OUT)],
                           capture_output=True, text=True)
        caught = [l[5:] for l in r.stdout.splitlines() if l.startswith("FAIL")]
        if r.returncode == 0:
            bad += 1
            print(f"NOT CAUGHT  {label}")
        elif not caught:
            # a non-zero exit with no finding means the checker crashed, which
            # is not the same as catching the mistake
            bad += 1
            print(f"CRASHED     {label}\n              "
                  f"{r.stderr.strip().splitlines()[-1][:110]}")
        else:
            print(f"caught      {label}\n              {caught[0][:110]}")
    print(f"\n{len(MUTATIONS) - bad}/{len(MUTATIONS)} mutations caught")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
