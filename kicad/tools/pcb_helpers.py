"""KiCad file-writing helpers shared by the tracker's generator.

The same functions as in ``gen_project.py``, taken out so the tracker
project depends on nothing but this module, ``sexpr.py`` and
``line_impedance.py``: importing ``gen_project`` reads the SWRA117D
antenna footprint, which a checkout of the tracker alone does not have.

Module state the caller sets before use: NAMESPACE, ROOT_UUID, PROJECT,
NETS and W50 (the width ``build_project`` writes into its RF net class).
"""

from __future__ import annotations

import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, find, num  # noqa: E402

HERE = pathlib.Path(__file__).resolve().parent
PRJ_DIR = HERE.parent
LIB_DIR = PRJ_DIR / "library"

NAMESPACE = uuid.UUID("3f6b2d0e-9c41-5a7e-b2d8-6a1c4e9f0b37")
PROJECT = ""
NETS: dict = {}
W50 = 0.0


def U(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


ROOT_UUID = U("sheet", "root")


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
            "netclass_patterns": [{"netclass": "RF_50R", "pattern": "ANT_FEED"},
                                  {"netclass": "RF_50R", "pattern": "RF_IN"}],
        },
        "pcbnew": {"last_paths": {"gencad": "", "idf": "", "netlist": "",
                                  "plot": "", "pos_files": "", "specctra_dsn": "",
                                  "step": "", "svg": "", "vrml": ""},
                   "page_layout_descr_file": ""},
        "schematic": {"legacy_lib_dir": "", "legacy_lib_list": []},
        "sheets": [[ROOT_UUID, "Root"]],
        "text_variables": {},
    }
