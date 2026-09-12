# 2.45 GHz PCB antenna (TI SWRA117D) — KiCad symbol, schematic, board and RF simulation

A complete, self-contained KiCad project built around the TI SWRA117D
**2.4 GHz printed inverted-F antenna** (left-hand layout), plus two simulation
flows for the RF side: a lumped **ngspice** match/return-loss testbench and a
full-wave **openEMS** model that reads its geometry straight out of the board
file.

```
kicad/
├── swra117d_2g4_antenna.kicad_pro   project (net classes, design rules)
├── swra117d_2g4_antenna.kicad_sch   schematic: SMA → pi match → antenna
├── swra117d_2g4_antenna.kicad_pcb   2 layer, 40 × 30 mm, 0.8 mm FR4
├── sym-lib-table / fp-lib-table     point KiCad at the project libraries
├── library/
│   ├── SWRA117D_RF.kicad_sym        ← the antenna symbol (+ C, L, SMA, GND, PWR_FLAG)
│   └── SWRA117D_RF.pretty/
│       ├── Texas_SWRA117D_2.4GHz_Left.kicad_mod   antenna (converted)
│       ├── SMA_EdgeMount_Generic.kicad_mod        50 Ω test port
│       └── Chip_0402_1005Metric_RF.kicad_mod      matching network land
├── sim/
│   ├── antenna_swra117d.lib         lumped antenna model (ngspice subckt)
│   ├── s11_pi_match.cir             S11 / VSWR / Zin testbench
│   └── openems/swra117d_openems.py  full-wave S11, impedance, directivity
└── tools/                           the generators and the static checker
```

Open `swra117d_2g4_antenna.kicad_pro` in KiCad, then press **B** in the PCB
editor to fill the ground zones (they are stored unfilled).

## KiCad version

Every file is written in the KiCad 9.x s-expression format
(`kicad_sym` 20241209, `kicad_sch` 20250114, `kicad_pcb` 20241229). KiCad 10
reads those directly and rewrites them in its own format the first time you
save — that is the normal upgrade path and nothing is lost. If you need the
files to *stay* in KiCad 10's format, open and save once, then commit.

## The symbols

`library/SWRA117D_RF.kicad_sym` is the project's only symbol library, and it
holds everything the schematic uses: the antenna, plus `C`, `L`,
`Conn_Coaxial_SMA`, `GND` and `PWR_FLAG`. Those five are stand-ins for stock
KiCad symbols, kept in-project on purpose — a schematic embeds a copy of every
symbol it places, and KiCad raises `lib_symbol_mismatch` whenever that copy
differs from the library it names, which it will for any stock symbol whose
definition moves between library releases. Resolving them here makes the
project self-contained and ERC-clean on any install. If you would rather use
the stock symbols, swap the `lib_id`s and run *Tools → Update Symbols from
Library* — but check `Conn_Coaxial_SMA` after doing it, because stock
`Connector:Conn_Coaxial` puts pin 1 on the other side and the wire will need
redrawing.

The antenna symbol itself is `ANT_SWRA117D_2G4_Left`:

| pin | name | type | goes to |
|-----|------|------|---------|
| 1 | FEED | passive | 50 Ω feed line |
| 2 | GND  | passive | ground plane edge, right at the feed |

The antenna is drawn over a ground bar, carries the TI
application-note URL as its datasheet, is pre-linked to the antenna footprint
and filters the footprint chooser to `Texas_SWRA117D*`. It also carries the
`Sim.*` fields that point KiCad's built-in ngspice at
`sim/antenna_swra117d.lib`, so the symbol can be simulated in place.

Pin 2 matters: this is an *inverted-F*, not a monopole. The footprint's second
pad is the ground/short pin and it has to sit on the edge of the ground plane,
which is what the board below does.

## The footprints

`Texas_SWRA117D_2.4GHz_Left.kicad_mod` is the supplied legacy (KiCad 4/5)
footprint converted to the modern format by `tools/convert_legacy_footprint.py`
— `module` → `footprint`, `fp_text reference/value` → `property`, bare `width`
→ `stroke`, `attr virtual` → `exclude_from_pos_files exclude_from_bom`, the v5
`connect` pad → `smd`, and a UUID on every item. The 53-vertex antenna
polygon, the pads and the `Dwgs.User` keep-out box are carried over unchanged.

The SMA and 0402 footprints are generic parts written for this board, not
copies of the stock KiCad library; check them against your own connector and
assembly rules before ordering.

## The board

2 layers, 40 × 30 mm, **0.8 mm FR4** (εr 4.4, tan δ 0.02), 35 µm copper —
the stackup is in the board file, so the 3D viewer and any EM export see it.

| item | value | why |
|------|-------|-----|
| 50 Ω microstrip | **w = 1.5 mm** | Hammerstad gives 50.8 Ω for w/h = 1.875, εr,eff = 3.33 (≈ 50 Ω once 35 µm copper is included) |
| guided wavelength | λg ≈ 67 mm at 2.45 GHz | keeps the whole feed well under λg/4 |
| ground plane | y ≥ 65.75 mm only | its edge is the antenna's ground reference |
| antenna keep-out | rule area above that edge, F.Cu **and** B.Cu | no pour, no tracks, no vias under or beside the antenna |
| top pour keep-away | 1.0 mm either side of the feed | keeps the line a microstrip instead of a narrow-gap coplanar waveguide |
| matching network | C1 / L1 / C2, 0402 | **not populated**: L1 is a 0 Ω jumper, C1 and C2 are DNP |
| stitching | 17 vias | connector ground, both shunt caps, and a row along the plane edge |

Signal path: `J1 → C1 shunt → L1 series → C2 shunt → AE1`, nets `RF_IN` and
`ANT_FEED` on the `RF_50R` net class (1.5 mm, 0.3 mm clearance).

The antenna polygon overlaps the plane edge by 0.25 mm at 28 of its vertices —
that is the part of both legs that lands on the pads, so the pads' own
clearance covers it. Nothing else crosses the line.

### Why a matching network on a 50 Ω antenna?

The SWRA117D antenna *is* a 50 Ω design, and this board ships with nothing
matched out: **L1 is a 0 Ω jumper and C1/C2 are unpopulated**, so the RF path
is just connector → 50 Ω line → antenna. The pi network is three empty
footprints, not a correction applied to the antenna.

They are there because "50 Ω" holds for the antenna *in the conditions the
application note assumes*, and a real board is never quite those conditions:

* **Stackup.** The published dimensions belong to a particular board thickness
  and copper/dielectric stack. This one is 0.8 mm FR4, and the arm's
  capacitance to the plane edge — hence the resonance — depends on that.
* **Ground plane.** An IFA radiates against the plane it is fed from; it is
  part of the antenna. A 40 × 30 mm plane is not the note's plane.
* **FR4 tolerance.** εr is typically quoted 4.2–4.8 between vendors and
  batches, and etch tolerance moves the arm width. Both shift resonance.
* **The product.** Plastic housing, battery, display, screws, a hand — these
  detune a printed antenna by tens of MHz, routinely more. This is the big one,
  and it cannot be designed out in advance; it is measured.

So the pads are cheap insurance: three 0402 sites cost nothing on the BOM when
unpopulated, and they turn a re-spin into a component swap if the assembled
product lands off band. Leaving them out of the layout is the expensive
decision, not putting them in.

The lumped model in `sim/` shows the scale of it. Unmatched, it is already
under −10 dB across the whole ISM band — which is the point: the antenna does
not *need* matching. Fitting the 0.8 nH the model asks for buys about 8 dB at
band centre and shifts resonance 30 MHz down — worth having only once you know
which way the real hardware moved.

If you want the cleanest possible reference measurement of the bare antenna,
say so and I will route a solid 50 Ω line straight from J1 to the feed pad; a
0 Ω 0402 still adds a few tenths of a nH and two pad discontinuities.

### Antenna rules this board follows (keep them if you re-use it)

* No copper of any kind — pour, track, via, component — above the plane edge.
* The antenna sits on the board edge; keep it there, and keep 10 mm or more of
  clear space in front of it in the enclosure.
* The ground pin (pad 2) touches the plane; the feed pin does not.
* Keep batteries, metal shields and displays away from the keep-out region.
* Tune the match against the *assembled, enclosed* product — plastic, battery
  and hand loading all pull the resonance down.

## RF simulation

### 1. Lumped match / return loss (ngspice)

`sim/antenna_swra117d.lib` is a behavioural model of the antenna: a series
R-L-C (50 Ω, 26 nH, 0.1618 pF → 2.454 GHz, Q ≈ 8) with 0.35 pF of feed
capacitance. `sim/s11_pi_match.cir` puts the pi network in front of it and
computes Γ = 2·v(in) − 1 directly from a 1 V source behind 50 Ω.

```sh
cd kicad/sim && ngspice -b s11_pi_match.cir       # writes s11_results.csv
```

As built — L1 a 0 Ω jumper, C1/C2 unpopulated — and with 0.8 nH fitted in L1
for comparison:

| | as built (0 Ω) | L1 = 0.8 nH |
|---|---|---|
| best match | −29 dB at 2.493 GHz | −31 dB at 2.461 GHz |
| 2.400 GHz | 39.4 − 25.8j Ω, −10.5 dB, VSWR 1.86 | 39.4 − 13.8j Ω, −14.4 dB, VSWR 1.47 |
| 2.442 GHz | 44.8 − 15.6j Ω, −15.3 dB, VSWR 1.41 | 44.9 − 3.4j Ω, −23.8 dB, VSWR 1.14 |
| 2.4835 GHz | 51.4 − 4.7j Ω, −26.3 dB, VSWR 1.10 | 51.4 + 7.7j Ω, −22.2 dB, VSWR 1.17 |
| −10 dB band | 2.394 – 2.595 GHz | 2.358 – 2.568 GHz |

The unmatched column is the one that matters: the antenna clears −10 dB across
2.400–2.4835 GHz on its own. Change the population by editing the `.param`
line (an unpopulated part is modelled as 1 fF, a jumper as 1 pH). **The antenna model is a plausible fit, not a field solution** — it
reproduces the shape of an IFA response on a board this size, but the real
resonance depends on your stackup, enclosure and ground plane. Refit it to
openEMS or VNA data before trusting it to better than a few dB.

The same model is reachable from the schematic: AE1 carries `Sim.Device`,
`Sim.Name`, `Sim.Library` and `Sim.Pins`, so KiCad's built-in simulator can
use it once you add a source to the sheet.

### 2. Full wave (openEMS)

`sim/openems/swra117d_openems.py` builds the FDTD model from the board file —
outline, stackup, ground plane edge, the antenna polygon and the feed point
all come out of `swra117d_2g4_antenna.kicad_pcb`, so the model cannot drift
away from the layout. The KiCad keyhole slits (the clearance ring around the
ground pin) are collapsed, since they are far below the mesh size.

```sh
python3 sim/openems/swra117d_openems.py --dry-run   # geometry only, no solver
python3 sim/openems/swra117d_openems.py --plot      # FDTD run + plots
```

`--dry-run` needs nothing but Python and reports what it read:

```
board          : 40.0 x 30.0 mm, 0.8 mm FR4 (er 4.4, tan d 0.02)
ground plane   : y = 0 .. 24.25 mm (antenna region 24.25 .. 30.0 mm is clear)
feed           : x = 24.00 mm, y = 24.00 mm, line width 1.5 mm
antenna copper : 29 vertices, x 12.15..26.55 mm, y 23.75..29.15 mm
```

A real run needs openEMS with its Python bindings
(<https://docs.openems.de/python/install.html>) and prints S11, the −10 dB
band, the input impedance at the band edges and the peak directivity, and
writes `s11_openems.csv`.

Two deliberate simplifications: the feed is a straight 50 Ω line from the
board edge to the feed pad (the routed board detours through the matching
network, which does not change the antenna), and the matching network is not
in the model. Simulate the bare antenna, then design the match from the
impedance you get — `s11_pi_match.cir` is where that match gets checked.

For other solvers, export from KiCad as usual: Gerbers or DXF for 2.5D tools
(Sonnet, ADS Momentum), STEP for 3D (HFSS, CST).

## Regenerating and checking the files

```sh
python3 tools/gen_project.py      # rebuild .kicad_sch / .kicad_pcb / .kicad_pro
python3 tools/check_project.py    # static netlist + clearance + keep-out checks
```

`gen_project.py` embeds the symbol and the footprints into the schematic and
the board, so all three files agree on pins, pads and nets by construction.
It is a one-shot generator: **once you edit anything in KiCad, KiCad owns the
files** — re-running it would overwrite your work.

`check_project.py` is the safety net used while writing these files. It
extracts the schematic netlist from the wire geometry, rebuilds the board pad
positions (rotations included) and verifies that

* every embedded symbol resolves to this project's library and is identical to
  it, so KiCad has nothing to report as `lib_symbol_mismatch`,
* every symbol pin lands on a wire and every net matches the intended one,
* every board pad carries the net the schematic gives it,
* every track ends on a pad, a via or another track,
* copper of different nets keeps ≥ 0.15 mm apart,
* nothing but the antenna lives above the ground plane edge.

```
ok   library: 6 symbols, 3 footprints parse cleanly
ok   schematic: 6 embedded symbols all match library/SWRA117D_RF.kicad_sym (no lib_symbol_mismatch)
ok   schematic: 15 pins placed, 12 wires, netlist matches the intended one
ok   board: 13 pads, 11 tracks, 17 vias, clearances >= 0.15 mm, keep-out clean
ok   board: 28 antenna polygon vertices overlap the plane edge, all of them inside the antenna's own pads
0 problem(s)
```

That is a structural check, not a substitute for KiCad, so **run ERC and DRC,
and fill the zones, after opening the project.**

### ERC history

The first version of this project was written without a KiCad installation to
test against. A KiCad 9 ERC run on it reported 1 error and 8 warnings, all of
them from the schematic's symbol sources rather than its wiring:

| report | cause | fix |
|--------|-------|-----|
| `power_pin_not_driven` on `#PWR01` | passive board, no power output anywhere | `#FLG01` `PWR_FLAG` added on the ground net |
| `lib_symbol_mismatch` × 8 (`C`, `L`, `Conn_Coaxial`, `GND`) | embedded stand-ins for stock symbols did not match the installed libraries | those symbols moved into `library/SWRA117D_RF.kicad_sym`, which the schematic embeds from, and `check_project.py` now enforces it |

Nothing in that report touched connectivity: no unconnected pins, no
conflicting drivers, no net collisions — the netlist was as designed. DRC on
the board has not been run yet.

## Reference

TI application note SWRA117D, *2.4 GHz Inverted F Antenna*:
<https://www.ti.com/lit/an/swra117d/swra117d.pdf>
