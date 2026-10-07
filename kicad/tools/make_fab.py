#!/usr/bin/env python3
"""Export fabrication files for the kit panel.

Gerbers, Excellon drill, pick-and-place and a zip, from the panel that
``gen_panel.py`` builds.

THE ZONES HAVE TO BE FILLED FIRST, and this is the whole reason this script
exists rather than a line in a README.  KiCad stores a zone as an outline
with no copper until somebody presses B and saves; every board in this
repository is written by a script and therefore ships unfilled.  Exporting
gerbers from an unfilled board does not warn you - it hands you a board with
**no ground plane at all**, which is the same fault that made a full-wave run
meaningless earlier in this project, except that this time you pay a fab house
to make it.

So the order is: fill, verify the fill exists, export, verify the files are
there.  The fill is done with KiCad's own ``pcbnew`` module, which is the only
thing entitled to do it - an approximation written here would be copper that
disagrees with KiCad's own DRC.

Needs KiCad 9 installed (``kicad-cli`` on PATH and ``pcbnew`` importable).
Without it the script says so and stops rather than producing something
plausible and wrong.

    python3 kicad/tools/make_fab.py
    python3 kicad/tools/make_fab.py --board kit/dn024_common/kit_dn024_common.kicad_pcb
"""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_panel as panel  # noqa: E402
from sexpr import find_all, parse  # noqa: E402

PRJ_DIR = panel.PRJ_DIR
OUT_DIR = PRJ_DIR / "kit" / "fab"
LAYERS = ("F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,"
          "F.Mask,B.Mask,Edge.Cuts,User.Comments")


def need(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        raise SystemExit(
            f"{tool} is not on PATH. This step needs KiCad 9 installed; the "
            f"generators and checkers in this repository do not, which is why "
            f"everything else runs anywhere.\n"
            f"  Debian/Ubuntu: sudo add-apt-repository ppa:kicad/kicad-9.0-releases"
            f" && sudo apt install kicad\n"
            f"  macOS:         brew install --cask kicad\n"
            f"The CI workflow in .github/workflows/pcb.yml does this and "
            f"publishes the result as a build artifact.")
    return path


def fill_zones(src: pathlib.Path, dest: pathlib.Path) -> int:
    """Fill with KiCad's own filler and save a copy. Returns zones filled."""
    try:
        import pcbnew                                    # noqa: PLC0415
    except ImportError:
        raise SystemExit(
            "KiCad's pcbnew module is not importable, so the zones cannot be "
            "filled, so the gerbers would come out with no ground plane. "
            "Install KiCad 9, or open the board, press B, save, and re-run "
            "with --already-filled.")
    board = pcbnew.LoadBoard(str(src))
    zones = board.Zones()
    pcbnew.ZONE_FILLER(board).Fill(zones)
    pcbnew.SaveBoard(str(dest), board)
    return len(list(zones))


def filled_count(path: pathlib.Path) -> int:
    pcb = parse(path.read_text())
    return len(find_all(pcb, "zone")) and sum(
        1 for z in find_all(pcb, "zone") if find_all(z, "filled_polygon"))


def run(*args) -> None:
    print("   $ " + " ".join(str(a) for a in args))
    subprocess.run([str(a) for a in args], check=True)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--board", default=None,
                    help="board to export (default: the 3-up panel)")
    ap.add_argument("--already-filled", action="store_true",
                    help="the board was filled and saved in KiCad already")
    args = ap.parse_args()

    src = (PRJ_DIR / args.board if args.board
           else panel.OUT_DIR / f"{panel.PROJECT}.kicad_pcb")
    if not src.exists():
        raise SystemExit(f"missing {src} - run tools/gen_panel.py")
    name = src.stem
    out = OUT_DIR / name
    gerbers = out / "gerber"
    if out.exists():
        shutil.rmtree(out)
    gerbers.mkdir(parents=True)

    cli = need("kicad-cli")
    print(f"exporting {src.relative_to(PRJ_DIR.parent)}")

    if args.already_filled:
        board = src
    else:
        board = out / f"{name}_filled.kicad_pcb"
        n = fill_zones(src, board)
        print(f"   filled {n} zone(s) with KiCad's own filler")

    have = filled_count(board)
    if not have:
        raise SystemExit(
            f"{board.name} still carries no filled_polygon. Exporting now "
            "would hand the fab a board with no copper pour - refusing.")
    print(f"   {have} zone(s) carry copper")

    run(cli, "pcb", "export", "gerbers", "--output", gerbers,
        "--layers", LAYERS, "--no-protel-ext", board)
    run(cli, "pcb", "export", "drill", "--output", gerbers,
        "--format", "excellon", "--drill-origin", "absolute",
        "--excellon-units", "mm", "--generate-map", "--map-format", "gerberx2",
        board)
    run(cli, "pcb", "export", "pos", "--output", out / f"{name}-pos.csv",
        "--format", "csv", "--units", "mm", "--side", "both", board)

    produced = sorted(p for p in gerbers.iterdir() if p.is_file())
    empty = [p.name for p in produced if p.stat().st_size == 0]
    if empty:
        raise SystemExit(f"these exports came out empty: {', '.join(empty)}")
    archive = shutil.make_archive(str(out / f"{name}-gerber"), "zip", gerbers)
    print(f"   {len(produced)} gerber/drill files")
    for p in produced:
        print(f"      {p.name}  {p.stat().st_size:>8} bytes")
    print(f"\nwrote {pathlib.Path(archive).relative_to(PRJ_DIR.parent)}")
    print(f"wrote {(out / f'{name}-pos.csv').relative_to(PRJ_DIR.parent)}")
    print("\nOrder as: 2 layer, 1.6 mm FR4, 1 oz copper, HASL or ENIG, "
          "V-score on the 2 marked lines (User.Comments).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
