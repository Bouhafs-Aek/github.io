#!/usr/bin/env python3
"""Regenerate every drawing in docs/, from one list rather than six commands.

A list of render commands kept in a CI file drifts the moment a board is
added: the new board has no drawing, and nothing says so.  Here the list is
the mapping below, and ``--check`` fails if any drawing is missing or stale,
which is what CI runs.

    python3 kicad/tools/gen_drawings.py
    python3 kicad/tools/gen_drawings.py --check
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import board_to_svg  # noqa: E402
import gen_panel as panel  # noqa: E402

PRJ_DIR = pathlib.Path(__file__).resolve().parent.parent
DOCS = PRJ_DIR / "docs"

DRAWINGS = {
    "board-drawing.svg": "swra117d_2g4_antenna.kicad_pcb",
    "sim-board-drawing.svg": "sim/board/swra117d_2g4_sim.kicad_pcb",
    "dn024-board-drawing.svg": "dn024/dn024_monopole_868_2440.kicad_pcb",
    "dn024-ti-form-drawing.svg": "dn024_ti_form/dn024_monopole_ti_form.kicad_pcb",
    "dn024-sim-board-drawing.svg": "sim/board/dn024_monopole_sim.kicad_pcb",
}
for _key in ("an043_ref", "an043_common", "dn023_ref", "dn023_common",
             "dn024_ref", "dn024_common"):
    DRAWINGS[f"kit/{_key}.svg"] = f"kit/{_key}/kit_{_key}.kicad_pcb"
DRAWINGS[f"kit/{panel.PROJECT}.svg"] = (
    f"kit/panel_common/{panel.PROJECT}.kicad_pcb")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true",
                    help="fail if a drawing is missing or out of date")
    args = ap.parse_args()

    stale = []
    for name, source in DRAWINGS.items():
        dest, src = DOCS / name, PRJ_DIR / source
        if not src.exists():
            print(f"FAIL {source} does not exist")
            return 1
        svg = board_to_svg.render(src)
        if args.check:
            if not dest.exists() or dest.read_text() != svg:
                stale.append(name)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(svg)
            print(f"wrote docs/{name} ({len(svg)} bytes)")
    if args.check:
        for name in stale:
            print(f"FAIL docs/{name} is missing or does not match its board")
        print(f"\n{len(stale)} stale drawing(s) of {len(DRAWINGS)}")
        return 1 if stale else 0
    print(f"\n{len(DRAWINGS)} drawing(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
