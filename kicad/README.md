# 2.45 GHz PCB antenna (TI SWRA117D) — KiCad symbol, schematic, board and RF simulation

A complete, self-contained KiCad project built around the TI SWRA117D
**2.4 GHz printed inverted-F antenna** (left-hand layout): the radiator fed
straight from a 50 Ω SMA port, with no matching network in the path. Plus two
simulation flows — a lumped **ngspice** return-loss testbench and a full-wave
**openEMS** model that reads its geometry out of the board file.

```
kicad/
├── swra117d_2g4_antenna.kicad_pro   project (net classes, design rules)
├── swra117d_2g4_antenna.kicad_sch   schematic: SMA → 50 Ω line → antenna
├── swra117d_2g4_antenna.kicad_pcb   2 layer, 40 × 30 mm, 0.8 mm FR4
├── sym-lib-table / fp-lib-table     point KiCad at the project libraries
├── library/
│   ├── SWRA117D_RF.kicad_sym        antenna, SMA, GND, PWR_FLAG (+ C, L spare)
│   └── SWRA117D_RF.pretty/
│       ├── Texas_SWRA117D_2.4GHz_Left.kicad_mod   antenna (converted)
│       ├── SMA_EdgeMount_Generic.kicad_mod        50 Ω test port
│       └── Chip_0402_1005Metric_RF.kicad_mod      spare 0402 land
├── sim/
│   ├── antenna_swra117d.lib         lumped antenna model (ngspice subckt)
│   ├── s11_antenna.cir              S11 / VSWR / Zin at the connector
│   └── openems/swra117d_openems.py  full-wave S11, impedance, directivity
└── tools/                           generators, static checker, line calculator
```

Open `swra117d_2g4_antenna.kicad_pro` in KiCad, then press **B** in the PCB
editor to fill the ground zones (they are stored unfilled).

## KiCad version

Every file is written in the KiCad 9.x s-expression format
(`kicad_sym` 20241209, `kicad_sch` 20250114, `kicad_pcb` 20241229). KiCad 10
reads those directly and rewrites them in its own format the first time you
save — that is the normal upgrade path and nothing is lost.

## The signal path

```
J1  SMA edge launch  ──  1.5 mm wide 50 Ω microstrip, 32.1 mm  ──  AE1 pin 1 (FEED)
    shell ── GND                                                  AE1 pin 2 (GND) ── GND
```

One net, `ANT_FEED`, on the `RF_50R` net class (1.5 mm, 0.3 mm clearance).
Nothing sits between the connector and the radiator: the SWRA117D antenna is a
50 Ω design, so the board does not try to correct it. See
[No matching network](#no-matching-network) for what to do if the assembled
product lands off band.

`#FLG01` (a `PWR_FLAG`) sits on the ground net — this board is entirely
passive, so without it ERC reports the ground pins as power inputs that
nothing drives.

## The symbols

`library/SWRA117D_RF.kicad_sym` is the project's only symbol library. The
schematic places four of its symbols — the antenna, `Conn_Coaxial_SMA`, `GND`
and `PWR_FLAG` — and `C` and `L` are kept spare for a matching network.

They live in-project on purpose: a schematic embeds a copy of every symbol it
places, and KiCad raises `lib_symbol_mismatch` whenever that copy differs from
the library it names — which it will for any stock symbol whose definition
moves between library releases. Resolving them here makes the project
self-contained and ERC-clean on any install. If you would rather use the stock
symbols, swap the `lib_id`s and run *Tools → Update Symbols from Library* —
but check `Conn_Coaxial_SMA` afterwards, because stock
`Connector:Conn_Coaxial` puts pin 1 on the other side and the wire will need
redrawing.

The antenna symbol is `ANT_SWRA117D_2G4_Left`:

| pin | name | type | goes to |
|-----|------|------|---------|
| 1 | FEED | passive | 50 Ω feed line |
| 2 | GND  | passive | ground plane edge, right at the feed |

It is drawn over a ground bar, carries the TI application-note URL as its
datasheet, is pre-linked to the antenna footprint, filters the footprint
chooser to `Texas_SWRA117D*`, and carries the `Sim.*` fields that point
KiCad's built-in ngspice at `sim/antenna_swra117d.lib`.

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
| feed length | 32.1 mm, board edge to feed pad | λg ≈ 67 mm at 2.45 GHz, so this is ≈ 172° of line |
| ground plane | y ≥ 65.75 mm only | its edge is the antenna's ground reference |
| antenna keep-out | rule area above that edge, F.Cu **and** B.Cu | no pour, no tracks, no vias under or beside the antenna |
| top pour keep-away | 1.0 mm either side of the feed | keeps the line a microstrip instead of a narrow-gap coplanar waveguide |
| stitching | 15 vias | connector shell, and a row along the plane edge |

The 1.5 mm line necks down to 0.5 mm over the last millimetre to meet the
antenna's 0.5 mm feed pad, and turns the one corner at 45°. Both are much
shorter than λg/20, so neither is worth modelling as a discontinuity — but
they are in the openEMS geometry anyway, because it reads the real tracks.

The antenna polygon overlaps the plane edge by 0.25 mm at 28 of its vertices —
that is the part of both legs that lands on the pads, so the pads' own
clearance covers it. Nothing else crosses the line.

### No matching network

The SWRA117D antenna *is* a 50 Ω design, so the board is built without one:
connector → 50 Ω line → radiator. That is also the only honest way to
*measure* the antenna — a 0 Ω 0402 jumper would still add a few tenths of a nH
plus two pad discontinuities, and any fitted reactance would be correcting a
model rather than the hardware.

It is worth knowing when that changes. "50 Ω" holds for the antenna in the
conditions the application note assumes, and a real product is never quite
those conditions:

* **Stackup.** The published dimensions belong to a particular board thickness
  and copper/dielectric stack. This one is 0.8 mm FR4, and the arm's
  capacitance to the plane edge — hence the resonance — depends on that.
* **Ground plane.** An IFA radiates against the plane it is fed from; the
  plane is part of the antenna. A 40 × 30 mm plane is not the note's plane.
* **FR4 tolerance.** εr is typically quoted 4.2–4.8 between vendors and
  batches, and etch tolerance moves the arm width. Both shift resonance.
* **The product.** Plastic housing, battery, display, screws, a hand — these
  detune a printed antenna by tens of MHz, routinely more. This is the
  dominant term and it cannot be designed out in advance; it is measured.

So measure first, on the assembled and enclosed product, and only then decide.
If it needs help, a pi network goes in the feed line: `C` and `L` are already
in the symbol library and `Chip_0402_1005Metric_RF` in the footprint library,
and `sim/s11_antenna.cir` has the topology in a comment block so you can work
out what the parts would buy before committing pads to a layout.

### Antenna rules this board follows (keep them if you re-use it)

* No copper of any kind — pour, track, via, component — above the plane edge.
* The antenna sits on the board edge; keep it there, and keep 10 mm or more of
  clear space in front of it in the enclosure.
* The ground pin (pad 2) touches the plane; the feed pin does not.
* Keep batteries, metal shields and displays away from the keep-out region.
* Tune against the *assembled, enclosed* product, not the bare board.

## RF simulation

### 1. Return loss at the connector (ngspice)

`sim/antenna_swra117d.lib` is a behavioural model of the antenna: a series
R-L-C (50 Ω, 26 nH, 0.1618 pF → 2.454 GHz, Q ≈ 8) with 0.35 pF of feed
capacitance. `sim/s11_antenna.cir` puts the routed feed line in front of it as
a lossless 50 Ω `T` element (32.1 mm, TD = 195 ps) and computes
Γ = 2·v(in) − 1 from a 1 V source behind 50 Ω.

```sh
cd kicad/sim && ngspice -b s11_antenna.cir       # writes s11_results.csv
```

| | Z at the antenna | Z at the SMA | S11 | VSWR |
|---|---|---|---|---|
| 2.400 GHz | 39.5 − 25.8j Ω | 49.5 − 31.2j Ω | −10.5 dB | 1.85 |
| 2.442 GHz | 44.9 − 15.6j Ω | 49.4 − 17.2j Ω | −15.4 dB | 1.41 |
| 2.4835 GHz | 51.4 − 4.7j Ω | 52.3 − 4.3j Ω | −26.4 dB | 1.10 |

Best match −28.8 dB at 2.493 GHz; below −10 dB from 2.394 to 2.595 GHz, so
the antenna covers 2.400–2.4835 GHz unaided. The two impedance columns show
what the line does: 172° of matched line rotates Zin right round the Smith
chart but cannot change |S11| — which is exactly why a lumped antenna model is
still the right tool for return loss at the connector.

**The antenna model is a plausible fit, not a field solution.** It reproduces
the shape of an IFA response on a board this size; the real resonance depends
on your stackup, enclosure and ground plane. Refit it to openEMS or VNA data
before trusting it to better than a few dB.

### 2. Full wave (openEMS)

`sim/openems/swra117d_openems.py` builds the FDTD model from the board file —
outline, stackup, ground plane edge, the antenna polygon, the routed feed
segments and the pour keep-away corridors all come out of
`swra117d_2g4_antenna.kicad_pcb`, so the model cannot drift away from the
layout. The KiCad keyhole slits (the clearance ring around the ground pin) are
collapsed, since they are far below the mesh size.

```sh
python3 sim/openems/swra117d_openems.py --dry-run   # geometry only, no solver
python3 sim/openems/swra117d_openems.py --plot      # FDTD run + plots
```

`--dry-run` needs nothing but Python and reports what it read:

```
board          : 40.0 x 30.0 mm, 0.8 mm FR4 (er 4.4, tan d 0.02)
ground plane   : y = 0 .. 24.25 mm (antenna region 24.25 .. 30.0 mm is clear)
feed line      : 4 segments, 32.1 mm total, port at x = 0, feed pad at (24.00, 24.00) mm
                 (  0.00, 15.00) -> ( 22.50, 15.00)  w = 1.5 mm
                 ( 22.50, 15.00) -> ( 24.00, 16.50)  w = 1.5 mm
                 ( 24.00, 16.50) -> ( 24.00, 23.00)  w = 1.5 mm
                 ( 24.00, 23.00) -> ( 24.00, 24.00)  w = 0.5 mm
top pour       : 6 boxes around 2 keep-away corridors
antenna copper : 29 vertices, x 12.15..26.55 mm, y 23.75..29.15 mm
```

A real run needs openEMS with its Python bindings
(<https://docs.openems.de/python/install.html>) and prints S11, the −10 dB
band, the input impedance at the band edges and the peak directivity, and
writes `s11_openems.csv`. Copper is a zero-thickness sheet, the connector body
is not modelled (the port launches at the board edge in its place), and the
SMA ground pads are left to the surrounding pour.

### 3. In-KiCad RFsim plugin — port setup

RFsim reads the board directly, so two things need saying before it will model
the launch correctly.

**Fill the zones first.** The copper pours are stored unfilled (KiCad computes
fills on **B**), so a fresh checkout has no B.Cu copper anywhere and RFsim
reports *"no copper on reference layer B.Cu"* for Port 1. That is the missing
fill, not a missing plane: the B.Cu ground pour outline covers the whole feed
line, which `tools/check_project.py` verifies.

**Set Port 1 to "Coplanar (CPW)".** RFsim also reports coplanar copper 0.8 mm
from the feed line, and it is right — that is the end-launch footprint doing
its job. `SMA_EdgeMount_Generic` puts a 1.5 mm signal pad between two ground
pads 0.8 mm either side, with the plane underneath: a grounded coplanar
waveguide, not a microstrip. A Lumped or Microstrip port looks for its return
directly beneath the signal only, so it mis-models the launch.

The two geometries are deliberately the same impedance, which
`tools/line_impedance.py` computes from the stackup in the board file:

| | | |
|---|---|---|
| feed line, microstrip, 1.5 mm | **49.7 Ω** | εr,eff 3.33, λg 67.0 mm |
| SMA launch, CPWG, 1.5 mm / 0.8 mm gap | **48.8 Ω** | εr,eff 3.19, λg 68.5 mm |
| 50 Ω microstrip width for this stackup | 1.49 mm | Hammerstad + Wheeler thickness |

So the launch is not a discontinuity — the CPW section is only as long as the
connector pads (3.5 mm), and the coplanar ground stops there: the pour is held
1.0 mm off the line by the `RF_POUR_KEEPAWAY_*` rule areas, so everything past
the connector is a true microstrip over the bottom plane.

For other solvers, export from KiCad as usual: Gerbers or DXF for 2.5D tools
(Sonnet, ADS Momentum), STEP for 3D (HFSS, CST).

## Regenerating and checking the files

```sh
python3 tools/gen_project.py      # rebuild .kicad_sch / .kicad_pcb / .kicad_pro
python3 tools/check_project.py    # static netlist + clearance + keep-out checks
python3 tools/line_impedance.py   # microstrip and CPWG impedance for the stackup
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
* nothing but the antenna lives above the ground plane edge,
* every end of the feed line sits over the B.Cu ground pour, so the microstrip
  has a return path — and it says so when the zones are still unfilled.

```
ok   library: 6 symbols, 3 footprints parse cleanly
ok   schematic: 4 embedded symbols all match library/SWRA117D_RF.kicad_sym (no lib_symbol_mismatch)
ok   schematic: 7 pins placed, 5 wires, netlist matches the intended one
ok   board: 7 pads, 4 tracks, 15 vias, clearances >= 0.15 mm, keep-out clean
ok   board: 28 antenna polygon vertices overlap the plane edge, all of them inside the antenna's own pads
ok   board: all 8 feed line ends sit over the B.Cu ground pour (reference plane present)
ok   board: 2 copper zones carry no fill yet - press B in the PCB editor before running DRC or an RF simulation, or tools that look for the reference layer will find it empty
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
conflicting drivers, no net collisions — the netlist was as designed. The
matching network was removed after that run, so the sheet is now J1, AE1, two
ground symbols and the flag; `PWR_FLAG` itself has not been through ERC yet.
DRC on the board has not been run at all.

## Reference

TI application note SWRA117D, *2.4 GHz Inverted F Antenna*:
<https://www.ti.com/lit/an/swra117d/swra117d.pdf>
