#!/usr/bin/env python3
"""Convert a legacy (KiCad 4/5) ``.kicad_mod`` to the modern s-expression format.

The modern format is what KiCad 8/9/10 write: ``footprint`` instead of
``module``, ``property`` instead of the reference/value ``fp_text`` items,
``stroke`` blocks instead of bare ``width``, quoted layer names and a UUID on
every item.

    ./convert_legacy_footprint.py old.kicad_mod new.kicad_mod

Only the element types used by the TI SWRA117D antenna footprints are
handled; anything else raises so a silent mis-conversion is impossible.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from sexpr import Sym, dumps, find, parse  # noqa: E402

FORMAT_VERSION = Sym("20241229")  # KiCad 9.0 footprint format
NAMESPACE = uuid.UUID("2f1d9f1a-7f9c-5b2e-9d2a-1c4a5e6f7081")

# legacy (attr ...) values -> modern footprint attributes
LEGACY_ATTRS = {
    "virtual": [Sym("exclude_from_pos_files"), Sym("exclude_from_bom")],
    "smd": [Sym("smd")],
    "through_hole": [Sym("through_hole")],
}


def det_uuid(*parts: str) -> str:
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


class Converter:
    def __init__(self, name: str):
        self.name = name
        self.counter = 0

    def uuid_item(self) -> list:
        self.counter += 1
        return [Sym("uuid"), det_uuid(self.name, str(self.counter))]

    def stroke(self, width) -> list:
        return [Sym("stroke"), [Sym("width"), width], [Sym("type"), Sym("solid")]]

    def text(self, node: list) -> list:
        kind, value = node[1], node[2]
        at = find(node, "at")
        layer = find(node, "layer")
        effects = find(node, "effects")
        body = [[Sym("at")] + list(at[1:]), [Sym("layer"), str(layer[1])], self.uuid_item()]
        if effects is not None:
            body.append(effects)
        if kind in ("reference", "value"):
            prop = "Reference" if kind == "reference" else "Value"
            return [Sym("property"), prop, str(value)] + body
        return [Sym("fp_text"), kind, str(value)] + body

    def line(self, node: list) -> list:
        width = find(node, "width")
        return [
            Sym("fp_line"),
            find(node, "start"),
            find(node, "end"),
            self.stroke(width[1]),
            [Sym("layer"), str(find(node, "layer")[1])],
            self.uuid_item(),
        ]

    def poly(self, node: list) -> list:
        width = find(node, "width")
        return [
            Sym("fp_poly"),
            find(node, "pts"),
            self.stroke(width[1]),
            [Sym("fill"), Sym("yes")],
            [Sym("layer"), str(find(node, "layer")[1])],
            self.uuid_item(),
        ]

    def pad(self, node: list) -> list:
        number, pad_type, shape = str(node[1]), node[2], node[3]
        if pad_type == "connect":  # v5 "connect" == SMD pad with no paste/mask
            pad_type = Sym("smd")
        out = [Sym("pad"), number, pad_type, shape]
        for child in node[4:]:
            if child[0] == "layers":
                out.append([Sym("layers")] + [str(layer) for layer in child[1:]])
            else:
                out.append(child)
        out.append(self.uuid_item())
        return out


def convert(text: str, descr_override: str | None = None) -> str:
    module = parse(text)
    if module[0] != "module":
        raise SystemExit("not a legacy footprint (expected a 'module' element)")
    name = str(module[1])
    conv = Converter(name)

    out = [
        Sym("footprint"),
        name,
        [Sym("version"), FORMAT_VERSION],
        [Sym("generator"), "convert_legacy_footprint.py"],
        [Sym("generator_version"), "9.0"],
        [Sym("layer"), str(find(module, "layer")[1])],
    ]
    texts, graphics, pads = [], [], []
    for child in module[2:]:
        head = child[0]
        if head in ("layer", "tedit", "tstamp"):
            continue
        if head == "descr":
            out.append([Sym("descr"), descr_override or str(child[1])])
        elif head == "tags":
            out.append([Sym("tags"), str(child[1])])
        elif head == "attr":
            out.append([Sym("attr")] + LEGACY_ATTRS[str(child[1])])
        elif head == "fp_text":
            texts.append(conv.text(child))
        elif head == "fp_line":
            graphics.append(conv.line(child))
        elif head == "fp_poly":
            graphics.append(conv.poly(child))
        elif head == "pad":
            pads.append(conv.pad(child))
        else:
            raise SystemExit(f"unhandled legacy element: {head}")

    out += texts + graphics + pads
    out.append([Sym("embedded_fonts"), Sym("no")])
    return dumps(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("source", type=pathlib.Path)
    ap.add_argument("dest", type=pathlib.Path)
    ap.add_argument("--descr", help="replace the footprint description")
    args = ap.parse_args()
    args.dest.write_text(convert(args.source.read_text(), args.descr))
    print(f"wrote {args.dest}")


if __name__ == "__main__":
    main()
