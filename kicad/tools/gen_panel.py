#!/usr/bin/env python3
"""Panelise the three common-plane kit boards into one fabrication order.

The three ``*_common`` boards exist to be compared with each other, so they
were generated with one outline - 55 x 90 mm - on purpose.  That means they
panelise: three in a row, butted, 165 x 90 mm, separated by two V-score lines.
One order, one stackup, one delivery, and three boards that came off the same
piece of laminate, which removes the last variable between them.

What this has to get right, and what a naive merge gets wrong:

  * **References must become unique.**  Three boards each carry J1, Z1, Z2,
    Z3 and AE1.  Merged as-is, the pick-and-place file has three J1s at three
    different places and nobody can tell which is which.  Each board's
    reference is prefixed here.
  * **Nets must NOT merge.**  Three GNDs merged into one net would tell DRC
    that three separate boards are connected.  Each board's nets are renamed
    and renumbered into its own set.
  * **UUIDs must be unique.**  Three copies of the same board carry three
    copies of every uuid; KiCad will load that, and then behave oddly.  Every
    uuid is rewritten deterministically.
  * **Only the panel has an outline.**  The boards' own Edge.Cuts become the
    V-score lines, on a documentation layer, because a fab reads Edge.Cuts as
    "route this" and would cut the panel into three before shipping it.

V-score wants copper clear of the scoring line.  These boards have 5 mm of
bare laminate either side of the ground plane, so there is nothing to check
that is remotely close - but ``check_panel.py`` checks it anyway.

    python3 kicad/tools/gen_panel.py
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_kit as kit  # noqa: E402
import gen_project as gp  # noqa: E402
from sexpr import Sym, dumps, find, find_all, num, parse  # noqa: E402

PRJ_DIR = gp.PRJ_DIR
OUT_DIR = PRJ_DIR / "kit" / "panel_common"
PROJECT = "kit_panel_common"
NAMESPACE = uuid.UUID("9c5a7e31-4b08-5d62-a7f9-31c0ae6b5d42")

# sub-GHz first, then 2.4 - so the panel reads in frequency order
ORDER = ["dn023_common", "dn024_common", "an043_common"]
PREFIX = {"dn023_common": "A", "dn024_common": "B", "an043_common": "C"}
VSCORE_LAYER = "Cmts.User"
PANEL_ORIGIN = (50.0, 50.0)

# nodes whose coordinates are absolute and therefore have to move
MOVING = {"segment", "via", "gr_line", "gr_text", "gr_poly", "gr_rect",
          "gr_circle", "gr_arc", "gr_curve", "zone", "dimension", "arc"}


def translate(node, dx, dy, top=True):
    """Shift one top-level board object. Footprint interiors are local."""
    tag = str(node[0])
    if tag == "footprint":
        at = find(node, "at")
        at[1], at[2] = num(float(at[1]) + dx), num(float(at[2]) + dy)
        return node                      # everything inside is footprint-local
    for child in node:
        if not isinstance(child, list) or not child:
            continue
        ctag = str(child[0])
        if ctag in ("at", "start", "end", "center", "mid", "xy"):
            child[1] = num(float(child[1]) + dx)
            child[2] = num(float(child[2]) + dy)
        else:
            translate(child, dx, dy, top=False)
    return node


def rewrite_uuids(node, salt):
    for child in node:
        if isinstance(child, list) and child:
            if str(child[0]) == "uuid":
                child[1] = str(uuid.uuid5(NAMESPACE, f"{salt}:{child[1]}"))
            else:
                rewrite_uuids(child, salt)
    return node


def rewrite_nets(node, mapping, by_name):
    """Point every net reference at this board's own renumbered net.

    A zone carries both ``(net N)`` and ``(net_name "X")`` and KiCad believes
    the name, so renumbering one without the other leaves a zone attached to
    whatever net happens to be called X - which, on a panel, is another
    board's.
    """
    for child in node:
        if not isinstance(child, list) or not child:
            continue
        ctag = str(child[0])
        if ctag == "net" and len(child) >= 2 and str(child[1]).isdigit():
            number, name = mapping[int(child[1])]
            child[1] = Sym(str(number))
            if len(child) >= 3:
                child[2] = name
        elif ctag == "net_name":
            child[1] = by_name[str(child[1])]
        else:
            rewrite_nets(child, mapping, by_name)
    return node


def board_path(key):
    return PRJ_DIR / "kit" / key / f"kit_{key}.kicad_pcb"


def build() -> list:
    specs = {s["key"]: s for s in kit.all_specs()}
    width = specs[ORDER[0]]["board_w"]
    height = specs[ORDER[0]]["board_h"]
    for key in ORDER:
        s = specs[key]
        if (s["board_w"], s["board_h"]) != (width, height):
            raise SystemExit(
                f"{key} is {s['board_w']} x {s['board_h']} mm, not "
                f"{width} x {height}: these boards no longer panelise")

    px, py = PANEL_ORIGIN
    panel = None
    nets_out = [("", 0)]
    bodies = []

    for i, key in enumerate(ORDER):
        pcb = parse(board_path(key).read_text())
        spec = specs[key]
        bx0, by0 = spec["board"][0], spec["board"][1]
        dx = px + i * width - bx0
        dy = py - by0

        # this board's nets become its own set: GND_A, ANT_FEED_A, ...
        mapping = {0: (0, "")}
        by_name = {"": ""}
        for net in [n for n in pcb if isinstance(n, list) and str(n[0]) == "net"]:
            number, name = int(net[1]), str(net[2])
            if number == 0:
                continue
            renamed = f"{name}_{PREFIX[key]}"
            mapping[number] = (len(nets_out), renamed)
            by_name[name] = renamed
            nets_out.append((renamed, len(nets_out)))

        if panel is None:
            panel = [n for n in pcb[:1]] + [
                n for n in pcb
                if isinstance(n, list) and str(n[0]) in (
                    "version", "generator", "generator_version", "general",
                    "paper", "layers", "setup")]

        for node in pcb:
            if not isinstance(node, list) or str(node[0]) not in MOVING | {"footprint"}:
                continue
            if str(node[0]) == "gr_line" and str(find(node, "layer")[1]) == "Edge.Cuts":
                continue                       # the panel draws its own outline
            node = rewrite_uuids(node, f"{key}:{i}")
            node = rewrite_nets(node, mapping, by_name)
            node = translate(node, dx, dy)
            if str(node[0]) == "footprint":
                for prop in find_all(node, "property"):
                    if str(prop[1]) == "Reference":
                        prop[2] = f"{PREFIX[key]}{prop[2]}"
            bodies.append(node)

    panel[0] = Sym("kicad_pcb")
    for node in panel:
        if isinstance(node, list) and str(node[0]) == "generator":
            node[1] = "gen_panel.py"
    panel.append([Sym("title_block"),
                  [Sym("title"), "PCB antenna evaluation kit - common plane "
                                 "panel, 3 up, V-scored"],
                  [Sym("date"), "2026-10-07"], [Sym("rev"), "A"],
                  [Sym("comment"), Sym("1"),
                   f"{len(ORDER) * width:g} x {height:g} mm, {gp.SUB_H} mm FR4, "
                   "2 layer, V-score on the two internal lines"],
                  [Sym("comment"), Sym("2"),
                   " | ".join(f"{PREFIX[k]} = {k}" for k in ORDER)]])
    for name, number in nets_out:
        panel.append([Sym("net"), Sym(str(number)), name])
    panel += bodies

    # The panel's own outline, V-score lines and labels.  They go through
    # rewrite_uuids too: gp.gr_text keys its uuid off the text, so two labels
    # that read the same - both V-score lines say "V-SCORE" - would otherwise
    # come out carrying one identifier between them.
    w, h = len(ORDER) * width, height
    corners = [(px, py), (px + w, py), (px + w, py + h), (px, py + h)]
    furniture = [gp.gr_line(corners[i], corners[(i + 1) % 4], "Edge.Cuts")
                 for i in range(4)]
    for i in range(1, len(ORDER)):
        x = px + i * width
        furniture.append(gp.gr_line((x, py), (x, py + h), VSCORE_LAYER, 0.2))
        furniture.append(gp.gr_text("V-SCORE", (x + 0.4, py + 4.0),
                                    VSCORE_LAYER, size=1.2))
    furniture.append(gp.gr_text(
        f"V-SCORE on the {len(ORDER) - 1} marked lines only. Panel "
        f"{w:g} x {h:g} mm, {gp.SUB_H} mm FR4, 2 layer, 1 oz, HASL or ENIG.",
        (px + 1.0, py - 1.5), VSCORE_LAYER, size=1.0))
    for i, key in enumerate(ORDER):
        furniture.append(gp.gr_text(
            f"{PREFIX[key]}  {key}", (px + i * width + 1.5, py + h - 1.5),
            "F.SilkS", size=1.0))
    for i, node in enumerate(furniture):
        panel.append(rewrite_uuids(node, f"panel:furniture:{i}"))
    panel.append([Sym("embedded_fonts"), Sym("no")])
    return panel


def main() -> None:
    argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    gp.NAMESPACE = NAMESPACE
    gp.ROOT_UUID = gp.U("sheet", "panel")
    gp.PROJECT = PROJECT
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = OUT_DIR / f"{PROJECT}.kicad_pcb"
    dest.write_text(dumps(build()) + "\n")
    specs = {s["key"]: s for s in kit.all_specs()}
    w = len(ORDER) * specs[ORDER[0]]["board_w"]
    h = specs[ORDER[0]]["board_h"]
    print(f"wrote {dest.relative_to(PRJ_DIR.parent)}")
    print(f"  {len(ORDER)} up, {w:g} x {h:g} mm, V-score on "
          f"{len(ORDER) - 1} internal lines")
    for key in ORDER:
        print(f"    {PREFIX[key]}  {key}")
    (OUT_DIR / f"{PROJECT}.kicad_pro").write_text(
        json.dumps(gp.build_project(), indent=2) + "\n")
    print(f"wrote {(OUT_DIR / f'{PROJECT}.kicad_pro').relative_to(PRJ_DIR.parent)}")


if __name__ == "__main__":
    main()
