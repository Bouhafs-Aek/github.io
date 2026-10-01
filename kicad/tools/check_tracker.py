#!/usr/bin/env python3
"""Check the football tracker project: netlist, electrical rules, RF layout.

Reads only the files KiCad reads - the schematic, the board and the project
library - and never imports the generator, so a mistake in the generator
cannot hide itself here.  Without a KiCad install in CI this is the stand-in
for ERC and for the parts of DRC that decide whether the board works:

  netlist      every schematic pin's net, worked out from wires, labels and
               no-connect flags, equals the net on the matching board pad
  ERC          no floating pins, no single-pin nets, every power input
               driven, no two outputs fighting
  electrical   supply pins within their absolute maximum, the battery
               divider within the ADC's range, charge current within the
               cell's rating, USB-C sink resistors, the u-blox and Nordic
               pin requirements
  RF + board   50 ohm feed on a GND reference, continuous from the patch to
               RF_IN; no courtyard overlaps; the patch and BLE antenna
               keep-outs clear; vias clear of other nets' pads

    python3 kicad/tools/check_tracker.py
"""

from __future__ import annotations

import collections
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from line_impedance import cpwg  # noqa: E402
from sexpr import find, find_all, parse  # noqa: E402

PRJ = pathlib.Path(__file__).resolve().parent.parent / "tracker"
SCH = PRJ / "epts_football_tracker.kicad_sch"
PCB = PRJ / "epts_football_tracker.kicad_pcb"

FAIL: list[str] = []


def check(ok: bool, msg: str) -> bool:
    print(("  ok    " if ok else "  FAIL  ") + msg)
    if not ok:
        FAIL.append(msg)
    return ok


def fval(node, i=1) -> float:
    return float(node[i])


# ------------------------------------------------------------ schematic side
def sch_netlist():
    sch = parse(SCH.read_text())
    lib = {str(s[1]): s for s in find(sch, "lib_symbols")[1:]}

    def pins_of(sym):
        out = []

        def walk(node):
            for c in node:
                if isinstance(c, list):
                    if c[0] == "pin":
                        at = find(c, "at")
                        out.append((str(find(c, "number")[1]), str(find(c, "name")[1]),
                                    str(c[1]), fval(at, 1), fval(at, 2)))
                    else:
                        walk(c)
        walk(sym)
        return out

    parent = {}

    def root(p):
        while parent.setdefault(p, p) != p:
            parent[p] = parent[parent[p]]
            p = parent[p]
        return p

    def join(a, b):
        parent[root(a)] = root(b)

    def key(x, y):
        return (round(x, 2), round(y, 2))

    for w in find_all(sch, "wire"):
        pts = find(w, "pts")
        join(key(fval(pts[1], 1), fval(pts[1], 2)), key(fval(pts[2], 1), fval(pts[2], 2)))
    labels = collections.defaultdict(list)
    for lab in find_all(sch, "label"):
        at = find(lab, "at")
        labels[str(lab[1])].append(key(fval(at, 1), fval(at, 2)))
    for name, pts in labels.items():
        for p in pts:
            join(("net", name), p)
    no_connects = {key(fval(find(n, "at"), 1), fval(find(n, "at"), 2))
                   for n in find_all(sch, "no_connect")}

    parts = {}
    pin_points = []
    for s in find_all(sch, "symbol"):
        lib_id = find(s, "lib_id")
        if lib_id is None:
            continue
        ref = next(str(p[2]) for p in find_all(s, "property") if p[1] == "Reference")
        at = find(s, "at")
        x, y, rot = fval(at, 1), fval(at, 2), fval(at, 3)
        r = math.radians(rot)
        sym = lib[str(lib_id[1])]
        pins = []
        for number, name, ptype, px, py in pins_of(sym):
            # library frame is y-up; the symbol turns counter-clockwise
            sx = x + px * math.cos(r) - py * math.sin(r)
            sy = y - (px * math.sin(r) + py * math.cos(r))
            pins.append(dict(num=number, name=name, type=ptype, pos=key(sx, sy)))
            pin_points.append(key(sx, sy))
        props = {str(p[1]): str(p[2]) for p in find_all(s, "property")}
        parts[ref] = dict(pins=pins, value=props.get("Value"), lib=str(lib_id[1]),
                          dnp=str(find(s, "dnp")[1]) == "yes", props=props)

    # a pin touching the middle of a wire is not connected in KiCad; touching
    # its end is.  All hookups here are stubs, so ends are all that count.
    net_of_root = {}
    for name in labels:
        net_of_root[root(("net", name))] = name
    for ref, part in parts.items():
        for pin in part["pins"]:
            rt = root(pin["pos"])
            pin["net"] = net_of_root.get(rt)
            pin["nc"] = pin["pos"] in no_connects
    return parts, labels, net_of_root


# ---------------------------------------------------------------- board side
def board():
    pcb = parse(PCB.read_text())
    nets = {int(n[1]): str(n[2]) for n in find_all(pcb, "net")}
    fps = {}
    for fp in find_all(pcb, "footprint"):
        ref = next(str(p[2]) for p in find_all(fp, "property") if p[1] == "Reference")
        at = find(fp, "at")
        x, y = fval(at, 1), fval(at, 2)
        rot = fval(at, 3) if len(at) > 3 else 0.0
        r = math.radians(rot)

        def to_board(lx, ly, x=x, y=y, r=r):
            return (x + lx * math.cos(r) + ly * math.sin(r),
                    y - lx * math.sin(r) + ly * math.cos(r))

        pads = []
        for pad in find_all(fp, "pad"):
            pat = find(pad, "at")
            size = find(pad, "size")
            net = find(pad, "net")
            layers = [str(v) for v in find(pad, "layers")[1:]]
            drill = find(pad, "drill")
            angle = fval(pat, 3) if len(pat) > 3 else 0.0
            pads.append(dict(num=str(pad[1]), kind=str(pad[2]),
                             pos=to_board(fval(pat, 1), fval(pat, 2)),
                             size=(fval(size, 1), fval(size, 2)),
                             angle=angle, ref=ref,
                             drill=fval(drill) if drill is not None and len(drill) > 1
                             and str(drill[1]) != "oval" else (
                                 min(fval(drill, 2), fval(drill, 3)) if drill is not None
                                 and len(drill) > 3 else None),
                             net=str(net[2]) if net is not None else None,
                             layers=layers))
        crt = []
        for c in fp:
            if isinstance(c, list) and c[0] in ("fp_line", "fp_rect") and \
                    str(find(c, "layer")[1]) == "F.CrtYd":
                for k in ("start", "end"):
                    p = find(c, k)
                    crt.append(to_board(fval(p, 1), fval(p, 2)))
        box = (min(p[0] for p in crt), min(p[1] for p in crt),
               max(p[0] for p in crt), max(p[1] for p in crt)) if crt else None
        fps[ref] = dict(pads=pads, box=box, at=(x, y, rot))
    segs = [dict(a=(fval(find(s, "start"), 1), fval(find(s, "start"), 2)),
                 b=(fval(find(s, "end"), 1), fval(find(s, "end"), 2)),
                 w=fval(find(s, "width")), layer=str(find(s, "layer")[1]),
                 net=nets[int(find(s, "net")[1])]) for s in find_all(pcb, "segment")]
    vias = [dict(pos=(fval(find(v, "at"), 1), fval(find(v, "at"), 2)),
                 size=fval(find(v, "size")), net=nets[int(find(v, "net")[1])])
            for v in find_all(pcb, "via")]
    edges = [((fval(find(l, "start"), 1), fval(find(l, "start"), 2)),
              (fval(find(l, "end"), 1), fval(find(l, "end"), 2)))
             for l in find_all(pcb, "gr_line") if str(find(l, "layer")[1]) == "Edge.Cuts"]
    zones = []
    for z in find_all(pcb, "zone"):
        layers = find(z, "layers") or find(z, "layer")
        pts = [(fval(a, 1), fval(a, 2)) for a in find(find(z, "polygon"), "pts")[1:]]
        zones.append(dict(net=str(find(z, "net_name")[1]), layers=[str(v) for v in layers[1:]],
                          pts=pts, keepout=find(z, "keepout") is not None,
                          name=str(find(z, "name")[1]) if find(z, "name") else ""))
    keepouts = []
    for z in find_all(pcb, "zone") + [z for fp in find_all(pcb, "footprint")
                                       for z in find_all(fp, "zone")]:
        ko = find(z, "keepout")
        if ko is None:
            continue
        layers = find(z, "layers") or find(z, "layer")
        pts = [(fval(a, 1), fval(a, 2)) for a in find(find(z, "polygon"), "pts")[1:]]
        keepouts.append(dict(box=(min(q[0] for q in pts), min(q[1] for q in pts),
                                  max(q[0] for q in pts), max(q[1] for q in pts)),
                             layers=[str(v) for v in layers[1:]],
                             tracks=str(find(ko, "tracks")[1]) == "not_allowed",
                             vias=str(find(ko, "vias")[1]) == "not_allowed"))
    stack = find(find(pcb, "setup"), "stackup")
    return dict(fps=fps, segs=segs, vias=vias, edges=edges, zones=zones, stack=stack,
                keepouts=keepouts)


def inside(pt, box, margin=0.0):
    return (box[0] - margin <= pt[0] <= box[2] + margin
            and box[1] - margin <= pt[1] <= box[3] + margin)


def overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def point_seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy)
                                                / (dx * dx + dy * dy)))
    return math.dist(p, (ax + t * dx, ay + t * dy))


def seg_seg_dist(a, b, c, d):
    """Distance between segments a-b and c-d (0 if they cross)."""
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1, o2, o3, o4 = orient(a, b, c), orient(a, b, d), orient(c, d, a), orient(c, d, b)
    if (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0) and 0 not in (o1, o2, o3, o4):
        return 0.0
    return min(point_seg_dist(a, c, d), point_seg_dist(b, c, d),
               point_seg_dist(c, a, b), point_seg_dist(d, a, b))


def seg_rect_dist(a, b, box):
    """Distance from segment a-b to an axis-aligned rectangle."""
    if inside(a, box) or inside(b, box):
        return 0.0
    corners = [(box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3])]
    return min(seg_seg_dist(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def parse_value(text: str) -> float:
    """'4.7uF' -> 4.7e-6, '2.0k' -> 2000, '470R' -> 470, '1M' -> 1e6."""
    mult = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6}
    t = text.replace("F", "").replace("R", "")
    if t and t[-1] in mult:
        return float(t[:-1]) * mult[t[-1]]
    return float(t)


# -------------------------------------------------------------------- checks
def main() -> None:
    parts, labels, _ = sch_netlist()
    brd = board()
    nets = collections.defaultdict(list)          # net -> [(ref, pin)]
    for ref, part in parts.items():
        for pin in part["pins"]:
            if pin["net"]:
                nets[pin["net"]].append((ref, pin))

    def pin(ref, number):
        return next(p for p in parts[ref]["pins"] if p["num"] == number)

    def net(ref, number):
        return pin(ref, number)["net"]

    def on_net(name):
        return {(r, p["num"]) for r, p in nets[name]}

    real = {r: p for r, p in parts.items() if not r.startswith("#")}

    print("Schematic connectivity")
    floating = [f"{r}.{p['num']} {p['name']}" for r, part in real.items()
                for p in part["pins"]
                if p["net"] is None and not p["nc"] and p["type"] != "no_connect"]
    check(not floating, "every pin is on a net or carries a no-connect flag"
          + (f": floating {floating}" if floating else ""))
    nc_on_net = [f"{r}.{p['num']}" for r, part in real.items() for p in part["pins"]
                 if p["net"] and p["nc"]]
    check(not nc_on_net, "no pin is both wired and flagged no-connect"
          + (f": {nc_on_net}" if nc_on_net else ""))
    single = [n for n, members in nets.items()
              if len({(r, p["pos"]) for r, p in members if not r.startswith("#")}) < 2]
    check(not single, "every net reaches at least two pins"
          + (f": single-pin {single}" if single else ""))
    lonely = [n for n, pts in labels.items() if len(pts) < 2]
    check(not lonely, "every label appears at least twice"
          + (f": {lonely}" if lonely else ""))

    print("ERC: drivers")
    for name, members in sorted(nets.items()):
        types = [p["type"] for _, p in members]
        if "power_in" in types:
            check("power_out" in types,
                  f"{name}: power inputs driven by a power output or PWR_FLAG")
        outs = [f"{r}.{p['num']}" for r, p in members if p["type"] == "power_out"
                and not r.startswith("#")]
        check(len(outs) <= 1, f"{name}: at most one power output ({outs or 'none'})")
        drivers = [f"{r}.{p['num']}" for r, p in members if p["type"] == "output"]
        check(len(drivers) <= 1, f"{name}: at most one logic output ({drivers or 'none'})")

    print("Schematic <-> board")
    fps = brd["fps"]
    check(set(real) == set(fps),
          f"same {len(real)} references in both"
          + (f": schematic only {sorted(set(real) - set(fps))}, board only "
             f"{sorted(set(fps) - set(real))}" if set(real) != set(fps) else ""))
    mismatch = []
    for ref, part in real.items():
        pads = collections.defaultdict(set)
        for pad in fps.get(ref, {"pads": []})["pads"]:
            pads[pad["num"]].add(pad["net"])
        for p in part["pins"]:
            if p["num"] not in pads:
                mismatch.append(f"{ref}.{p['num']} has no pad")
                continue
            if pads[p["num"]] != {p["net"]}:
                mismatch.append(f"{ref}.{p['num']}: sch {p['net']} pcb {pads[p['num']]}")
        extra = set(pads) - {p["num"] for p in part["pins"]} - {""}
        for number in extra:
            if pads[number] != {None}:
                mismatch.append(f"{ref} pad {number} (no pin) is on {pads[number]}")
    check(not mismatch, "every pad carries its pin's net, extra pads stay unconnected"
          + (f": {mismatch[:8]}" if mismatch else ""))

    print("Electrical: supplies")
    rail_max = {"+3V3": 3.3 * 1.03, "VBUS": 5.25, "VSYS": 5.25, "VBAT": 4.2, "GND": 0.0}
    abs_max = [  # (ref, pin, limit V, source)
        ("U1", "23", 3.6, "NEO-M9N VCC"), ("U1", "22", 3.6, "NEO-M9N V_BCKP"),
        ("U2", "28", 3.6, "nRF52840 VDD"), ("U2", "30", 5.5, "nRF52840 VDDH"),
        ("U2", "32", 5.5, "nRF52840 VBUS"),
        ("U3", "8", 4.8, "ISM330DHCX VDD"), ("U3", "5", 4.8, "ISM330DHCX VDDIO"),
        ("J3", "4", 3.6, "microSD VDD"), ("U4", "4", 6.0, "MCP73831 VDD"),
        ("U5", "1", 6.0, "AP2112K VIN"), ("U6", "5", 6.0, "USBLC6 VBUS"),
        ("J4", "1", 3.6, "SWD VCC sense")]
    for ref, number, limit, what in abs_max:
        n = net(ref, number)
        check(n in rail_max and rail_max[n] <= limit,
              f"{what} on {n} ({rail_max.get(n, '?')} V <= {limit} V)")
    for ref, number in (("U2", "28"), ("U2", "30")):
        check(net(ref, number) == "+3V3",
              f"nRF52840 normal voltage mode: {pin(ref, number)['name']} on +3V3")
    check(net("U2", "31") is None, "nRF52840 DCCH unused (only for high voltage mode)")
    check(net("U5", "3") == net("U5", "1") == "VSYS", "LDO enabled whenever it has input")

    # signal nets must stay at 3.3 V logic: none may touch a higher rail
    high = {"VBUS", "VSYS", "VBAT"}
    mcu = {p["net"] for p in parts["U2"]["pins"] if p["name"].startswith("P")}
    check(not (mcu & high), "no MCU GPIO wired straight to VBUS, VSYS or VBAT")

    print("Electrical: battery and charging")
    r_top, r_bot = (parse_value(parts[r]["value"]) for r in ("R10", "R11"))
    check({net("R10", "1"), net("R10", "2")} == {"VBAT", "VBAT_SENSE"}
          and {net("R11", "1"), net("R11", "2")} == {"VBAT_SENSE", "GND"},
          "VBAT -> R10 -> VBAT_SENSE -> R11 -> GND")
    v_adc = 4.2 * r_bot / (r_top + r_bot)
    check(v_adc <= 3.6 * 0.95,
          f"full cell at the ADC: {v_adc:.2f} V, inside the 3.6 V SAADC range (gain 1/6, 0.6 V ref)")
    check(pin("U2", "11")["name"] == "P0.02" and net("U2", "11") == "VBAT_SENSE",
          "VBAT_SENSE on P0.02 = AIN0")
    check(4.2 / (r_top + r_bot) * 1e6 < 5, f"divider draws {4.2 / (r_top + r_bot) * 1e6:.1f} uA")
    i_chg = 1000 / parse_value(parts["R7"]["value"])
    cell_mah = 1800
    check({net("R7", "1"), net("R7", "2")} == {"CHG_PROG", "GND"} and net("U4", "5") == "CHG_PROG",
          "R7 from PROG to GND")
    check(0.1 <= i_chg <= 0.5 and i_chg * 1000 / cell_mah <= 1.0,
          f"charge current {i_chg * 1000:.0f} mA = {i_chg * 1000 / cell_mah:.2f} C "
          f"for {cell_mah} mAh, inside the MCP73831's 500 mA")
    check(net("U4", "3") == "VBAT" and net("J2", "1") == "VBAT" and net("J2", "2") == "GND",
          "charger output and battery + on VBAT")
    check(net("Q1", "3") == "VBAT" and net("Q1", "2") == "VSYS" and net("Q1", "1") == "VBUS",
          "Q1: drain on the cell, source on the load, gate on VBUS (off with USB in)")
    check(on_net("VBUS") >= {("R9", "1")} and net("R9", "2") == "GND",
          "Q1 gate pulled down when USB is unplugged")
    check(net("D1", "2") == "VBUS" and net("D1", "1") == "VSYS",
          "D1 anode on VBUS, cathode on VSYS")

    print("Electrical: USB-C")
    for cc, rr in (("CC1", "R5"), ("CC2", "R6")):
        check({net(rr, "1"), net(rr, "2")} == {cc, "GND"} and parts[rr]["value"] == "5.1k",
              f"{cc}: 5.1 kohm Rd to GND (sink)")
    check(net("J1", "A6") == net("J1", "B6") == "USB_DP" == net("U2", "35")
          and net("J1", "A7") == net("J1", "B7") == "USB_DN" == net("U2", "34"),
          "both D+/D- pairs of the receptacle to the nRF52840 USB")
    check({net("U6", "1"), net("U6", "6")} == {"USB_DP"} and {net("U6", "3"), net("U6", "4")}
          == {"USB_DN"} and net("U6", "5") == "VBUS" and net("U6", "2") == "GND",
          "USBLC6 across D+, D- and VBUS")
    check(net("U2", "32") == "VBUS", "nRF52840 VBUS sees USB for USB detect")

    print("Electrical: u-blox NEO-M9N")
    check(net("U1", "7") == "GND", "VDD_USB to GND: the module's USB is unused")
    check(net("U1", "2") is None, "D_SEL open: UART and I2C, not SPI")
    check(net("U1", "9") is None and net("U1", "14") is None,
          "VCC_RF and LNA_EN unused with a passive patch")
    uart = {("U1", "20"): ("U2", "P0.08"), ("U1", "21"): ("U2", "P0.06"),
            ("U1", "3"): ("U2", "P0.13"), ("U1", "4"): ("U2", "P0.14"),
            ("U1", "8"): ("U2", "P0.15")}
    for (ref, number), (mref, pname) in uart.items():
        mpin = next(p for p in parts[mref]["pins"] if p["name"] == pname)
        check(net(ref, number) == mpin["net"] and net(ref, number) is not None,
              f"NEO {pin(ref, number)['name']} -> nRF {pname} ({net(ref, number)})")
    check(on_net("GNSS_RF") == {("U1", "11"), ("Z2", "1"), ("Z1", "1")}
          and on_net("GNSS_ANT") == {("AE1", "1"), ("Z2", "2"), ("Z3", "1")},
          "RF_IN reaches the patch only through the pi network")

    print("Electrical: IMU, microSD, debug")
    imu = {"1": "IMU_MISO", "13": "IMU_SCK", "14": "IMU_MOSI", "12": "IMU_CS",
           "4": "IMU_INT1", "9": "IMU_INT2"}
    check(all(net("U3", k) == v for k, v in imu.items()), "ISM330DHCX in SPI mode on its own bus")
    check(net("U3", "2") == net("U3", "3") == "GND"
          and net("U3", "10") is None and net("U3", "11") is None,
          "ISM330DHCX: SDx/SCx to GND, OCS_Aux/SDO_Aux open (datasheet pin table)")
    sd = {"2": "SD_CS", "3": "SD_MOSI", "5": "SD_SCK", "7": "SD_MISO"}
    check(all(net("J3", k) == v for k, v in sd.items()), "microSD wired for SPI mode")
    for n in ("SD_CS", "SD_DAT1", "SD_DAT2", "SD_MISO"):
        pull = [r for r, p in nets[n] if r.startswith("R")]
        check(len(pull) == 1 and on_net("+3V3") & {(pull[0], "1"), (pull[0], "2")},
              f"{n} pulled up to 3V3")
    swd = {"SWDIO": "SWDIO", "SWDCLK": "SWDCLK", "NRESET": "P0.18", "SWO": "P1.00"}
    for n, pname in swd.items():
        mpin = next(p for p in parts["U2"]["pins"] if p["name"] == pname)
        check(mpin["net"] == n and ("J4", next(p["num"] for p in parts["J4"]["pins"]
                                              if p["net"] == n)) in on_net(n),
              f"Tag-Connect {n} on nRF52840 {pname}")
    used = sorted((p["name"], p["net"]) for p in parts["U2"]["pins"]
                  if p["net"] and p["name"].startswith("P"))
    print("        firmware pin map: " + ", ".join(f"{a}={b}" for a, b in used))

    print("Board: RF feed")
    stack = brd["stack"]
    layers = [l for l in find_all(stack, "layer")]
    names = [str(l[1]) for l in layers]
    d1 = layers[names.index("dielectric 1")]
    d3 = layers[names.index("dielectric 3")]
    h1, er1 = fval(find(d1, "thickness")), fval(find(d1, "epsilon_r"))
    h3, er3 = fval(find(d3, "thickness")), fval(find(d3, "epsilon_r"))
    rf_segs = [s for s in brd["segs"] if s["net"] in ("GNSS_ANT", "GNSS_RF")]
    widths = {s["w"] for s in rf_segs}
    check(len(widths) == 1, f"one feed width ({sorted(widths)})")
    w = widths.pop()
    # the gap is the smallest distance from the line to any other copper
    # that the pour will follow: the netclass clearance
    import json
    pro = json.loads((PRJ / "epts_football_tracker.kicad_pro").read_text())
    cls = next(c for c in pro["net_settings"]["classes"] if c["name"] == "GNSS_50R")
    gap = cls["clearance"]
    for layer, h, er in (("F.Cu", h1, er1), ("B.Cu", h3, er3)):
        z0, _ = cpwg(w, gap, h, er)
        check(45 <= z0 <= 55, f"{layer} CPWG w={w} gap={gap} on {h} mm er={er}: {z0:.1f} ohm")
    planes = {z["layers"][0] for z in brd["zones"]
              if not z["keepout"] and z["net"] == "GND" and len(z["layers"]) == 1}
    check({"In1.Cu", "In2.Cu", "F.Cu", "B.Cu"} <= planes,
          "GND pours on all four layers: In1 under F.Cu, In2 under B.Cu")

    # continuity: AE1.1 -> ... -> U1.11 over segments, vias and Z2
    def near(a, b):
        return math.dist(a, b) < 0.01
    graph = collections.defaultdict(set)
    nodes = [("seg", i, end) for i, s in enumerate(rf_segs) for end in ("a", "b")]
    pts = {n: rf_segs[n[1]][n[2]] for n in nodes}
    for i in range(len(rf_segs)):
        graph[("seg", i, "a")].add(("seg", i, "b"))
        graph[("seg", i, "b")].add(("seg", i, "a"))
    rf_vias = [v for v in brd["vias"] if v["net"] in ("GNSS_ANT", "GNSS_RF")]
    anchors = {("AE1", "1"): fps["AE1"], ("U1", "11"): fps["U1"],
               ("Z2", "1"): fps["Z2"], ("Z2", "2"): fps["Z2"]}
    for (ref, number), f in anchors.items():
        pos = next(p["pos"] for p in f["pads"] if p["num"] == number)
        pts[(ref, number)] = pos
    for v in rf_vias:
        pts[("via", v["pos"])] = v["pos"]
    keys = list(pts)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if near(pts[a], pts[b]):
                graph[a].add(b)
                graph[b].add(a)
    # a segment end landing on a segment's middle (a T) also joins
    for n in nodes:
        for j, s in enumerate(rf_segs):
            if n[1] != j and s["layer"] == rf_segs[n[1]]["layer"] and \
                    point_seg_dist(pts[n], s["a"], s["b"]) < 0.01:
                graph[n] |= {("seg", j, "a")}
                graph[("seg", j, "a")] |= {n}
    graph[("Z2", "1")].add(("Z2", "2"))
    graph[("Z2", "2")].add(("Z2", "1"))
    seen, todo = set(), [("AE1", "1")]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        todo.extend(graph[n] - seen)
    check(("U1", "11") in seen, "copper path from the patch feed to RF_IN, through Z2")
    length = sum(math.dist(s["a"], s["b"]) for s in rf_segs)
    check(length < 30, f"feed length {length:.1f} mm (lambda/4 at 1575 MHz in FR4 is ~26 mm)")
    for s in rf_segs:
        for v in brd["vias"]:
            if v["net"] == "GND":
                d = point_seg_dist(v["pos"], s["a"], s["b"]) - v["size"] / 2 - s["w"] / 2
                if d < gap - 1e-6:
                    check(False, f"GND via at {v['pos']} {d:.2f} mm from the feed")

    print("Board: placement")
    ex = [p for e in brd["edges"] for p in e]
    outline = (min(p[0] for p in ex), min(p[1] for p in ex),
               max(p[0] for p in ex), max(p[1] for p in ex))
    print(f"        board {outline[2] - outline[0]:.1f} x {outline[3] - outline[1]:.1f} mm")
    edge_parts = {"J1", "J2", "J3"}            # connectors overhang by design
    outside = [r for r, f in fps.items() if r not in edge_parts and f["box"]
               and not (inside(f["box"][:2], outline, 0.01) and inside(f["box"][2:], outline, 0.01))]
    check(not outside, "every courtyard inside the board, bar the edge connectors"
          + (f": {outside}" if outside else ""))
    clash = [(a, b) for i, a in enumerate(sorted(fps)) for b in sorted(fps)[i + 1:]
             if fps[a]["box"] and fps[b]["box"] and overlap(fps[a]["box"], fps[b]["box"])]
    check(not clash, "no courtyard overlaps" + (f": {clash}" if clash else ""))
    patch = fps["AE1"]["box"]
    near_patch = [r for r, f in fps.items() if r != "AE1" and f["box"]
                  and overlap(f["box"], (patch[0] - 0.5, patch[1] - 0.5,
                                         patch[2] + 0.5, patch[3] + 0.5))]
    check(not near_patch, "no part within 1 mm of the GNSS patch"
          + (f": {near_patch}" if near_patch else ""))
    ble = next(z for z in brd["zones"] if z["name"] == "BLE_ANTENNA_KEEPOUT")
    bbox = (min(p[0] for p in ble["pts"]), min(p[1] for p in ble["pts"]),
            max(p[0] for p in ble["pts"]), max(p[1] for p in ble["pts"]))
    check(bbox[2] >= outline[2] and set(ble["layers"]) >= {"F.Cu", "In1.Cu", "In2.Cu", "B.Cu"},
          "BLE antenna keep-out runs to the board edge on all four copper layers")
    intruders = [r for r, f in fps.items() if r != "U2"
                 for p in f["pads"] if inside(p["pos"], bbox)]
    intruders += ["via"] * sum(inside(v["pos"], bbox, v["size"] / 2 - 1e-3) for v in brd["vias"])
    intruders += ["track"] * sum(inside(s["a"], bbox) or inside(s["b"], bbox) for s in brd["segs"])
    check(not intruders, "nothing in the BLE antenna keep-out" + (f": {intruders}" if intruders else ""))
    worst = []
    for v in brd["vias"]:
        for r, f in fps.items():
            for p in f["pads"]:
                if p["net"] == v["net"] and p["kind"] != "np_thru_hole":
                    continue
                w, h = p["size"]
                if round(p["angle"]) % 180 == 90:
                    w, h = h, w
                dx = max(abs(v["pos"][0] - p["pos"][0]) - w / 2, 0.0)
                dy = max(abs(v["pos"][1] - p["pos"][1]) - h / 2, 0.0)
                if math.hypot(dx, dy) < v["size"] / 2 + 0.15 - 1e-3:
                    worst.append(f"{v['net']} via {v['pos']} on {r}.{p['num']}")
    check(not worst, f"{len(brd['vias'])} vias clear of other nets' pads"
          + (f": {worst[:5]}" if worst else ""))

    print("Board: clearances (the DRC rules KiCad applies to pads)")
    loops = collections.Counter()
    for a, b in brd["edges"]:
        loops[(round(a[0], 3), round(a[1], 3))] += 1
        loops[(round(b[0], 3), round(b[1], 3))] += 1
    check(bool(brd["edges"]) and all(v == 2 for v in loops.values()),
          f"board outline: {len(brd['edges'])} Edge.Cuts segments forming a closed loop")
    patterns = {pat["pattern"]: pat["netclass"] for pat in pro["net_settings"]["netclass_patterns"]}
    clearance = {c["name"]: c["clearance"] for c in pro["net_settings"]["classes"]}
    rules = pro["board"]["design_settings"]["rules"]

    def need(net_a, net_b):
        return max(clearance[patterns.get(net_a, "Default")],
                   clearance[patterns.get(net_b, "Default")])

    def pad_box(p):
        w, h = p["size"]
        if round(p["angle"]) % 180 == 90:
            w, h = h, w
        elif round(p["angle"]) % 90:
            w = h = max(w, h)              # off-axis: the conservative square
        x, y = p["pos"]
        return (x - w / 2, y - h / 2, x + w / 2, y + h / 2)

    def box_gap(a, b):
        dx = max(a[0] - b[2], b[0] - a[2], 0.0)
        dy = max(a[1] - b[3], b[1] - a[3], 0.0)
        return math.hypot(dx, dy)

    copper = [p for f in fps.values() for p in f["pads"] if p["kind"] != "np_thru_hole"]
    for p in copper:
        p["box"] = pad_box(p)
    tight = []
    for i, a in enumerate(copper):
        for b in copper[i + 1:]:
            if a["net"] is not None and a["net"] == b["net"]:
                continue
            if not set(a["layers"]) & set(b["layers"]) and "*.Cu" not in a["layers"] + b["layers"]:
                continue
            gap = box_gap(a["box"], b["box"])
            req = need(a["net"], b["net"])
            if gap < req - 1e-4:
                tight.append(f"{a['ref']}.{a['num']}-{b['ref']}.{b['num']} "
                             f"{gap:.3f} < {req}")
    check(not tight, f"{len(copper)} copper pads: every pad-to-pad gap meets its "
          "net classes' clearance" + (f": {tight[:6]}" if tight else ""))
    holes = [p for f in fps.values() for p in f["pads"] if p["drill"]]
    near_holes = []
    for h in holes:
        for p in copper:
            if p is h or (p["ref"] == h["ref"] and p["num"] == h["num"] and h["num"]):
                continue
            x0, y0, x1, y1 = p["box"]
            dx = max(x0 - h["pos"][0], h["pos"][0] - x1, 0.0)
            dy = max(y0 - h["pos"][1], h["pos"][1] - y1, 0.0)
            gap = math.hypot(dx, dy) - h["drill"] / 2
            if gap < rules["min_hole_clearance"] - 1e-4:
                near_holes.append(f"{p['ref']}.{p['num']} {gap:.3f} mm from a "
                                  f"{h['ref']} hole")
    check(not near_holes, f"{len(holes)} holes: copper at least "
          f"{rules['min_hole_clearance']} mm away" + (f": {near_holes[:6]}" if near_holes else ""))

    print("Board: tracks and vias (fan-out, power routing, RF)")
    for p in copper:
        p["cu"] = {"F.Cu", "In1.Cu", "In2.Cu", "B.Cu"} if any(
            l == "*.Cu" for l in p["layers"]) else {l for l in p["layers"] if l.endswith(".Cu")}
    via_r = {id(v): v["size"] / 2 for v in brd["vias"]}
    edge_rule = rules["min_copper_edge_clearance"]
    bad = []
    segs = brd["segs"]
    for k, sg in enumerate(segs):
        a, b, half = sg["a"], sg["b"], sg["w"] / 2
        lo = (min(a[0], b[0]) - 2, min(a[1], b[1]) - 2, max(a[0], b[0]) + 2, max(a[1], b[1]) + 2)
        for pd in copper:
            if pd["net"] == sg["net"] or sg["layer"] not in pd["cu"] or not overlap(pd["box"], lo):
                continue
            gap = seg_rect_dist(a, b, pd["box"]) - half
            if gap < need(sg["net"], pd["net"]) - 1e-3:
                bad.append(f"{sg['net']} track {gap:.3f} mm from {pd['ref']}.{pd['num']}")
        for o in segs[k + 1:]:
            if o["net"] == sg["net"] or o["layer"] != sg["layer"]:
                continue
            gap = seg_seg_dist(a, b, o["a"], o["b"]) - half - o["w"] / 2
            if gap < need(sg["net"], o["net"]) - 1e-3:
                bad.append(f"{sg['net']}/{o['net']} tracks {gap:.3f} mm apart near {a}")
        for v in brd["vias"]:
            if v["net"] == sg["net"]:
                continue
            gap = point_seg_dist(v["pos"], a, b) - half - via_r[id(v)]
            if gap < need(sg["net"], v["net"]) - 1e-3:
                bad.append(f"{sg['net']} track {gap:.3f} mm from a {v['net']} via at {v['pos']}")
        for h in holes:
            gap = point_seg_dist(h["pos"], a, b) - half - h["drill"] / 2
            if gap < rules["min_hole_clearance"] - 1e-3 and not (
                    h["net"] == sg["net"] and h["kind"] == "thru_hole"):
                bad.append(f"{sg['net']} track {gap:.3f} mm from a {h['ref']} hole")
        for e0, e1 in brd["edges"]:
            gap = seg_seg_dist(a, b, e0, e1) - half
            if gap < edge_rule - 1e-3:
                bad.append(f"{sg['net']} track {gap:.3f} mm from the board edge")
        for ko in brd["keepouts"]:
            if ko["tracks"] and sg["layer"] in ko["layers"] and \
                    seg_rect_dist(a, b, ko["box"]) < half - 1e-3:
                bad.append(f"{sg['net']} track in a keep-out at {a}")
    vias = brd["vias"]
    for k, v in enumerate(vias):
        r = via_r[id(v)]
        for pd in copper:
            if pd["net"] == v["net"] or not pd["cu"] & {"F.Cu", "B.Cu"}:
                continue
            gap = rect_gap = max(pd["box"][0] - v["pos"][0], v["pos"][0] - pd["box"][2], 0.0)
            dy = max(pd["box"][1] - v["pos"][1], v["pos"][1] - pd["box"][3], 0.0)
            gap = math.hypot(rect_gap, dy) - r
            if gap < need(v["net"], pd["net"]) - 1e-3:
                bad.append(f"{v['net']} via {gap:.3f} mm from {pd['ref']}.{pd['num']}")
        for o in vias[k + 1:]:
            gap = math.dist(v["pos"], o["pos"]) - r - via_r[id(o)]
            req = 0.25 if o["net"] == v["net"] else need(v["net"], o["net"])
            if gap < req - 1e-3:
                bad.append(f"vias {gap:.3f} mm apart at {v['pos']}")
        for h in holes:
            gap = math.dist(v["pos"], h["pos"]) - r - h["drill"] / 2
            if gap < rules["min_hole_clearance"] - 1e-3:
                bad.append(f"{v['net']} via {gap:.3f} mm from a {h['ref']} hole")
        x0, y0, x1, y1 = outline
        if min(v["pos"][0] - x0, x1 - v["pos"][0], v["pos"][1] - y0, y1 - v["pos"][1]) - r \
                < edge_rule - 1e-3:
            bad.append(f"via at {v['pos']} too close to the board edge")
        for ko in brd["keepouts"]:
            if ko["vias"] and inside(v["pos"], ko["box"], r - 1e-3):
                bad.append(f"{v['net']} via in a keep-out at {v['pos']}")
    check(not bad, f"{len(segs)} tracks and {len(vias)} vias: clearances to every other "
          "net's copper, holes, board edge and keep-outs" + (f": {bad[:6]}" if bad else ""))

    # connectivity, by KiCad's rule: a track end (or a via) joins whatever
    # copper it lies inside on its layer.  Crossing mid-track joins nothing.
    def joined(net):
        items = []
        for pd in copper:
            if pd["net"] == net:
                items.append(("pad", pd))
        for sg in segs:
            if sg["net"] == net:
                items.append(("seg", sg))
        for v in vias:
            if v["net"] == net:
                items.append(("via", v))
        parent = list(range(len(items)))

        def root(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def covers(item, pt, layer):
            kind, o = item
            if kind == "pad":
                return layer in o["cu"] and inside(pt, o["box"], 1e-3)
            if kind == "seg":
                return o["layer"] == layer and point_seg_dist(pt, o["a"], o["b"]) <= o["w"] / 2 + 1e-3
            return math.dist(pt, o["pos"]) <= via_r[id(o)] + 1e-3

        anchors = []
        for i, (kind, o) in enumerate(items):
            if kind == "seg":
                anchors += [(i, o["a"], o["layer"]), (i, o["b"], o["layer"])]
            elif kind == "via":
                anchors += [(i, o["pos"], "F.Cu"), (i, o["pos"], "B.Cu")]
        for i, pt, layer in anchors:
            for j, other in enumerate(items):
                if j != i and covers(other, pt, layer):
                    parent[root(i)] = root(j)
        pads = [i for i, (k, _) in enumerate(items) if k == "pad"]
        groups = {root(i) for i in pads}
        return len(groups), len(pads), items, root

    for net in ("VBUS", "VBAT", "VSYS", "+3V3"):
        groups, npads, _, _ = joined(net)
        check(groups == 1, f"{net}: all {npads} pads joined by copper" +
              ("" if groups == 1 else f" - {groups} separate pieces"))
    _, _, items, root = joined("GND")
    via_roots = {root(i) for i, (k, _) in enumerate(items) if k == "via"}
    rf = (min(s_["a"][0] for s_ in rf_segs) - 4, min(s_["a"][1] for s_ in rf_segs),
          max(s_["a"][0] for s_ in rf_segs) + 4, max(s_["b"][1] for s_ in rf_segs) + 2)
    stranded = [f"{o['ref']}.{o['num']}" for i, (k, o) in enumerate(items)
                if k == "pad" and o["kind"] == "smd" and "F.Cu" in o["cu"]
                and root(i) not in via_roots and not inside(o["pos"], rf)]
    check(not stranded, "every top-layer GND pad has its own via to the inner planes"
          + (f": not {stranded}" if stranded else ""))

    print()
    if FAIL:
        print(f"{len(FAIL)} check(s) failed")
        sys.exit(1)
    print("all checks passed")


if __name__ == "__main__":
    main()
