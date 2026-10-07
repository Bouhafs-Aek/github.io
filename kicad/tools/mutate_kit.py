#!/usr/bin/env python3
"""Break the kit on purpose, one fault at a time, and see if check_kit says so.

A checker that has never failed is a checker nobody has tested.  Each mutation
below is a mistake that is easy to make and invisible in the PCB editor; the
test is that the checker names it.  The kit is regenerated clean afterwards.

    python3 kicad/tools/mutate_kit.py
"""

from __future__ import annotations

import contextlib
import io
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import gen_kit as kit  # noqa: E402


def run_check() -> list[str]:
    import importlib
    import check_kit
    importlib.reload(check_kit)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        check_kit.main()
    return [l for l in buf.getvalue().splitlines() if l.startswith("FAIL")]


def regenerate() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        for s in kit.all_specs():
            kit.write(s)


MUTATIONS = [
    ("the antenna is not centred on the board",
     lambda: setattr(kit, "SIDE_MARGIN", kit.SIDE_MARGIN),
     "off_centre"),
    ("the board is too narrow for the 5 mm either side SWRA228C asks for",
     None, "narrow"),
    ("the shorting leg never reaches the plane", None, "no_short"),
    ("Z2 is wired as a shunt instead of in series", None, "z2_shunt"),
    ("one common-plane board gets a different plane", None, "odd_plane"),
    ("AE1 is placed so its feed pin misses the bus", None, "pin_off"),
    ("the antenna is pushed down over the plane edge", None, "over_plane"),
    ("a ground pour goes missing from the bottom layer", None, "one_layer"),
]


def apply(name):
    """Return an undo callable."""
    if name == "off_centre":
        orig = kit.spec

        def spec(a, k):
            s = orig(a, k)
            s["feed_x"] += 1.5
            s["origin"] = (s["origin"][0] + 1.5, s["origin"][1])
            return s
        kit.spec = spec
        return lambda: setattr(kit, "spec", orig)
    if name == "narrow":
        orig = kit.SIDE_MARGIN
        kit.SIDE_MARGIN = 1.0
        return lambda: setattr(kit, "SIDE_MARGIN", orig)
    if name == "no_short":
        orig = kit.feed_tracks
        kit.feed_tracks = lambda s: [t for t in orig(s)
                                     if not (t[3] == "GND" and t[0][0] != t[1][0]
                                             or t[3] == "GND" and t[0][1] != t[1][1])]
        return lambda: setattr(kit, "feed_tracks", orig)
    if name == "z2_shunt":
        orig = kit.parts

        def parts(s):
            out = orig(s)
            for p in out:
                if p["ref"] == "Z2":
                    p["nets"] = {"1": "RF_IN", "2": "GND"}
            return out
        kit.parts = parts
        return lambda: setattr(kit, "parts", orig)
    if name == "odd_plane":
        orig = kit.spec

        def spec(a, k):
            s = orig(a, k)
            if s["key"] == "dn023_common":
                s["plane_w"] = 40.0
                px0, py0, px1, py1 = s["plane"]
                s["plane"] = (px0 + 2.5, py0, px1 - 2.5, py1)
            return s
        kit.spec = spec
        return lambda: setattr(kit, "spec", orig)
    if name == "pin_off":
        orig = kit.spec

        def spec(a, k):
            s = orig(a, k)
            s["ae1_sch"] = (s["ae1_sch"][0] + 1.27, s["ae1_sch"][1])
            return s
        kit.spec = spec
        return lambda: setattr(kit, "spec", orig)
    if name == "over_plane":
        orig = kit.spec

        def spec(a, k):
            s = orig(a, k)
            s["origin"] = (s["origin"][0], s["origin"][1] + 2.0)
            return s
        kit.spec = spec
        return lambda: setattr(kit, "spec", orig)
    if name == "one_layer":
        orig = kit.gp.gnd_zone
        kit.gp.gnd_zone = lambda layer, pts: (orig(layer, pts) if layer == "F.Cu"
                                              else orig("F.Cu", pts))
        return lambda: setattr(kit.gp, "gnd_zone", orig)
    raise SystemExit(f"no mutation called {name}")


def main() -> int:
    regenerate()
    base = run_check()
    if base:
        print("the kit does not pass before mutating:")
        for line in base:
            print(" ", line)
        return 1

    caught = 0
    for label, _unused, name in MUTATIONS:
        undo = apply(name)
        try:
            regenerate()
            fails = run_check()
        except BaseException as exc:                       # noqa: BLE001
            fails = [f"FAIL generator raised {type(exc).__name__}: {exc}"]
        finally:
            undo()
        if fails:
            caught += 1
            print(f"caught   {label}\n           -> {fails[0][5:]}")
        else:
            print(f"MISSED   {label}")
    regenerate()
    after = run_check()
    if after:
        print("the kit did not come back clean after mutating")
        return 1
    print(f"\n{caught}/{len(MUTATIONS)} mutations caught")
    return 0 if caught == len(MUTATIONS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
