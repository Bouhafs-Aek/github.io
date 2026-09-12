#!/usr/bin/env python3
"""Generate the KiCad project, schematic and board for the SWRA117D test board.

Everything is derived from two sources of truth that live next to it:

  * ``library/SWRA117D_RF.kicad_sym``   - the antenna symbol
  * ``library/SWRA117D_RF.pretty/*``    - the antenna, SMA and 0402 footprints

The symbol and footprints are parsed and embedded into the schematic and the
board exactly as KiCad would do it, so the three files always agree on pins,
pads and nets.  Run it once; after that KiCad owns the files:

    python3 kicad/tools/gen_project.py
"""

from __future__ import annotations

import copy
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, dumps, find, num, parse  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
PRJ_DIR = HERE.parent
LIB_DIR = PRJ_DIR / "library"
FP_DIR = LIB_DIR / "SWRA117D_RF.pretty"
PROJECT = "swra117d_2g4_antenna"
LIB_NICK = "SWRA117D_RF"

NAMESPACE = uuid.UUID("6d0c4a55-3a1e-5f2b-8c77-2b9d6e0a4413")


def U(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


ROOT_UUID = U("sheet", "root")

# ---------------------------------------------------------------- board data
BOARD_X0, BOARD_Y0, BOARD_X1, BOARD_Y1 = 100.0, 60.0, 140.0, 90.0
GND_EDGE_Y = 65.75          # top edge of the ground plane = bottom of the antenna
FEED_Y = 75.0               # y of the 50 ohm feed line
ANT_ORIGIN = (124.0, 66.0)  # antenna feed pad on the board
W50 = 1.5                   # 50 ohm microstrip width for 0.8 mm FR4, er = 4.4
W_NECK = 0.5                # neck into the 0402 lands and the antenna feed pad
POUR_GAP = 1.0              # top pour keep-away either side of the 50 ohm line
SUB_H, SUB_ER, SUB_TAND = 0.8, 4.4, 0.02

NETS = {"": 0, "GND": 1, "RF_IN": 2, "ANT_FEED": 3}

TITLE = "2.45 GHz PCB antenna (TI SWRA117D) - RF test board"

# reference, library id, value, footprint, schematic placement, board placement
PARTS = [
    dict(ref="J1", lib=f"{LIB_NICK}:Conn_Coaxial_SMA", value="SMA edge launch",
         fp="SMA_EdgeMount_Generic", sch=(76.2, 88.9, 0), pcb=(100.0, FEED_Y, 0),
         nets={"1": "RF_IN", "2": "GND"},
         ref_at=(76.2, 81.28), val_at=(76.2, 83.82),
         desc="Coaxial connector, 50 ohm test port"),
    dict(ref="C1", lib=f"{LIB_NICK}:C", value="0.5pF", fp="Chip_0402_1005Metric_RF",
         sch=(91.44, 96.52, 0), pcb=(113.5, FEED_Y + 0.51, 270), dnp=True,
         nets={"1": "RF_IN", "2": "GND"},
         ref_at=(93.98, 95.25), val_at=(93.98, 97.79),
         desc="Shunt element of the pi matching network (source side)"),
    dict(ref="L1", lib=f"{LIB_NICK}:L", value="0.8nH", fp="Chip_0402_1005Metric_RF",
         sch=(101.6, 88.9, 90), pcb=(118.0, FEED_Y, 0),
         nets={"1": "RF_IN", "2": "ANT_FEED"},
         ref_at=(101.6, 85.09), val_at=(101.6, 92.71),
         desc="Series element of the pi matching network"),
    dict(ref="C2", lib=f"{LIB_NICK}:C", value="0.5pF", fp="Chip_0402_1005Metric_RF",
         sch=(111.76, 96.52, 0), pcb=(120.5, FEED_Y + 0.51, 270), dnp=True,
         nets={"1": "ANT_FEED", "2": "GND"},
         ref_at=(114.3, 95.25), val_at=(114.3, 97.79),
         desc="Shunt element of the pi matching network (antenna side)"),
    dict(ref="AE1", lib=f"{LIB_NICK}:ANT_SWRA117D_2G4_Left",
         value="ANT_SWRA117D_2G4_Left", fp="Texas_SWRA117D_2.4GHz_Left",
         sch=(127.0, 81.28, 0), pcb=(ANT_ORIGIN[0], ANT_ORIGIN[1], 0),
         nets={"1": "ANT_FEED", "2": "GND"},
         ref_at=(132.08, 77.47), val_at=(132.08, 80.01),
         fp_ref_at=(-6.0, 1.6), in_bom=False,
         desc="2.45 GHz printed inverted-F antenna (TI SWRA117D, left layout)",
         extra_props=[
             ("Sim.Device", "SUBCKT"),
             ("Sim.Name", "ANT_SWRA117D_2G4"),
             ("Sim.Library", "${KIPRJMOD}/sim/antenna_swra117d.lib"),
             ("Sim.Pins", "1=1 2=2"),
         ]),
]

WIRES = [
    ((81.28, 88.9), (91.44, 88.9)),     # J1 -> C1 node
    ((91.44, 88.9), (97.79, 88.9)),     # C1 node -> L1
    ((105.41, 88.9), (111.76, 88.9)),   # L1 -> C2 node
    ((111.76, 88.9), (127.0, 88.9)),    # C2 node -> antenna
    ((127.0, 88.9), (127.0, 86.36)),    # up into AE1 pin 1
    ((91.44, 88.9), (91.44, 92.71)),    # C1 stub
    ((91.44, 100.33), (91.44, 102.87)),  # C1 -> GND
    ((111.76, 88.9), (111.76, 92.71)),  # C2 stub
    ((111.76, 100.33), (111.76, 102.87)),  # C2 -> GND
    ((76.2, 93.98), (76.2, 96.52)),     # J1 shield -> GND
    ((129.54, 86.36), (129.54, 96.52)),  # AE1 ground pin -> GND
    ((91.44, 102.87), (86.36, 102.87)),  # GND -> PWR_FLAG
]
JUNCTIONS = [(91.44, 88.9), (111.76, 88.9)]
LABELS = [("RF_IN", (85.09, 88.9)), ("ANT_FEED", (120.65, 88.9))]

SCH_NOTE = (
    "RF test board for the TI SWRA117D 2.45 GHz printed inverted-F antenna.\n"
    "\n"
    "J1 feeds a 1.5 mm wide 50 ohm microstrip on 0.8 mm FR4 (er 4.4, tan d 0.02).\n"
    "C1 / L1 / C2 form a pi matching network; only L1 is fitted by default.\n"
    "AE1 pin 2 must sit on the ground plane edge - see the keep-out on the PCB.\n"
    "\n"
    "Simulation: sim/s11_pi_match.cir (ngspice, lumped antenna model) and\n"
    "sim/openems/swra117d_openems.py (full wave S11, impedance, far field)."
)

POWER = [  # ground symbols and the ERC power flag: reference, sheet position
    ("#PWR01", (76.2, 96.52)),
    ("#PWR02", (91.44, 102.87)),
    ("#PWR03", (111.76, 102.87)),
    ("#PWR04", (129.54, 96.52)),
]
# A passive RF board has no power source of its own, so ERC reports
# "Input Power pin not driven by any Output Power pins" on the ground net.
# One flag with a power-output pin on that net is the standard answer.
PWR_FLAGS = [("#FLG01", (86.36, 102.87))]


def effects(size=1.27, hide=False, justify=None, thickness=None):
    font = [Sym("font"), [Sym("size"), num(size), num(size)]]
    if thickness is not None:
        font.append([Sym("thickness"), num(thickness)])
    out = [Sym("effects"), font]
    if justify:
        out.append([Sym("justify")] + [Sym(j) for j in justify.split()])
    if hide:
        out.append([Sym("hide"), Sym("yes")])
    return out


def prop(name, value, at, hide=False, justify=None):
    x, y, rot = at
    return [Sym("property"), name, value,
            [Sym("at"), num(x), num(y), num(rot)],
            effects(hide=hide, justify=justify)]


# ------------------------------------------------------------------ schematic
def lib_symbols() -> list:
    out = [Sym("lib_symbols")]
    ant = parse((LIB_DIR / f"{LIB_NICK}.kicad_sym").read_text())
    for child in ant[1:]:
        if isinstance(child, list) and child[0] == "symbol":
            sym = copy.deepcopy(child)
            sym[1] = f"{LIB_NICK}:{sym[1]}"
            out.append(sym)
    return out


def sch_symbol(part) -> list:
    x, y, rot = part["sch"]
    ref, value = part["ref"], part["value"]
    node = [Sym("symbol"),
            [Sym("lib_id"), part["lib"]],
            [Sym("at"), num(x), num(y), num(rot)],
            [Sym("unit"), Sym("1")],
            [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("yes" if part.get("in_bom", True) else "no")],
            [Sym("on_board"), Sym("yes")],
            [Sym("dnp"), Sym("yes" if part.get("dnp") else "no")],
            [Sym("uuid"), U("sym", ref)],
            prop("Reference", ref, (*part["ref_at"], 0), justify="left"),
            prop("Value", value, (*part["val_at"], 0), justify="left"),
            prop("Footprint", f"{LIB_NICK}:{part['fp']}", (x, y, 0), hide=True),
            prop("Datasheet", part.get("datasheet", "~"), (x, y, 0), hide=True),
            prop("Description", part["desc"], (x, y, 0), hide=True)]
    for name, value in part.get("extra_props", []):
        node.append(prop(name, value, (x, y, 0), hide=True))
    for pin in sorted(part["nets"]):
        node.append([Sym("pin"), pin, [Sym("uuid"), U("pin", ref, pin)]])
    node.append([Sym("instances"),
                 [Sym("project"), PROJECT,
                  [Sym("path"), f"/{ROOT_UUID}",
                   [Sym("reference"), ref], [Sym("unit"), Sym("1")]]]])
    return node


def sch_power(ref, pos, name="GND", below=True, in_bom=True) -> list:
    """Ground symbol or ERC power flag - both are 'power' symbols with one pin."""
    x, y = pos
    label_y = y + 3.81 if below else y - 3.81
    return [Sym("symbol"),
            [Sym("lib_id"), f"{LIB_NICK}:{name}"],
            [Sym("at"), num(x), num(y), Sym("0")],
            [Sym("unit"), Sym("1")],
            [Sym("exclude_from_sim"), Sym("no" if in_bom else "yes")],
            [Sym("in_bom"), Sym("yes" if in_bom else "no")],
            [Sym("on_board"), Sym("yes" if in_bom else "no")],
            [Sym("dnp"), Sym("no")],
            [Sym("uuid"), U("sym", ref)],
            prop("Reference", ref, (x, y + 6.35, 0), hide=True),
            prop("Value", name, (x, label_y, 0)),
            prop("Footprint", "", (x, y, 0), hide=True),
            prop("Datasheet", "", (x, y, 0), hide=True),
            prop("Description", "Ground reference" if name == "GND"
                 else "ERC power source flag", (x, y, 0), hide=True),
            [Sym("pin"), "1", [Sym("uuid"), U("pin", ref, "1")]],
            [Sym("instances"),
             [Sym("project"), PROJECT,
              [Sym("path"), f"/{ROOT_UUID}",
               [Sym("reference"), ref], [Sym("unit"), Sym("1")]]]]]


def build_schematic() -> list:
    sch = [Sym("kicad_sch"),
           [Sym("version"), Sym("20250114")],
           [Sym("generator"), "gen_project.py"],
           [Sym("generator_version"), "9.0"],
           [Sym("uuid"), ROOT_UUID],
           [Sym("paper"), "A4"],
           [Sym("title_block"),
            [Sym("title"), TITLE],
            [Sym("date"), "2026-09-12"],
            [Sym("rev"), "A"],
            [Sym("comment"), Sym("1"), "50 ohm microstrip feed + pi matching network"],
            [Sym("comment"), Sym("2"), "Antenna keep-out: no copper on any layer"]],
           lib_symbols()]

    for a, b in WIRES:
        sch.append([Sym("wire"),
                    [Sym("pts"), [Sym("xy"), num(a[0]), num(a[1])],
                     [Sym("xy"), num(b[0]), num(b[1])]],
                    [Sym("stroke"), [Sym("width"), Sym("0")], [Sym("type"), Sym("default")]],
                    [Sym("uuid"), U("wire", str(a), str(b))]])
    for x, y in JUNCTIONS:
        sch.append([Sym("junction"),
                    [Sym("at"), num(x), num(y)],
                    [Sym("diameter"), Sym("0")],
                    [Sym("color"), Sym("0"), Sym("0"), Sym("0"), Sym("0")],
                    [Sym("uuid"), U("junction", str((x, y)))]])
    for name, (x, y) in LABELS:
        sch.append([Sym("label"), name,
                    [Sym("at"), num(x), num(y), Sym("0")],
                    effects(justify="left bottom"),
                    [Sym("uuid"), U("label", name)]])
    sch.append([Sym("text"), SCH_NOTE,
                [Sym("exclude_from_sim"), Sym("no")],
                [Sym("at"), num(76.2), num(112.0), Sym("0")],
                effects(size=1.27, justify="left top"),
                [Sym("uuid"), U("text", "note")]])

    for part in PARTS:
        sch.append(sch_symbol(part))
    for ref, pos in POWER:
        sch.append(sch_power(ref, pos))
    for ref, pos in PWR_FLAGS:
        sch.append(sch_power(ref, pos, name="PWR_FLAG", below=False, in_bom=False))

    sch.append([Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]])
    sch.append([Sym("embedded_fonts"), Sym("no")])
    return sch


# ---------------------------------------------------------------------- board
def rotate_at(node, rot):
    """Give a footprint child its absolute text/pad angle."""
    at = find(node, "at")
    if at is None or not rot:
        return
    angle = float(at[3]) if len(at) > 3 else 0.0
    angle = (angle + rot) % 360
    if len(at) > 3:
        at[3] = num(angle)
    else:
        at.append(num(angle))


def board_footprint(part) -> list:
    src = parse((FP_DIR / f"{part['fp']}.kicad_mod").read_text())
    x, y, rot = part["pcb"]
    out = [Sym("footprint"), f"{LIB_NICK}:{src[1]}",
           [Sym("layer"), "F.Cu"],
           [Sym("uuid"), U("fp", part["ref"])],
           [Sym("at"), num(x), num(y)] + ([num(rot)] if rot else [])]
    for child in src[2:]:
        head = child[0]
        if head in ("version", "generator", "generator_version", "layer", "embedded_fonts"):
            continue
        child = copy.deepcopy(child)
        if head == "property":
            if child[1] == "Reference":
                child[2] = part["ref"]
                if part.get("fp_ref_at"):
                    at = find(child, "at")
                    at[1], at[2] = num(part["fp_ref_at"][0]), num(part["fp_ref_at"][1])
            elif child[1] == "Value":
                child[2] = part["value"]
            rotate_at(child, rot)
            child.append([Sym("unlocked"), Sym("yes")])
        elif head == "fp_text":
            rotate_at(child, rot)
            child.append([Sym("unlocked"), Sym("yes")])
        elif head == "pad":
            rotate_at(child, rot)
            net = part["nets"].get(str(child[1]))
            if net is None:
                raise SystemExit(f"{part['ref']}: no net for pad {child[1]}")
            child.append([Sym("net"), Sym(str(NETS[net])), net])
            child.append([Sym("pinfunction"), net])
            child.append([Sym("pintype"), "passive"])
        out.append(child)
    out += [[Sym("path"), f"/{U('sym', part['ref'])}"],
            [Sym("sheetname"), "Root"],
            [Sym("sheetfile"), f"{PROJECT}.kicad_sch"],
            [Sym("embedded_fonts"), Sym("no")]]
    return out


def segment(a, b, width, net, layer="F.Cu"):
    return [Sym("segment"),
            [Sym("start"), num(a[0]), num(a[1])],
            [Sym("end"), num(b[0]), num(b[1])],
            [Sym("width"), num(width)],
            [Sym("layer"), layer],
            [Sym("net"), Sym(str(NETS[net]))],
            [Sym("uuid"), U("seg", str(a), str(b), str(width))]]


def via(pos, net="GND", size=0.6, drill=0.3):
    return [Sym("via"),
            [Sym("at"), num(pos[0]), num(pos[1])],
            [Sym("size"), num(size)],
            [Sym("drill"), num(drill)],
            [Sym("layers"), "F.Cu", "B.Cu"],
            [Sym("net"), Sym(str(NETS[net]))],
            [Sym("uuid"), U("via", str(pos))]]


def gr_line(a, b, layer, width=0.1):
    return [Sym("gr_line"),
            [Sym("start"), num(a[0]), num(a[1])],
            [Sym("end"), num(b[0]), num(b[1])],
            [Sym("stroke"), [Sym("width"), num(width)], [Sym("type"), Sym("solid")]],
            [Sym("layer"), layer],
            [Sym("uuid"), U("grline", str(a), str(b), layer)]]


def gr_text(text, pos, layer, size=1.0, thickness=0.15, justify="left"):
    return [Sym("gr_text"), text,
            [Sym("at"), num(pos[0]), num(pos[1]), Sym("0")],
            [Sym("layer"), layer],
            [Sym("uuid"), U("grtext", text, layer)],
            effects(size=size, justify=justify, thickness=thickness)]


def zone_poly(points):
    return [Sym("polygon"),
            [Sym("pts")] + [[Sym("xy"), num(px), num(py)] for px, py in points]]


def gnd_zone(layer, points):
    return [Sym("zone"),
            [Sym("net"), Sym("1")],
            [Sym("net_name"), "GND"],
            [Sym("layer"), layer],
            [Sym("uuid"), U("zone", layer)],
            [Sym("name"), "GND"],
            [Sym("hatch"), Sym("edge"), num(0.508)],
            [Sym("priority"), Sym("0")],
            [Sym("connect_pads"), [Sym("clearance"), num(0.2)]],
            [Sym("min_thickness"), num(0.25)],
            [Sym("filled_areas_thickness"), Sym("no")],
            [Sym("fill"), Sym("yes"),
             [Sym("thermal_gap"), num(0.4)],
             [Sym("thermal_bridge_width"), num(0.4)]],
            zone_poly(points)]


def keepout_zone(name, points, layers=("F.Cu", "B.Cu"), tracks="not_allowed",
                 vias="not_allowed"):
    return [Sym("zone"),
            [Sym("net"), Sym("0")],
            [Sym("net_name"), ""],
            [Sym("layers")] + [str(l) for l in layers],
            [Sym("uuid"), U("zone", name)],
            [Sym("name"), name],
            [Sym("hatch"), Sym("full"), num(0.508)],
            [Sym("connect_pads"), [Sym("clearance"), num(0)]],
            [Sym("min_thickness"), num(0.25)],
            [Sym("filled_areas_thickness"), Sym("no")],
            [Sym("keepout"),
             [Sym("tracks"), Sym(tracks)],
             [Sym("vias"), Sym(vias)],
             [Sym("pads"), Sym("allowed")],
             [Sym("copperpour"), Sym("not_allowed")],
             [Sym("footprints"), Sym("allowed")]],
            [Sym("fill"), [Sym("thermal_gap"), num(0.4)],
             [Sym("thermal_bridge_width"), num(0.4)]],
            zone_poly(points)]


def stackup():
    def layer(name, ltype, thickness=None, material=None, er=None, tand=None):
        node = [Sym("layer"), name, [Sym("type"), ltype]]
        if material:
            node.append([Sym("material"), material])
        if thickness is not None:
            node.append([Sym("thickness"), num(thickness)])
        if er is not None:
            node.append([Sym("epsilon_r"), num(er)])
        if tand is not None:
            node.append([Sym("loss_tangent"), num(tand)])
        return node

    return [Sym("stackup"),
            layer("F.SilkS", "Top Silk Screen"),
            layer("F.Paste", "Top Solder Paste"),
            layer("F.Mask", "Top Solder Mask", thickness=0.01),
            layer("F.Cu", "copper", thickness=0.035),
            layer("dielectric 1", "core", thickness=SUB_H, material="FR4",
                  er=SUB_ER, tand=SUB_TAND),
            layer("B.Cu", "copper", thickness=0.035),
            layer("B.Mask", "Bottom Solder Mask", thickness=0.01),
            layer("B.Paste", "Bottom Solder Paste"),
            layer("B.SilkS", "Bottom Silk Screen"),
            [Sym("copper_finish"), "None"],
            [Sym("dielectric_constraints"), Sym("no")]]


def build_board() -> list:
    layers = [(0, "F.Cu", "signal", None), (31, "B.Cu", "signal", None),
              (32, "B.Adhes", "user", "B.Adhesive"), (33, "F.Adhes", "user", "F.Adhesive"),
              (34, "B.Paste", "user", None), (35, "F.Paste", "user", None),
              (36, "B.SilkS", "user", "B.Silkscreen"), (37, "F.SilkS", "user", "F.Silkscreen"),
              (38, "B.Mask", "user", None), (39, "F.Mask", "user", None),
              (40, "Dwgs.User", "user", "User.Drawings"), (41, "Cmts.User", "user", "User.Comments"),
              (42, "Eco1.User", "user", "User.Eco1"), (43, "Eco2.User", "user", "User.Eco2"),
              (44, "Edge.Cuts", "user", None), (45, "Margin", "user", None),
              (46, "B.CrtYd", "user", "B.Courtyard"), (47, "F.CrtYd", "user", "F.Courtyard"),
              (48, "B.Fab", "user", None), (49, "F.Fab", "user", None)]
    layer_nodes = [Sym("layers")]
    for number, name, ltype, alias in layers:
        node = [Sym(str(number)), name, Sym(ltype)]
        if alias:
            node.append(alias)
        layer_nodes.append(node)

    pcb = [Sym("kicad_pcb"),
           [Sym("version"), Sym("20241229")],
           [Sym("generator"), "gen_project.py"],
           [Sym("generator_version"), "9.0"],
           [Sym("general"), [Sym("thickness"), num(SUB_H + 0.09)],
            [Sym("legacy_teardrops"), Sym("no")]],
           [Sym("paper"), "A4"],
           [Sym("title_block"),
            [Sym("title"), TITLE],
            [Sym("date"), "2026-09-12"],
            [Sym("rev"), "A"],
            [Sym("comment"), Sym("1"), "2 layer, 0.8 mm FR4, 35 um Cu"],
            [Sym("comment"), Sym("2"), "50 ohm microstrip w = 1.5 mm"]],
           layer_nodes,
           [Sym("setup"), stackup(),
            [Sym("pad_to_mask_clearance"), Sym("0")],
            [Sym("allow_soldermask_bridges_in_footprints"), Sym("no")]]]

    for name, number in NETS.items():
        pcb.append([Sym("net"), Sym(str(number)), name])

    for part in PARTS:
        pcb.append(board_footprint(part))

    # board outline
    corners = [(BOARD_X0, BOARD_Y0), (BOARD_X1, BOARD_Y0),
               (BOARD_X1, BOARD_Y1), (BOARD_X0, BOARD_Y1)]
    for i in range(4):
        pcb.append(gr_line(corners[i], corners[(i + 1) % 4], "Edge.Cuts"))

    # ground plane edge marker + notes
    pcb.append(gr_line((BOARD_X0, GND_EDGE_Y), (BOARD_X1, GND_EDGE_Y), "Cmts.User", 0.12))
    pcb.append(gr_text("GND plane edge - no copper above this line on any layer",
                       (BOARD_X0 + 0.8, GND_EDGE_Y - 0.8), "Cmts.User", size=0.9))
    pcb.append(gr_text("ANTENNA KEEP-OUT", (BOARD_X0 + 0.8, 63.2), "F.SilkS", size=1.0))
    pcb.append(gr_text("SWRA117D 2.45 GHz IFA - RF test board",
                       (BOARD_X0 + 1.0, 87.5), "F.SilkS", size=1.2))
    pcb.append(gr_text("50R microstrip w=1.5mm / 0.8mm FR4 er=4.4",
                       (BOARD_X0 + 1.0, 89.0), "F.SilkS", size=0.9))

    # 50 ohm feed: SMA -> pi network -> antenna feed pad
    tracks = [
        ((101.75, FEED_Y), (112.5, FEED_Y), W50, "RF_IN"),
        ((112.5, FEED_Y), (113.5, FEED_Y), W_NECK, "RF_IN"),
        ((113.5, FEED_Y), (117.52, FEED_Y), W_NECK, "RF_IN"),
        ((118.48, FEED_Y), (120.5, FEED_Y), W_NECK, "ANT_FEED"),
        ((120.5, FEED_Y), (121.5, FEED_Y), W_NECK, "ANT_FEED"),
        ((121.5, FEED_Y), (122.5, FEED_Y), W50, "ANT_FEED"),
        ((122.5, FEED_Y), (124.0, 73.5), W50, "ANT_FEED"),
        ((124.0, 73.5), (124.0, 67.0), W50, "ANT_FEED"),
        ((124.0, 67.0), (124.0, 66.0), W_NECK, "ANT_FEED"),
    ]
    for a, b, width, net in tracks:
        pcb.append(segment(a, b, width, net))

    # shunt capacitor ground returns: pad -> via -> bottom plane
    for x in (113.5, 120.5):
        pcb.append(segment((x, FEED_Y + 0.99), (x, FEED_Y + 2.0), W_NECK, "GND"))

    # ground stitching
    stitch = [(101.0, 72.0), (103.0, 72.0), (101.0, 78.0), (103.0, 78.0),
              (113.5, FEED_Y + 2.0), (120.5, FEED_Y + 2.0)]
    stitch += [(x, GND_EDGE_Y + 1.0) for x in
               (103, 106, 109, 112, 115, 118, 121, 127.5, 130.5, 133.5, 136.5)]
    for pos in stitch:
        pcb.append(via(pos))

    plane = [(BOARD_X0 + 0.2, GND_EDGE_Y), (BOARD_X1 - 0.2, GND_EDGE_Y),
             (BOARD_X1 - 0.2, BOARD_Y1 - 0.2), (BOARD_X0 + 0.2, BOARD_Y1 - 0.2)]
    pcb.append(gnd_zone("F.Cu", plane))
    pcb.append(gnd_zone("B.Cu", plane))
    pcb.append(keepout_zone("ANTENNA_KEEPOUT",
                            [(BOARD_X0 - 0.5, BOARD_Y0 - 0.5), (BOARD_X1 + 0.5, BOARD_Y0 - 0.5),
                             (BOARD_X1 + 0.5, GND_EDGE_Y), (BOARD_X0 - 0.5, GND_EDGE_Y)]))
    # Keep the top pour POUR_GAP away from the 50 ohm line so it stays a
    # microstrip referenced to the bottom plane instead of turning into a
    # narrow-gap coplanar waveguide.  Tracks, vias and pads stay legal.
    half = W50 / 2 + POUR_GAP
    pcb.append(keepout_zone("RF_POUR_KEEPAWAY_H",
                            [(BOARD_X0 - 0.5, FEED_Y - half), (125.75, FEED_Y - half),
                             (125.75, FEED_Y + half), (BOARD_X0 - 0.5, FEED_Y + half)],
                            layers=("F.Cu",), tracks="allowed", vias="allowed"))
    pcb.append(keepout_zone("RF_POUR_KEEPAWAY_V",
                            [(122.25, GND_EDGE_Y), (125.75, GND_EDGE_Y),
                             (125.75, FEED_Y + half), (122.25, FEED_Y + half)],
                            layers=("F.Cu",), tracks="allowed", vias="allowed"))
    pcb.append([Sym("embedded_fonts"), Sym("no")])
    return pcb


# -------------------------------------------------------------------- project
def build_project() -> dict:
    def netclass(name, clearance, width, priority):
        return {
            "bus_width": 12, "clearance": clearance, "diff_pair_gap": 0.25,
            "diff_pair_via_gap": 0.25, "diff_pair_width": 0.2, "line_style": 0,
            "microvia_diameter": 0.3, "microvia_drill": 0.1, "name": name,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "priority": priority,
            "schematic_color": "rgba(0, 0, 0, 0.000)", "track_width": width,
            "via_diameter": 0.6, "via_drill": 0.3, "wire_width": 6,
        }

    return {
        "board": {
            "3dviewports": [],
            "design_settings": {
                "defaults": {
                    "board_outline_line_width": 0.1,
                    "copper_line_width": 0.2,
                    "copper_text_size_h": 1.0,
                    "copper_text_size_v": 1.0,
                    "copper_text_thickness": 0.15,
                    "other_line_width": 0.15,
                    "silk_line_width": 0.15,
                    "silk_text_size_h": 1.0,
                    "silk_text_size_v": 1.0,
                    "silk_text_thickness": 0.15,
                },
                "diff_pair_dimensions": [],
                "drc_exclusions": [],
                "rules": {
                    "min_clearance": 0.15,
                    "min_copper_edge_clearance": 0.2,
                    "min_hole_clearance": 0.2,
                    "min_microvia_diameter": 0.2,
                    "min_microvia_drill": 0.1,
                    "min_through_hole_diameter": 0.2,
                    "min_track_width": 0.15,
                    "min_via_annular_width": 0.1,
                    "min_via_diameter": 0.5,
                },
                "track_widths": [0.0, 0.25, 0.5, 1.5],
                "via_dimensions": [{"diameter": 0.0, "drill": 0.0},
                                   {"diameter": 0.6, "drill": 0.3}],
            },
            "layer_presets": [],
            "viewports": [],
        },
        "boards": [],
        "cvpcb": {"equivalence_files": []},
        "libraries": {"pinned_footprint_libs": [], "pinned_symbol_libs": []},
        "meta": {"filename": f"{PROJECT}.kicad_pro", "version": 3},
        "net_settings": {
            "classes": [netclass("Default", 0.2, 0.25, 2147483647),
                        netclass("RF_50R", 0.3, W50, 0)],
            "meta": {"version": 4},
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [{"netclass": "RF_50R", "pattern": "RF_IN"},
                                  {"netclass": "RF_50R", "pattern": "ANT_FEED"}],
        },
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "",
                                  "plot": "", "pos_files": "", "specctra_dsn": "",
                                  "step": "", "svg": "", "vrml": ""},
                   "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[ROOT_UUID, "Root"]],
        "text_variables": {},
    }


def main() -> None:
    sch_path = PRJ_DIR / f"{PROJECT}.kicad_sch"
    pcb_path = PRJ_DIR / f"{PROJECT}.kicad_pcb"
    pro_path = PRJ_DIR / f"{PROJECT}.kicad_pro"
    sch_path.write_text(dumps(build_schematic()) + "\n")
    pcb_path.write_text(dumps(build_board()) + "\n")
    pro_path.write_text(json.dumps(build_project(), indent=2) + "\n")
    for path in (sch_path, pcb_path, pro_path):
        print(f"wrote {path.relative_to(PRJ_DIR.parent)}")


if __name__ == "__main__":
    main()
