#!/usr/bin/env python3
"""Build the kit's bill of materials, out of the board files.

Read from the written ``.kicad_pcb`` rather than from the generator's tables,
so the BOM says what is actually on the board.  A part whose value is DNP is
a land with nothing on it: it still appears, marked not fitted, because the
whole reason those sites exist is that somebody may need to fit them later
and a BOM that hides them hides that.

Manufacturer parts are given only where an application note names one.  The
3.9 pF is SWRA227E's own; the 0 ohm links and the unfitted sites are generic
by nature, and nothing here invents a part number.

    python3 kicad/tools/gen_bom.py
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_kit as kit  # noqa: E402
import gen_panel as panel  # noqa: E402
from sexpr import find, find_all, parse  # noqa: E402

OUT_DIR = kit.PRJ_DIR / "kit" / "fab"

# Only where a note or a manufacturer names the part.
PARTS = {
    "U.FL receptacle": ("Hirose U.FL-R-SMT-1(10)",
                        "mates with a U.FL to SMA pigtail, not supplied on "
                        "the board"),
    "3.9pF": ("Murata GRM1555C1H3R9CZ01D",
              "SWRA227E Table 3, dual band; C0G 0402"),
    "0R": ("any 0402 0 ohm link", "no matching values are published for this "
                                  "antenna; the link makes the site a through"),
    "DNP": ("", "land laid out, nothing fitted - for compensating an "
                "enclosure later (AN058, and SWRA228C section 3)"),
}


def rows_for(pcb_path: pathlib.Path) -> list[dict]:
    pcb = parse(pcb_path.read_text())
    out = []
    for fp in find_all(pcb, "footprint"):
        props = {str(p[1]): str(p[2]) for p in find_all(fp, "property")}
        ref, value = props.get("Reference", "?"), props.get("Value", "")
        if ref.startswith("#") or not value:
            continue
        name = str(fp[1]).rpartition(":")[2]
        if "Monopole" in name or "IFA" in name or "GHz" in name:
            continue                       # the antenna is etched, not bought
        mpn, note = PARTS.get(value, ("", ""))
        out.append(dict(reference=ref, value=value, footprint=name,
                        fitted="no" if value == "DNP" else "yes",
                        manufacturer_part=mpn, note=note))
    return sorted(out, key=lambda r: r["reference"])


def group(rows: list[dict]) -> list[dict]:
    by = {}
    for r in rows:
        key = (r["value"], r["footprint"])
        by.setdefault(key, {**r, "reference": []})["reference"].append(
            r["reference"])
    out = []
    for r in by.values():
        refs = sorted(r["reference"])
        out.append({**r, "reference": " ".join(refs), "qty": len(refs)})
    return sorted(out, key=lambda r: (r["fitted"] == "no", r["reference"]))


FIELDS = ["reference", "qty", "value", "footprint", "fitted",
          "manufacturer_part", "note"]


def write_csv(dest: pathlib.Path, rows: list[dict]) -> None:
    with dest.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in FIELDS})


def main() -> None:
    argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    made = []
    for key in panel.ORDER:
        rows = group(rows_for(kit.OUT_DIR / key / f"kit_{key}.kicad_pcb"))
        dest = OUT_DIR / f"bom_{key}.csv"
        write_csv(dest, rows)
        made.append((key, rows, dest))

    panel_rows = group(rows_for(
        panel.OUT_DIR / f"{panel.PROJECT}.kicad_pcb"))
    dest = OUT_DIR / f"bom_{panel.PROJECT}.csv"
    write_csv(dest, panel_rows)

    for key, rows, path in made:
        fitted = sum(r["qty"] for r in rows if r["fitted"] == "yes")
        print(f"{key:14} {len(rows)} line(s), {fitted} part(s) fitted "
              f"-> {path.relative_to(kit.PRJ_DIR.parent)}")
    fitted = sum(r["qty"] for r in panel_rows if r["fitted"] == "yes")
    print(f"{'panel (3 up)':14} {len(panel_rows)} line(s), {fitted} part(s) "
          f"fitted -> {dest.relative_to(kit.PRJ_DIR.parent)}")
    print("\nfitted parts on the panel:")
    for r in panel_rows:
        if r["fitted"] == "yes":
            print(f"  {r['qty']} x {r['value']:16} {r['reference']:18} "
                  f"{r['manufacturer_part']}")
    print("\nnot on the board, but needed to measure:")
    print("  3 x U.FL to SMA bulkhead pigtail, <= 300 mm, RG178 or RG316")
    print("  3 x clamp ferrite for the pigtail - without it the cable braid "
          "is part of the antenna")


if __name__ == "__main__":
    main()
