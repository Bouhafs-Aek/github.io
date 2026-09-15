# TI reference PCB antennas in KiCad — symbols, boards, checks and RF simulation

Two TI reference antennas, each as a complete self-contained KiCad project,
each an exact copy of its application note's dimension table and each with a
checker that fails the build if it stops being one:

* **TI SWRA117D**, a **2.45 GHz printed inverted-F** (left-hand layout) — the
  radiator fed straight from a 50 Ω SMA port, with no matching network,
  because the note says it is already a 50 Ω design.
* **TI DN024 / SWRA227E**, a **868 + 2440 MHz meandering monopole** — copper
  on both layers and a pi matching network at the feed, because this note says
  it needs one and gives the values.

Plus a third project for RFsim, the inverted-F drawn the way its Figure 3
draws it — ground on layer 2 only, one via, no connector — and two simulation
flows: a lumped **ngspice** return-loss testbench and a
full-wave **openEMS** model that reads its geometry out of whichever board
file you point it at.

```
kicad/
├── swra117d_2g4_antenna.kicad_pro   project (net classes, design rules)
├── swra117d_2g4_antenna.kicad_sch   schematic: SMA → 50 Ω line → antenna
├── swra117d_2g4_antenna.kicad_pcb   2 layer, 40 × 30 mm, 1.6 mm FR4
├── sym-lib-table / fp-lib-table     point KiCad at the project libraries
├── library/
│   ├── SWRA117D_RF.kicad_sym        antenna, SMA, RF_PORT, GND, PWR_FLAG (+ C, L)
│   ├── TI_DN024.kicad_sym           the second antenna's symbols
│   ├── TI_DN024.pretty/             the DN024 monopole footprint
│   └── SWRA117D_RF.pretty/
│       ├── Texas_SWRA117D_2.4GHz_Left.kicad_mod  antenna, as published
│       ├── SWRA117D_2G4_Left_retuned.kicad_mod   antenna, scaled x1.155
│       ├── SMA_EdgeMount_Generic.kicad_mod       50 Ω connector land
│       ├── RF_Port_Land.kicad_mod                the same land, no connector
│       └── Chip_0402_1005Metric_RF.kicad_mod     spare 0402 land
├── dn024/                           second antenna: TI DN024 monopole
│   └── dn024_monopole_868_2440.*    868 + 2440 MHz, sch + pcb + pro
├── docs/
│   ├── board-drawing.svg            dimensioned drawing, generated from the PCB
│   ├── dn024-board-drawing.svg      the same, for the DN024 board
│   ├── sim-board-drawing.svg        the same, for the simulation board
│   └── antenna-integration-checklist.md   design review list for any project
├── sim/
│   ├── antenna_swra117d.lib         lumped antenna model (ngspice subckt)
│   ├── s11_antenna.cir              S11 / VSWR / Zin at the connector
│   ├── board/swra117d_2g4_sim.*     RFsim project: Figure 3, ground on layer 2
│   └── openems/swra117d_openems.py  full-wave S11, impedance, directivity
└── tools/                           generators, checkers, line + scaling calculators
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
J1  SMA edge launch  ──  2.95 mm wide 50 Ω microstrip, 23.5 mm  ──  AE1 pin 1 (FEED)
    shell ── GND         one straight run, no corner              AE1 pin 2 (GND) ── GND
```

The connector sits on the bottom edge directly below the antenna's feed pad
and faces it, so the feed is a single vertical run. That is as short as an
edge-launch connector can be here: the antenna owns the top edge, its ground
pin blocks any approach from the right, and the SMA needs 12.95 mm of board edge
with all of it on the ground plane — which only the bottom edge offers.

One net, `ANT_FEED`, on the `RF_50R` net class (2.95 mm, 0.3 mm clearance).
Nothing sits between the connector and the radiator: the SWRA117D antenna is a
50 Ω design, so the board does not try to correct it. See
[No matching network](#no-matching-network) for what to do if the assembled
product lands off band.

`#FLG01` (a `PWR_FLAG`) sits on the ground net — this board is entirely
passive, so without it ERC reports the ground pins as power inputs that
nothing drives.

## The antenna is a DC short

Worth knowing before any simulator or multimeter surprises you: **pad 1 and
pad 2 are connected by the radiator**. The arm is one continuous piece of
copper that lands on the feed pad at one end and on the ground pad at the
other — that is the shorting strap, the "F" in inverted-F. The port sees
0 Ω to ground at DC.

The footprint does not make this obvious, which is why `check_project.py`
asserts it. The polygon looks like it has an isolation ring around pad 2, but
that 22-vertex ring is 0.147–0.152 mm in radius: it is the 0.15 mm **drill
barrel** punched out of the copper, not a gap. Probe anywhere else on pad 2's
land and you are on the radiator:

```
pad 1 centre                       inside radiator copper = True
pad 2 centre (in the drill hole)   inside radiator copper = False
pad 2 copper, +0.2 mm in y         inside radiator copper = True
pad 2 copper, ±0.3 mm in x         inside radiator copper = True
```

**This is why a circuit-level RF extraction of this board reports VSWR → ∞.**
A tool that turns the layout into transmission lines and lumped connectivity
has no radiation mechanism, so the only thing it can see at the port is a
shorted stub: |Γ| = 1. Radiation resistance — the ~50 Ω that makes the
antenna work — exists only in a solver that lets power leave the board. So a
huge VSWR from a quasi-static or TL extractor is that model being used outside
its domain, not a fault in the feed line. Use openEMS (or any full-wave
solver) for the antenna, and the lumped model in `sim/` for the match.

If you want to check the *feed line* separately from the antenna, that is
worth doing and it is easy: terminate the line into 50 Ω instead of the
radiator — delete AE1 temporarily, or in RFsim put port 2 at the antenna feed
pad and look at S21 and the port impedances.

## The symbols

`library/SWRA117D_RF.kicad_sym` is the project's only symbol library. The
schematic places four of its symbols — the antenna, `Conn_Coaxial_SMA`, `GND`
and `PWR_FLAG`; the RFsim project places `RF_PORT` in place of the connector;
and `C` and `L` are kept spare for a matching network.

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

## Simulating this board: four settings that decide whether the answer means anything

An RFsim run of this board reported resonance at 2.83 GHz, and the board
carried a x1.155 scaled radiator for one commit because of it. **That number
was not usable, and the scaling has been reverted.** The layout plot from the
run shows why: the only copper on the board is the antenna, the feed line and
the connector pads. The ground pours are absent, and the dialog was set to
RFsim's FR-4 preset rather than this board's stackup. Two large errors pulling
in opposite directions.

Before trusting any result from this board, check all four:

| setting | must be | why |
|---|---|---|
| **copper zones** | **filled** — press **B** in the PCB editor before exporting | An inverted-F radiates *against its ground plane*; the plane is half the antenna. With the pours unfilled there is no plane at all, only the connector's pads, and the 41 stitching vias connect to nothing. This is not a small error — it is a different antenna. |
| **substrate** | **1.6 mm, εr 4.5** | This is the fabricated stackup, and it happens to be RFsim's FR-4 preset, so this setting is usually right by accident. Check it anyway: the field-plot caption names the mid-plane, and it should read 0.80 mm. On 0.8 mm the 2.95 mm line would be **32 Ω**, not 50. |
| **domain margin** | **≥ λ/4 at the lowest frequency in the sweep** — 31 mm from 2.45 GHz, but **37.5 mm** from a sweep that starts at 2 GHz | At the 4 mm default the absorbing boundary sits inside the antenna's near field — λ/31 away — so it truncates the fields that make the antenna an antenna. The number follows the sweep, not the design frequency: starting at 2.3 GHz instead of 2.0 asks for 32.6 mm rather than 37.5 and cuts the domain volume by a third. `sim/openems/swra117d_openems.py` uses 30 mm, which suits its own 1.45–3.45 GHz excitation. |
| **port** | attached to the feed line: **Coplanar (CPW)** on the fabrication board, **Microstrip (MSL)** on the RFsim project, which has no connector pads beside the line | The dialog showed *Port 1 [No Track]*, *Feed: No Line*, Lumped, width 3.114 mm. The width was never the problem: 3.11 mm is the 50 Ω width for this stackup with copper thickness ignored, and the board's 2.95 mm is the same width with it. *No Track* and *No Line* were the problem — a lumped port that is not attached to anything excites nothing. |

The stackup leaves a usable fingerprint in RFsim's own guess:
`tools/line_impedance.py` gives 50 Ω at **3.03 mm** on 1.6 mm / εr 4.5 with
zero-thickness copper and **2.97 mm** with 35 µm of it. RFsim guessed
3.114 mm, so RFsim was reading 1.6 mm all along — which, once the board owner
confirmed 1.6 mm, turned out to be right.

### Retuning, once a valid run exists

Uniform in-plane scaling is the retune whose physics needs no model of the
meander: scale every dimension *and every gap* by k and each current path and
coupling distance scales with it, so the resonance moves as 1/k. It also
carries the feed tap and the short along with it, so the input impedance is
preserved — lengthening one arm by hand would fix the frequency and break the
50 Ω. It is first order only (the substrate thickness does not scale), so
expect to iterate.

```sh
python3 tools/scale_footprint.py \
    library/SWRA117D_RF.pretty/Texas_SWRA117D_2.4GHz_Left.kicad_mod \
    library/SWRA117D_RF.pretty/SWRA117D_2G4_Left_retuned.kicad_mod \
    --scale <f_measured / 2.45> --name SWRA117D_2G4_Left_retuned
# then set ANT_SCALE and ANT_FOOTPRINT in tools/gen_project.py
python3 tools/gen_project.py
```

### Run log

Five full-wave runs so far. The frequency a run reports is only as good as
the setup behind it, so the setup is recorded with it:

| run | board | ground plane | substrate | domain | resonance |
|---|---|---|---|---|---|
| 1 | fabrication | **absent** (pours unfilled) | 1.6 mm (preset) | **4 mm** | 2.83 GHz |
| 2 | fabrication | present | 1.6 mm (mid-plane caption read 0.80 mm) | **4 mm** | 2.02 GHz |
| 3 | fabrication | to confirm | to confirm | to confirm | 2.82 GHz, VSWR 1.2 |
| 4 | fabrication | present | 1.6 mm (mid-plane caption again read 0.80 mm) | **4 mm**, bright field on the boundary | 2.65 GHz |
| 5 | **RFsim project** (Figure 3) | present, layer 2 | 1.6 mm | to confirm | **2.575 GHz, −38.5 dB** |

Run 5 is the first with a model that is not obviously wrong: no connector, no
top pour, ground on one layer, MSL port on a pad with reference copper under
it. It is also the first that looks like an antenna rather than like a setup
artefact — one clean resonance, smooth either side, no ripple against the
boundary.

The substrate column is no longer bolded as a fault: the board owner has since
confirmed 1.6 mm, so the simulator's preset was right and this project's
0.8 mm assumption was the error. What remains wrong in every one of these runs
is the 4 mm domain, and in run 1 the missing ground plane.

Runs 1–4 span **2.02 – 2.83 GHz: 810 MHz, or 33% of the target frequency**, on
a board whose copper did not meaningfully change. No geometry moved by 33%.
That spread was the measurement, not the antenna. Runs 1 and 3 agree, and that
agreement means nothing on its own: run 1 had no ground plane at all, which is
a different antenna, and it landed on the same number as a run that had one.

#### What run 5 says

Read off the plot, so ±0.01 GHz and ±1 dB:

| | |
|---|---|
| resonance | **2.575 GHz**, 5.1% above 2.45 |
| depth | **−38.5 dB**, VSWR **1.02** |
| −10 dB band | ≈ 2.48 – 2.68 GHz, **200 MHz**, 7.8% (TI quotes bandwidth at VSWR 2.0 = −9.5 dB, marginally wider) |
| at 2.400 GHz | ≈ −5.5 dB, VSWR 3.3 |
| at 2.4835 GHz | ≈ −11 dB, VSWR 1.8 |

Two separate results, and it is worth keeping them apart.

**The match is excellent and that is a real finding.** −38.5 dB is not
something a mis-set port produces by accident: it says the feed tap sits in
the right place relative to the short, which is Table 1's D5 = 1.40 mm doing
its job. The bandwidth is 200 MHz where the ISM band needs 83 MHz, so there is
more than twice the bandwidth required — the antenna does not need widening,
only centring.

**The frequency is 5.1% high**, which as it stands leaves 2.400 GHz at VSWR
3.3: the band is not covered at the low end. Resonance high means the radiator
is electrically short, and uniform scaling by k = 2.575 / 2.45 = **1.051**
would centre it while preserving the feed-to-short ratio, so the match should
survive.

#### Before scaling anything

5.1% is small enough to be the model rather than the antenna, and that
distinction decides whether to touch copper at all:

* **εr is a guess.** FR4 is quoted 4.2–4.8 between vendors and batches. The
  antenna has no ground under it so it sits mostly in air and is less sensitive
  than the feed line is, but not insensitive — and 4.5 is a nominal value, not
  a measurement of this laminate.
* **The model has no solder mask.** The real board has ~25 µm of εr ≈ 3.5
  resin over the radiator, which loads it and pulls resonance *down* by roughly
  a percent. That is a third of this error, in the right direction, and it is
  absent from the model by construction.
* **Etch tolerance** moves a 0.5 mm strip by a few percent of its width.

So a 5% error is inside the envelope of the model's own inputs. Scaling the
copper to cancel it would be fitting the geometry to an uncertainty.

**And there is a reason not to aim at 2.45 GHz in free space at all.** AN058's
measurements of a handheld PCB antenna show plastic encapsulation pulling the
resonance *down*, and a hand holding the encapsulated device pulling it down
further still — the effect only ever goes one way. An antenna centred on the
band on the bench is an antenna sitting below the band once it is in its case.
So the free-space target is not the band centre; it is the band centre plus
whatever the enclosure takes away, which is a number you get by measuring your
enclosure. Run 5 being 5% high is, on its own, not obviously the wrong place
to be.

AN058 does confirm the *direction*, for when there is something to correct:
*"if the resonance frequency is too low, the antenna should be made shorter.
If the resonance frequency is too high, the antenna length should be
increased."* Uniform scaling by k > 1 lengthens every path at once, which is
what `tools/scale_footprint.py` does.

**The gate**, unchanged in principle and now down to two items for run 5:

1. ~~copper pours filled~~ — the ground is a filled zone in the exported
   geometry, or there would be no resonance at all.
2. ~~substrate 1.6 mm, εr 4.5~~ — confirmed by the board owner.
3. **domain margin ≥ 37.5 mm.** λ/4 at the *lowest* frequency in the sweep,
   and this sweep starts at 2 GHz, not 2.45 — so 31 mm is not enough here,
   37.5 mm is. Check the field plot extends that far past the copper and is
   dark at the boundary. Starting the sweep at 2.3 GHz instead would drop the
   requirement to 32.6 mm and shrink the domain volume by a third.
4. **Run it twice.** A converged model gives the same answer twice, and this
   one has not yet been asked to.

Confirm those two and `k = 1.051` is a two-line change:

```sh
python3 tools/scale_footprint.py     library/SWRA117D_RF.pretty/Texas_SWRA117D_2.4GHz_Left.kicad_mod     library/SWRA117D_RF.pretty/SWRA117D_2G4_Left_retuned.kicad_mod     --scale 1.051 --name SWRA117D_2G4_Left_retuned
# then ANT_SCALE = 1.051 and ANT_FOOTPRINT = "SWRA117D_2G4_Left_retuned"
```

The scaled radiator is 15.13 × 5.68 mm of copper against 14.40 × 5.40 mm, and
its keep-out box reaches y = 60.77 mm against a board edge at 60.00, so it
still fits with 0.77 mm to spare. `SWRA117D_2G4_Left_retuned.kicad_mod` is in
the library at ×1.155 from the discredited run 3 and has not been regenerated:
**the board carries the published geometry**, and it stays that way until a
confirmed run says otherwise.

The honest alternative to scaling is to build one board and put a VNA on it.
A 5% model error against an unmeasured laminate is exactly the situation the
application note's own remedy addresses — *"To compensate for a
thicker/thinner PCB the antenna could be made slightly shorter/longer"* — and
it is cheaper to trim after a measurement than to guess before one.

### Verified against the application note

SWRA117D (AN043) states the antenna as a dimension table, and states why it
matters: *"Small changes of the antenna dimensions may have large impact on
the performance. Therefore it is strongly recommended to make an exact copy of
the reference design to achieve optimum performance."*

`tools/verify_against_swra117d.py` measures the footprint's geometry out of
the polygon and compares it with Table 1. **All 14 dimensions match within
11 µm** — L1–L6, W1, W2 and D1–D6, including both repeats of the meander:

```
L1  3.94   3.940   open-end leg, under the top strip
L2  2.70   2.700   meander top strips (second instance 2.700)
L3  5.00   5.000   first top strip, ground leg to first finger
L4  2.64   2.640   meander finger depth
L5  2.00   2.000   meander bottom links (second instance 2.000)
L6  4.90   4.900   feed and ground legs
W1  0.90   0.900   ground (shorting) leg width
W2  0.50   0.500   trace width everywhere else
D1  0.50   0.500   clearance beyond the ground leg
D2  0.30   0.300   clearance above the top strip
D3  0.30   0.300   clearance beyond the open end
D4  0.50   0.500   feed/ground pad height at the plane edge
D5  1.40   1.400   gap, feed leg to ground leg
D6  1.70   1.700   gap, feed leg to first meander finger
```

`check_project.py` runs this on whichever antenna footprint the board
actually carries, so a scaled or redrawn radiator fails the build rather than
passing quietly. Putting the ×1.155 variant back reports:

```
FAIL board: SWRA117D_2G4_Left_retuned is not an exact copy of SWRA117D
     Table 1 - 14 dimension(s) differ, worst L3 by +775 um
```

Two things fall out of the table that the drawing alone does not tell you.
The keep-out box is not arbitrary: D1, D2 and D3 are the note's own
clearances, and D4 is the pad height at the plane edge — which is why the
ground plane edge is read from that box rather than typed in. And the note's
"15.2 × 5.7 mm" envelope is the copper (14.4 × 5.4 mm) plus exactly those
clearances.

### The stackup: 1.6 mm, confirmed by the board owner

SWRA117D does not give the stackup. It says *"It is also recommended to use
the same thickness and type of PCB material as used in the reference design.
Information about the PCB can be found in a separate readme file included in
the reference design"* — a readme we do not have. What it does give is the
remedy: *"To compensate for a thicker/thinner PCB the antenna could be made
slightly shorter/longer."*

**The board is 1.6 mm FR4.** That is the fabricated reality, so the design
follows it, and the simulator was right all along — it was this project's
0.8 mm assumption that was wrong. Everything downstream is derived, so the
change was one constant:

| | 0.8 mm (was) | 1.6 mm (is) |
|---|---|---|
| 50 Ω microstrip | 1.50 mm | **2.95 mm** (50.2 Ω) |
| SMA signal pad | 1.5 mm | **2.95 mm**, footprint generated to match |
| coplanar gap at the launch | 0.8 mm → 48.8 Ω | **2.0 mm → 49.8 Ω** |
| top pour keep-away | 1.0 mm | **2.0 mm** |
| taper into the antenna's 0.5 mm pad | 1 mm neck | **4.5 mm, 6 steps** |

Two consequences worth naming. A 2.95 mm line cannot simply butt against a
0.5 mm feed pad — the step would be a real discontinuity and the wide line
would crowd the antenna's ground pin, so the last 4.5 mm tapers down in six
stages. And the pour keep-away corridor now stops 3 mm short of the plane
edge: at 2.0 mm either side it would otherwise cut a 7 mm notch into the
ground plane edge directly under the antenna, and that edge is part of the
antenna.

### Board edge, keep-out edge, and domain edge are three different things

Easy to conflate, and the RFsim plot draws two of them:

* **Board edge** (Edge.Cuts, solid line). The antenna's keep-out box sits
  0.9 mm inside the top edge. Do **not** extend the board past the antenna to
  "give it room": dielectric alongside and above the arm loads it, which pulls
  the resonance *down* and adds loss. An inverted-F belongs at the edge of its
  board. The only reason to keep any margin at all is mechanical — routing
  tolerance — and 0.9 mm is enough.
* **Keep-out edge** (the ground plane edge, Cmts.User line at y = 66.25). This
  is the antenna's ground reference and it is not negotiable: no copper above
  it on any layer. Extending the *plane* into the keep-out would short the
  antenna's near field to ground and destroy it.
* **Domain edge** (the dashed rectangle in RFsim's plot). This is the
  simulation air box, nothing to do with the board. **This is the one to
  extend** — from 4 mm to at least 31 mm, per the table above.

### What could not be established analytically

A quarter-wave check on the arm would have predicted the resonance without any
simulator, and it does not work here — worth recording so nobody retries it.
The radiator's copper area is 21.31 mm² at 0.5 mm wide, so 42.6 mm of
developed strip, or a ~32.8 mm arm after subtracting the two 4.9 mm legs. For
that to resonate at 2.45 GHz needs εr,eff = 0.87, and at 2.83 GHz εr,eff =
0.65 — both below 1, i.e. faster than light. The developed length therefore
over-predicts the electrical length by a wide margin, which is exactly what a
meander does: adjacent segments carry opposing currents that partly cancel. So
there is no shortcut, and the resonance of this geometry can only come from a
correctly set up field solver or a VNA.

## The footprints

`Texas_SWRA117D_2.4GHz_Left.kicad_mod` is the supplied legacy (KiCad 4/5)
footprint, converted to the modern format by `tools/convert_legacy_footprint.py`
— `module` → `footprint`, `fp_text reference/value` → `property`, bare `width`
→ `stroke`, `attr virtual` → `exclude_from_pos_files exclude_from_bom`, the v5
`connect` pad → `smd`, and a UUID on every item. The 53-vertex antenna
polygon, the pads and the `Dwgs.User` keep-out box are carried over unchanged.
`SWRA117D_2G4_Left_retuned.kicad_mod` is that footprint scaled x1.155 by
`tools/scale_footprint.py` (copper 16.63 × 6.24 mm, strip 0.578 mm, feed pad
0.578 mm, ground pin at 2.425 mm). **The board uses the published one** — the
scaled copy is an example of the retune path, kept for when a valid simulation
says what k should be. See [Retuning](#retuning-once-a-valid-run-exists).

The SMA footprint is a generic end launch, generated by
`tools/gen_sma_footprint.py` from the stackup: a 2.95 mm signal pad with a
ground tab 2.0 mm either side on the top, and one solid 12.95 mm ground pad
under the whole launch on the bottom so the port keeps its reference without a
zone fill. It
and the 0402 land are parts written for this board, not copies of the stock
KiCad library; check them against your own connector and assembly rules
before ordering.

## The board

2 layers, 40 × 30 mm, **1.6 mm FR4** (εr 4.5, tan δ 0.02), 35 µm copper —
the stackup is in the board file, so the 3D viewer and any EM export see it.

| item | value | why |
|------|-------|-----|
| 50 Ω microstrip | **w = 2.95 mm** | not a chosen number: `gen_project.py` synthesises it from `SUB_H`/`SUB_ER` (50.2 Ω), and the SMA footprint is generated to match |
| feed length | 23.5 mm, board edge to feed pad | λg ≈ 66 mm at 2.45 GHz, so ≈ 128° of line; the last 4.5 mm tapers 2.95 → 0.5 mm in 6 steps to meet the antenna pad |
| ground plane | y ≥ 66.25 mm only | its edge is the antenna's ground reference, and `gen_project.py` reads it from the footprint's own keep-out box so a rescaled antenna moves it |
| antenna keep-out | rule area above that edge, F.Cu **and** B.Cu | no pour, no tracks, no vias under or beside the antenna |
| top pour keep-away | 2.0 mm either side of the feed, starting 3 mm below the plane edge | keeps the line a microstrip; stopping short of the edge leaves the antenna a straight plane edge instead of a notch |
| stitching | 41 vias | 8 in the connector pads, an 11-via fence at 3 mm along the plane edge, and a 5 mm grid over the pour — `tools/stitching_span.py` measures the worst-stitched point at 4.67 mm from a via, a 9.35 mm span, half-wave resonant at 7.6 GHz; see [Ground stitching](#ground-stitching-the-rule-and-what-it-is-for) |

The 2.95 mm line tapers to 0.5 mm over the last 4.5 mm to meet the antenna's
0.5 mm feed pad. That is λg/15, long enough to matter, which is why it is six
graded steps rather than a butt joint — and it is in the openEMS geometry
anyway, because that reads the real tracks. `BOARD_H` in `tools/gen_project.py` sets the board
height: 26 mm gives an 18.3 mm feed, 22 mm gives 14.3 mm. Both shorten the
feed by shrinking the ground plane, which is the antenna's counterpoise — so
that trade buys tidiness at the cost of antenna performance, not the other way
round.

### A shorter feed does not move the resonance

Worth being explicit, because it is the one thing a short feed cannot do. For
a lossless line matched to the port, |Γ| at the connector equals |Γ| at the
antenna: a length of 50 Ω line rotates the Smith chart trace but cannot change
its radius. So the VSWR-versus-frequency curve — and the frequency where it
dips — is the antenna's, whatever the feed length.

What the shorter feed does buy: 129° of rotation instead of 172°, so the Smith
trace winds round less and the impedance is easier to read; slightly less FR4
loss; and no corner to argue about. If a simulation puts the dip at the wrong
frequency, the feed line is not the thing to change.

The antenna polygon overlaps the plane edge by 0.25 mm at 28 of its vertices —
that is the part of both legs that lands on the pads, so the pads' own
clearance covers it. Nothing else crosses the line.

### No matching network — components, but AN058 says lay out the pads

Two TI documents, and they are not in conflict once you separate *values* from
*footprints*.

**SWRA117D on this antenna:** it is a 50 Ω design, so nothing goes between the
connector and the radiator. That is why this board has no L and no C in the
path, and it is the right answer to "what value should I fit".

**AN058 as a general rule, section 3.4:** *"Mismatching of the antenna is one
of the largest factors that reduce the total RF link budget. To avoid
unnecessary mismatch losses, it is recommended to add a pi-matching network so
that the antenna can always be matched. If the antenna design is adequately
matched then it just takes one zero ohm resistor or DC block cap to be
inserted into the pi-matching network."*

That is about **pads, not parts**: lay the pi network out, and populate it
with a 0 Ω link when the antenna needs no correction. The second antenna's
board does exactly that — `Z61` and `Z63` are on the PCB and unfitted. This
board has neither, so there is nowhere to put a component if an enclosure
detunes it, and AN058's own measurements say an enclosure will.

Adding three unpopulated 0402 lands and a 0 Ω link in the feed would close
that gap without putting anything in the signal path today. It is not done
here because it was ruled out for this board explicitly; the evidence above
is new, so the decision is worth revisiting rather than reversing quietly.

The SWRA117D antenna *is* a 50 Ω design, so the board is built without one:
connector → 50 Ω line → radiator. That is also the only honest way to
*measure* the antenna — a 0 Ω 0402 jumper would still add a few tenths of a nH
plus two pad discontinuities, and any fitted reactance would be correcting a
model rather than the hardware.

It is worth knowing when that changes. "50 Ω" holds for the antenna in the
conditions the application note assumes, and a real product is never quite
those conditions:

* **Stackup.** The published dimensions belong to a particular board thickness
  and copper/dielectric stack. This one is 1.6 mm FR4, and the arm's
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

### Ground stitching: the rule, and what it is for

Stitching vias tie the top pour to the bottom plane. The pitch rule everyone
quotes is **≤ λ/20 at the highest frequency of interest, measured in the
dielectric** (λ = c / f√εr, so εr = 4.5 here, *not* the microstrip εr,eff):

| f | λ in FR4 | λ/10 | λ/20 |
|---|---|---|---|
| 2.45 GHz | 57.7 mm | 5.8 mm | 2.9 mm |
| 4.90 GHz (2nd harmonic) | 28.8 mm | 2.9 mm | 1.4 mm |
| 7.35 GHz (3rd harmonic) | 19.4 mm | 1.9 mm | 1.0 mm |

But the pitch is the *consequence*, not the rule. What actually matters is
that no piece of pour is left electrically large, because a patch of copper
d wide is half-wave resonant at c / 2d√εr — and a resonant patch is a cavity
that stores energy, couples between traces and radiates from the board edge:

| unstitched patch | resonates at |
|---|---|
| 22 mm | 3.25 GHz |
| 12 mm | 5.96 GHz |
| 8 mm | 8.9 GHz |
| 5 mm | 14.3 GHz |

Vias also have inductance, which is why one is rarely enough anywhere it
matters. A 0.3 mm drill through 1.6 mm FR4 is about 1.30 nH — **20 Ω at
2.45 GHz**. Two in parallel give 10 Ω, four give 5 Ω. So a shunt component's
ground pad wants two or more vias, not one, or the component sees tens of ohms
of inductance in series with it. (On the 0.8 mm stackup this board started
from, the same via was 0.54 nH and 8.3 Ω: via inductance scales with board
thickness, so doubling the thickness doubles the penalty for stitching thinly.)

This board stitches for three distinct reasons, which is the useful way to
think about it:

| where | why | pitch here |
|---|---|---|
| 8 vias inside the connector's own pads | the return current has to cross layers at the launch; this is the one place vias are not optional | — |
| 11-via fence along the plane edge | stops the plane pair radiating from its open edge | 3.0 mm = λ/19 at 2.45 GHz |
| 30-via grid over the pour | keeps every pour patch small | 5.0 mm, patches ≤ 8.4 mm → 8.5 GHz |

That grid was added after measuring the gap: the feed corridor splits the top
pour into two ~22 mm islands, each stitched only along its top edge, and a
22 mm island is half-wave resonant at **3.25 GHz** — inside the range this
board gets simulated over. With the grid the worst-case distance from any pour
copper to a via is 4.22 mm, so the largest span is 8.4 mm and the first patch
resonance moves to 8.5 GHz.

**Where vias earn their place, in priority order:**

1. **Beside every layer-changing signal via**, within 1–2 mm. The return
   current must change layers too, and if there is no ground via nearby it
   detours around the plane, which is both an inductance and a loop antenna.
2. **At the connector / port launch**, as above.
3. **Along the edges of a plane pair**, as a fence at λ/20.
4. **Along both gaps of a coplanar waveguide.** GCPW *requires* this: without
   it the coplanar ground floats between vias and supports its own modes. A
   via fence beside an ordinary microstrip, by contrast, does close to nothing
   — the return current is already in the plane directly under the trace.
5. **Between RF blocks**, as a wall, where isolation is the goal.
6. **Area fill**, to keep patches small — the lowest-value job, and the one
   those tidy grids on educational boards usually are.

So the rows of aligned vias you have seen are sometimes doing job 3 or 4,
where they are essential, and sometimes decoration. The test is simple: ask
what return current crosses layers there. If the answer is "none", the vias
are cosmetic — on a 2-layer board with an intact pour they cost drill hits and
nothing else, but they are not what makes a layout work.

One exception worth knowing: do not stitch into an antenna keep-out. A via
there is metal in the near field and will detune the antenna, which is why
this board's fence stops at the plane edge and the keep-out rule area forbids
vias above it.

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
a lossless 50 Ω `T` element (23.5 mm, TD = 143 ps) and computes
Γ = 2·v(in) − 1 from a 1 V source behind 50 Ω.

```sh
cd kicad/sim && ngspice -b s11_antenna.cir       # writes s11_results.csv
```

| | Z at the antenna | Z at the SMA | S11 | VSWR |
|---|---|---|---|---|
| 2.400 GHz | 39.5 − 25.8j Ω | 88.0 + 16.8j Ω | −10.5 dB | 1.85 |
| 2.442 GHz | 44.9 − 15.6j Ω | 70.1 + 4.2j Ω | −15.4 dB | 1.41 |
| 2.4835 GHz | 51.4 − 4.7j Ω | 54.0 + 2.9j Ω | −26.4 dB | 1.10 |

Best match −28.8 dB at 2.493 GHz; below −10 dB from 2.394 to 2.595 GHz, so
the antenna covers 2.400–2.4835 GHz unaided. The two impedance columns show
what the line does: 126° of matched line rotates Zin round the Smith
chart but cannot change |S11| — which is exactly why a lumped antenna model is
still the right tool for return loss at the connector, and why the S11 column
is identical to the 32 mm version of this board.

**The antenna model is design intent, not a prediction of the etched
geometry.** It is a 2.454 GHz resonator — the antenna this board is meant to
have. Use a correctly set up field solver to find where the copper actually
resonates (see the four settings above), and this deck to work out what to do
about the impedance once you know.

### 2. Full wave (openEMS)

`sim/openems/swra117d_openems.py` builds the FDTD model from a board file —
outline, stackup, ground plane edge, the antenna polygon, the stitching vias,
any routed feed and the pour keep-away corridors all come out of the
`.kicad_pcb`, so the model cannot drift away from the layout. The KiCad
keyhole slits (the clearance ring around the ground pin) are collapsed, since
they are far below the mesh size.

```sh
python3 sim/openems/swra117d_openems.py --dry-run   # geometry only, no solver
python3 sim/openems/swra117d_openems.py --plot      # FDTD run + plots
python3 sim/openems/swra117d_openems.py --dry-run \
        --board sim/board/swra117d_2g4_sim.kicad_pcb   # the same, no connector
```

`--dry-run` needs nothing but Python and reports what it read:

```
board file     : swra117d_2g4_antenna.kicad_pcb
board          : 40.0 x 30.0 mm, 1.6 mm FR4 (er 4.5, tan d 0.02)
ground plane   : y = 0 .. 23.75 mm (antenna region 23.75 .. 30.0 mm is clear)
feed line      : 8 segments, 23.5 mm total, microstrip port launches along y from (24.00, 0.00) mm, feed pad at (24.00, 23.50) mm
                 ( 24.00,  0.00) -> ( 24.00, 18.50)  w = 2.95 mm
                 ( 24.00, 18.50) -> ( 24.00, 19.25)  w = 2.746 mm
                 ( 24.00, 19.25) -> ( 24.00, 20.00)  w = 2.338 mm
                 ( 24.00, 20.00) -> ( 24.00, 20.75)  w = 1.929 mm
                 ( 24.00, 20.75) -> ( 24.00, 21.50)  w = 1.521 mm
                 ( 24.00, 21.50) -> ( 24.00, 22.25)  w = 1.113 mm
                 ( 24.00, 22.25) -> ( 24.00, 23.00)  w = 0.704 mm
                 ( 24.00, 23.00) -> ( 24.00, 23.50)  w = 0.5 mm
stitching vias : 41, 11 of them within 2 mm of the plane edge
top pour       : 5 boxes around 1 keep-away corridors
antenna copper : 29 vertices, x 12.15..26.55 mm, y 23.25..28.65 mm
```

and on the RFsim project, where the ground is on one layer and there is
nothing to stitch:

```
board file     : swra117d_2g4_sim.kicad_pcb
board          : 40.0 x 30.0 mm, 1.6 mm FR4 (er 4.5, tan d 0.02)
ground plane   : B.Cu, y = 0 .. 23.75 mm (antenna region 23.75 .. 30.0 mm is clear)
feed line      : 8 segments, 23.5 mm total, microstrip port launches along y from (24.00, 0.00) mm, feed pad at (24.00, 23.50) mm
                 ( 24.00,  0.00) -> ( 24.00, 18.50)  w = 2.95 mm
                 ( 24.00, 18.50) -> ( 24.00, 19.25)  w = 2.746 mm
                 ( 24.00, 19.25) -> ( 24.00, 20.00)  w = 2.338 mm
                 ( 24.00, 20.00) -> ( 24.00, 20.75)  w = 1.929 mm
                 ( 24.00, 20.75) -> ( 24.00, 21.50)  w = 1.521 mm
                 ( 24.00, 21.50) -> ( 24.00, 22.25)  w = 1.113 mm
                 ( 24.00, 22.25) -> ( 24.00, 23.00)  w = 0.704 mm
                 ( 24.00, 23.00) -> ( 24.00, 23.50)  w = 0.5 mm
stitching vias : none - with no top pour there is nothing to stitch; the antenna's own ground pad carries the short
top pour       : none - ground is on B.Cu only, as SWRA117D Figure 3 draws it
antenna copper : 29 vertices, x 12.15..26.55 mm, y 23.25..28.65 mm
```

A real run needs openEMS with its Python bindings
(<https://docs.openems.de/python/install.html>) and prints S11, the −10 dB
band, the input impedance at the band edges and the peak directivity, and
writes `s11_openems.csv`. Copper is a zero-thickness sheet, vias are square
barrels of the drill diameter, and on the fabrication board the connector body
is not modelled (the port launches at the board edge in its place).

### 3. In-KiCad RFsim plugin — port setup

RFsim reads the board directly, so three things need saying.

**On the fabrication board, set Port 1 to "Coplanar (CPW)".** RFsim reports
coplanar copper beside the feed line, and it is right — that is the end-launch
footprint doing its job. `SMA_EdgeMount_Generic` puts a 2.95 mm signal pad
between two ground pads 2.0 mm either side, with ground underneath: a grounded
coplanar waveguide, not a microstrip. A Lumped or Microstrip port looks for
its return directly beneath the signal only, so it mis-models the launch.
(The RFsim project below has no connector footprint and so no coplanar
ground beside the line: there, **Microstrip (MSL)** is the matching port —
see [The RFsim project](#the-rfsim-project-swra117d-figure-3-as-the-note-draws-it).)

**The launch no longer needs a zone fill to have a reference.** The warning
*"no copper on reference layer B.Cu"* was true of the first version of this
board: the only B.Cu copper under the launch came from the ground pour, and
pours are stored unfilled (KiCad computes fills on **B**), so nothing was
there to reference. The SMA footprint now carries a solid 3.5 × 12.95 mm B.Cu
ground pad under the whole launch — real copper in the file, net GND, directly
under the port pad, which is also what an end-launch connector wants
physically. `check_project.py` verifies the port pad sits fully inside it.

**Still fill the zones** (**B**) before DRC, and before simulating anything
past the launch: the rest of the feed line is referenced to the B.Cu pour, and
the checker warns while that fill is missing.

The line impedances are deliberately all within a couple of ohms of 50, which
`tools/line_impedance.py` computes from the stackup in the board file:

| | Z₀ | |
|---|---|---|
| feed line, microstrip, 2.95 mm | **50.2 Ω** | εr,eff 3.39, λg 66.4 mm |
| feed line with the pour at its 2.0 mm keep-away, CPWG | **49.8 Ω** | εr,eff 3.30 |
| launch, after 8 ground vias in the connector pads | — | coplanar ground tied to the plane at the port |
| 50 Ω microstrip width for this stackup | 2.97 mm | Hammerstad + Wheeler, rounded to 2.95 on the board |

`tools/line_impedance.py` reads the stackup, the feed width and the keep-away
straight out of the board file, so those numbers move when the board does
rather than going stale here. The keep-away was chosen for this: at 2.0 mm the
coplanar ground is far enough that the line is still 49.8 Ω, where 0.8 mm
would pull it to 45.1 Ω. So if a simulation shows a badly matched *line*, the
geometry is not the cause — check the port type and the reference layer first,
and remember the radiator shorts the port (above).

For other solvers, export from KiCad as usual: Gerbers or DXF for 2.5D tools
(Sonnet, ADS Momentum), STEP for 3D (HFSS, CST).

## Regenerating and checking the files

```sh
python3 tools/gen_project.py         # rebuild .kicad_sch / .kicad_pcb / .kicad_pro
python3 tools/check_project.py       # static netlist + clearance + keep-out checks
python3 tools/gen_sim_board.py       # rebuild the RFsim project (sch + pcb + pro)
python3 tools/check_sim_board.py     # check it: no connector, feed reaches the edge
python3 tools/mutate_sim_board.py    # prove those checks actually fail when they should
python3 tools/verify_against_swra117d.py   # the footprint against Table 1, dimension by dimension
python3 tools/line_impedance.py      # microstrip and CPWG impedance, read from the board
python3 tools/stitching_span.py      # largest patch of top pour with no via in it
python3 tools/gen_sma_footprint.py               # the SMA land, for the stackup
python3 tools/gen_sma_footprint.py --style port # the same land with no coplanar tabs
python3 tools/scale_footprint.py     # retune the antenna by uniform scaling
python3 tools/gen_dn024_symbols.py    # the second antenna's symbol library
python3 tools/gen_dn024_footprint.py # its radiator, from SWRA227E Table 1
python3 tools/gen_dn024_project.py   # its schematic + board + project
python3 tools/check_dn024.py         # and its checks
python3 tools/verify_against_swra227e.py   # its footprint against Table 1
python3 tools/board_to_svg.py docs/board-drawing.svg
python3 tools/board_to_svg.py docs/sim-board-drawing.svg sim/board/swra117d_2g4_sim.kicad_pcb
```

`gen_project.py` embeds the symbol and the footprints into the schematic and
the board, so all three files agree on pins, pads and nets by construction.
It is a one-shot generator: **once you edit anything in KiCad, KiCad owns the
files** — re-running it would overwrite your work. `gen_sim_board.py` imports
it and reuses the same outline, stackup, plane edge and footprint, so the
simulation board cannot drift away from the one that gets built.

`check_project.py` is the safety net used while writing these files. It
extracts the schematic netlist from the wire geometry, rebuilds the board pad
positions (rotations included) and verifies that

* every embedded symbol resolves to this project's library and is identical to
  it, so KiCad has nothing to report as `lib_symbol_mismatch`,
* every symbol pin lands on a wire and every net matches the intended one,
* every board pad carries the net the schematic gives it,
* every track ends on a pad, a via or another track,
* copper of different nets keeps ≥ 0.15 mm apart,
* nothing but the antenna lives above the ground plane edge — which the
  checker reads from the board's own zones, never a hardcoded value, so it
  follows the antenna when it moves or is rescaled,
* every end of the feed line sits over the B.Cu ground pour, so the microstrip
  has a return path — and it says so when the zones are still unfilled,
* the port pad sits inside the bottom-side ground pad, so an RF simulator
  finds reference copper at the launch whether or not the pours are filled,
* the radiator touches both antenna pads, which is the inverted-F short,
* every island of pour, on either layer, carries at least one stitching via,
* the feed line and the port pad are the same width, and that width is the one
  the stackup implies,
* the antenna footprint still matches all 14 dimensions of SWRA117D Table 1 —
  a redrawn or rescaled radiator fails here rather than passing quietly.

`check_sim_board.py` does the same job for the RFsim project, asking a
different question: is what the solver sees the antenna and its feed, and
nothing else? See
[The RFsim project](#the-rfsim-project-swra117d-figure-3-as-the-note-draws-it).

```
ok   library: 7 symbols, 5 footprints parse cleanly
ok   schematic: 4 embedded symbols all match library/SWRA117D_RF.kicad_sym (no lib_symbol_mismatch)
ok   schematic: 7 pins placed, 5 wires, netlist matches the intended one
ok   board: 6 pads, 8 tracks, 41 vias, clearances >= 0.15 mm, keep-out above y = 66.25 clean
ok   board: 28 antenna polygon vertices overlap the plane edge, all of them inside the antenna's own pads
ok   board: all 16 feed line ends sit over the B.Cu ground pour (reference plane present)
ok   board: 2 copper zones carry no fill yet - press B in the PCB editor before running DRC or an RF simulation, or tools that look for the reference layer will find it empty
ok   board: port pad 3.5 x 2.95 mm sits inside a 3.5 x 12.95 mm B.Cu ground pad, so the launch is referenced without a zone fill
ok   board: the radiator is one piece of copper touching both antenna pads (inverted-F short: the port is a DC short to GND)
ok   board: all 2 pour islands across 2 layers carry stitching vias (top and bottom ground tied together everywhere)
ok   board: feed line 2.95 mm matches the 2.95 mm port pad, and the width is derived from the stackup
ok   board: Texas_SWRA117D_2.4GHz_Left matches all 14 dimensions of SWRA117D Table 1 within 11 um (exact copy)

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

## The RFsim project: SWRA117D Figure 3, as the note draws it

`sim/board/swra117d_2g4_sim.*` is a second complete KiCad project —
schematic, board and project file. Open it and run RFsim on it.

Look at Figure 3 again. It is a two-layer board where layer 1 carries the
antenna and the feed, and the ground is the grey area captioned **"Ground
Layer 2"** — layer 2 and nowhere else. There is no ground copper on the top
layer at all, and exactly one via in the whole picture: **"Via to ground"**,
the W1 = 0.90 mm pad that shorts the inverted-F. This project is that
arrangement, on the fabricated 1.6 mm stackup.

That single change removes three arguments at once:

* **No coplanar ground anywhere near the line**, so the feed is unambiguously
  a microstrip over layer 2 and **MSL** is the port model with nothing left to
  debate.
* **No top pour**, so no pour islands to resonate and nothing to stitch — the
  only via on the board is the antenna's own.
* **The port's reference is the ground plane itself**, directly under the
  signal pad, rather than a second sheet of copper that has to be tied to it.

The connector goes with it. J1 is real hardware and belongs on the board that
gets built, but inside a simulation its coplanar ground tabs are copper that
is not the antenna, they carry the port's return current, and the bright near
field around them reads as an antenna problem when it is a launch. What
replaces it is the minimum a solver needs: `RF_Port_Land` — the signal pad,
the width of the 50 Ω line, with a solid B.Cu ground pad directly underneath.

**Why a land and not a bare track end.** RFsim attaches its port to a *pad*,
and it needs reference copper under the pad it drives. Leave the board without
one and it falls back to the antenna's own feed pad, which sits on the plane
edge with no plane beneath it, and stops with:

```
Port 1 (AE1 Pad 1 (ANT_FEED)): no copper on reference layer B.Cu under the pad.
```

The land answers that directly, and it answers it with a **pad rather than a
zone**: zones ship unfilled, so a reference that depends on a fill is a
reference that is missing the first time anyone opens the project.

| | fabrication project | RFsim project |
|---|---|---|
| antenna | `Texas_SWRA117D_2.4GHz_Left`, exact Table 1 copy | **the same file**, unchanged |
| substrate | 1.6 mm FR4, εr 4.5, 35 µm | the same |
| outline, plane edge, keep-out | 40 × 30 mm, plane from y = 66.25 | the same |
| feed | 2.95 mm 50 Ω microstrip, 23.5 mm, 6-step taper | **the same line**, ending on the board edge |
| ground | F.Cu **and** B.Cu pours, 41 stitching vias | **B.Cu only** — Figure 3's "Ground Layer 2" |
| vias | 41 | **one**: the antenna's own ground pad, Figure 3's "Via to ground" |
| launch | `SMA_EdgeMount_Generic`: signal pad, **two coplanar ground tabs**, B.Cu ground pad | `RF_Port_Land`: signal pad and B.Cu ground pad, **no coplanar tabs** |
| port model | Coplanar (CPW) — the tabs and the top pour make it one | **Microstrip (MSL)** |
| schematic port | J1, `Conn_Coaxial_SMA` | `P1`, `RF_PORT` |

`tools/gen_sim_board.py` imports `tools/gen_project.py` and reuses its
outline, stackup, plane edge, footprint, feed taper and pour rules, so the two
projects cannot drift apart. The differences are the ones in that table.

Both lands come out of `tools/gen_sma_footprint.py`, from the same code and
the same stackup — `--style sma` keeps the coplanar tabs, `--style port` drops
them.

Two details worth knowing:

* **The absent top pour is the design, not an omission.** With it, the launch
  is a grounded coplanar waveguide and CPW fits; without it the line is a plain
  microstrip over layer 2 and **MSL** is the match. Leaving the port on CPW
  here produces a plausible, wrong S11 and no warning. `check_sim_board.py`
  fails if anyone adds an F.Cu pour, or an F.Cu ground pad to the land,
  because either silently invalidates the port model the documentation tells
  you to use.
* **Copper touches the board edge on purpose.** A port launch belongs at the
  edge, so this project's `min_copper_edge_clearance` is 0. That rule exists to
  protect a *fabricated* board; this one is not meant to be fabricated.

### Running it

```sh
python3 tools/gen_sim_board.py       # rebuild schematic + board + project
python3 tools/check_sim_board.py     # check it
python3 tools/mutate_sim_board.py    # prove those checks can fail
```

In KiCad: open `sim/board/swra117d_2g4_sim.kicad_pro`, press **B** in the PCB
editor to fill the zone, then set **port 1 to P1 pad 1** and its model to
**Microstrip (MSL)**. The coplanar/CPW advice from
[section 3](#3-in-kicad-rfsim-plugin--port-setup) does **not** apply here.

If RFsim names `AE1 Pad 1` as the port, it has not found the land — check that
P1 is on the board (it is `on_board yes` with the `RF_Port_Land` footprint) and
that you are on the current version of the project. The antenna's own feed pad
is never a valid port here: it sits on the ground plane edge with the keep-out
above it, so there is no reference copper under it by design.

The other three settings are unchanged: zones filled, substrate 1.6 mm /
εr 4.5, and a domain margin of λ/4 at the bottom of your sweep — 37.5 mm if
it starts at 2 GHz.

`sim/openems/swra117d_openems.py --board sim/board/swra117d_2g4_sim.kicad_pcb`
models the same file, if you want a second opinion from a different solver.

### What the checker checks

```
ok   board: the radiator plus a bare port land - no connector, and no coplanar ground beside the line, so the launch is microstrip (use an MSL port, not CPW)
ok   board: Texas_SWRA117D_2.4GHz_Left matches all 14 dimensions of SWRA117D Table 1 within 11 um (exact copy) - the same footprint file the fabrication board uses
ok   board: ground plane 39.6 x 23.5 mm on B.Cu only, as Figure 3 draws it - no ground copper on F.Cu
ok   board: antenna keep-out runs down to the plane edge at y = 66.25, on F.Cu and B.Cu
ok   port: pad 1 is 2.95 x 3.50 mm over a 12.95 x 3.50 mm B.Cu ground pad, so the reference is real copper and does not wait on a zone fill
ok   feed: 8 segments, 21.8 mm, from the port pad at (124.0, 88.25) (2.95 mm wide) down to the 0.5 mm antenna pad
ok   board: one via on the board - the antenna's own ground pad, 0.90 mm wide with a 0.3 mm drill, which is Figure 3's 'Via to ground' (W1 = 0.90 mm)
ok   board: the feed is the only copper crossing the plane edge at y = 66.25, and its neck stops exactly on it
ok   board: 1 copper zone(s) carry no fill yet - open the board and press B before simulating, or the model has no ground plane
ok   schematic: 4 embedded symbols match the library, 7 pins all land on wires, ['#FLG01', '#PWR01', '#PWR02', 'AE1', 'P1'] placed

0 problem(s)
```

ok   board: the radiator plus a bare port land - no connector, and no coplanar ground beside the line, so the launch is microstrip (use an MSL port, not CPW)
ok   board: Texas_SWRA117D_2.4GHz_Left matches all 14 dimensions of SWRA117D Table 1 within 11 um (exact copy) - the same footprint file the fabrication board uses
ok   board: ground plane 39.6 x 23.5 mm on F.Cu and B.Cu, same outline, both on GND
ok   board: antenna keep-out runs down to the plane edge at y = 66.25, on F.Cu and B.Cu
ok   port: pad 1 is 2.95 x 3.50 mm over a 12.95 x 3.50 mm B.Cu ground pad, so the reference is real copper and does not wait on a zone fill
ok   feed: 8 segments, 21.8 mm, from the port pad at (124.0, 88.25) (2.95 mm wide) down to the 0.5 mm antenna pad
ok   port: 8 ground vias within 7.0 mm of the launch, nearest at 4.05 mm
ok   board: 41 ground vias total, all F.Cu -> B.Cu
ok   board: every via clears the feed line by at least 2.20 mm (minimum 0.15 mm)
ok   board: the top pour is held 2.00 mm off the 2.95 mm line, so it stays a microstrip
ok   board: 2 copper zone(s) carry no fill yet - open the board and press B before simulating, or the model has no ground plane
ok   schematic: 4 embedded symbols match the library, 7 pins all land on wires, ['#FLG01', '#PWR01', '#PWR02', 'AE1', 'P1'] placed

0 problem(s)
```

ok   board: one footprint (the radiator) and no connector - the port launches off the bare feed line
ok   board: Texas_SWRA117D_2.4GHz_Left matches all 14 dimensions of SWRA117D Table 1 within 11 um (exact copy) - the same footprint file the fabrication board uses
ok   board: ground plane 39.6 x 23.5 mm on F.Cu and B.Cu, same outline, both on GND
ok   board: antenna keep-out runs down to the plane edge at y = 66.25, on F.Cu and B.Cu
ok   feed: 8 segments, 23.5 mm, from the board edge at (124.0, 90.0) (2.95 mm wide) down to the 0.5 mm antenna pad - port 1 goes on the edge end
ok   port: 6 ground vias within 6.0 mm of the launch, nearest at 4.01 mm
ok   board: 41 ground vias total, all F.Cu -> B.Cu
ok   board: every via clears the feed line by at least 2.20 mm (minimum 0.15 mm)
ok   board: the top pour is held 2.00 mm off the 2.95 mm line, so it stays a microstrip
ok   board: 2 copper zone(s) carry no fill yet - open the board and press B before simulating, or the model has no ground plane
ok   schematic: 4 embedded symbols match the library, 5 pins all land on wires, ['#FLG01', '#PWR01', 'AE1', 'P1'] placed

0 problem(s)
```

Those checks are mutation-tested, and the test is in the repo:
`tools/mutate_sim_board.py` breaks a scratch copy of the project 18 different
ways and asserts the checker catches each one — a connector put back, the port
land deleted, its B.Cu reference pad deleted or made narrower than the port
pad, coplanar ground tabs added back at the port, **a ground pour added on the
top layer**, **a stitching via added that Figure 3 does not have**, **the
antenna's ground pad turned from a plated hole into an SMD pad**, the layer 2
ground deleted, the feed line deleted, stopped short of the port pad, not
landing on the antenna pad, branching, or widened until it spills into the
keep-out, the keep-out stopping short of the plane edge, `P1` left off the
board, an embedded symbol edited away from the library, and a pin lifted off
its wire.

```
$ python3 tools/mutate_sim_board.py
caught      a ground pour added on the top layer too
              board: ground pour on F.Cu as well as B.Cu - Figure 3 puts the ground on layer 2 only...
caught      a stitching via added that Figure 3 does not have
              board: 1 stitching via(s) at [(110.0, 75.0)] - with ground on layer 2 only there is...
...
18/18 mutations caught
```

A mutation that exits non-zero without printing a finding is reported as
`CRASHED`, not as caught: a checker that throws has not detected anything.

[`docs/sim-board-drawing.svg`](docs/sim-board-drawing.svg) is the drawing,
generated from this board by the same renderer as the other one.

## The second antenna: TI DN024 meandering monopole

`dn024/dn024_monopole_868_2440.*` is a separate, complete project for a
different antenna: the TI DN024 / **SWRA227E** meandering monopole, dual band
**868 + 2440 MHz**. It shares the toolchain and nothing else — different
radiator, different band, different rules.

Four differences from the inverted-F are worth stating up front, because three
of them contradict advice that is correct for the first antenna:

| | SWRA117D inverted-F | DN024 monopole |
|---|---|---|
| **matching** | none — "the antenna is a 50 Ω design" | **required.** "It is recommended to use a pi-matching network at the feed point ... since the geometry of the ground plane affects the impedance of the antenna" |
| **copper** | one layer | **both layers**, "this enables a lower resistive loss and gives a slightly wider bandwidth" |
| **DC** | short to ground (the F's strap) | **open** — a monopole has one terminal |
| **ground plane** | part of the antenna, size matters | part of the antenna, size matters **and changes the match**: "For larger ground planes L4 would have to be further reduced or the antenna match re-calculated" |

So the matching network here is not this project's invention — it is TI's, and
the values are published. That is the opposite of the first board, where
adding one would have been meddling.

### What is built, and the two choices behind it

**Dual band, not single band.** The dual band configuration keeps L4 at its
published 38.0 mm, so the radiator is an exact copy of Table 1 with nothing
guessed. The single band 868/915/920 MHz variant needs L4 *"shortened to the
silkscreen marking"* — and SWRA227E dimensions that marking nowhere. It can
only be read off Figure 2 by eye, which would stop the antenna being an exact
copy. If you need single band, that is the one number to get from the
CC-Antenna-DK Gerber rather than from the note.

**The reference ground plane, 43 × 63 mm.** Table 2 and Table 3 both name it,
and it is the only plane on which the published matching values apply as
given. `check_dn024.py` fails if it changes size, because that quietly
invalidates the BOM.

| | value | where it comes from |
|---|---|---|
| board | 45 × 95 mm, 1.6 mm FR4 | Table 2/3; the note specifies 1.6 mm FR4 |
| ground plane | 43 × 63 mm | Table 2/3 |
| antenna | 38 × 25 mm, 2.0 mm trace | Table 1 — `L4 × X2`, `W` |
| clear either side | 2.5 mm | **observed**: the reference centres 38 mm of antenna on 43 mm of ground. DN024 gives no clearance dimension of its own |
| Z62 | **3.9 pF series** | Table 3, dual band |
| Z61, Z63 | **not fitted** | Table 3 — laid out anyway, which is the note's own reason for the network: somewhere to compensate detuning from an enclosure |
| measured | SWR 1.2 @ 868, 1.6 @ 2.44 GHz | section 4.3 |
| bandwidth | 73 MHz @ 868, 354 MHz @ 2.4 GHz | section 4.3.2 |
| efficiency | 94–95 %, gain 3.4–4.9 dBi | OTA summary, Table 4 |

One thing is inferred rather than stated: **which of Z61/Z63 sits on which
side of Z62.** Figure 2 draws Z63 above Z61 with the connector below both, and
the single band BOM — series 1.8 nH with a shunt 2.7 pF — is an L match that
only works with the shunt on the source side. Both readings put Z61 nearest
the connector, which is how it is laid out.

### The radiator is arithmetic, not tracing

DN024 gives the antenna as a picture and nine numbers, and says the
authoritative source is the CC-Antenna-DK board 6 Gerber — which we do not
have — but also that *"If the CAD tool being used does not support import of
Gerber files, Figure 2 and Table 1 can be used."*

Table 1 closes on itself, and that is what makes the reading of Figure 2
checkable rather than a guess: four arms of `W` with three `L3` gaps between
them is 17.0 mm; `X2 − 17.0` leaves 8.0 mm below the bottom arm; and
`L1 + L5 − W` is also 8.0 mm. Two independent routes to the same number. The
envelope that falls out, `L4 × X2` = 38 × 25 mm, is the size the note quotes
in its own introduction — a third.

`tools/gen_dn024_footprint.py` builds the meander as a centre-line path and
offsets it into a constant-width ribbon; every segment is axis aligned and
every turn a right angle, so the mitres are exact rather than approximated.
`tools/verify_against_swra227e.py` then reads the polygon back out of the file
and re-derives Table 1 from it *without using the generator*:

```
TI_DN024_Monopole_868_2440.kicad_mod: 18 polygon vertices on B.Cu + F.Cu, 4 meander arms
  copper envelope 38.00 x 24.00 mm, feed pad 2.0 x 2.0 mm with a 0.6 mm plated hole

dim    SWRA227E   measured    error   what it is
L1        9.00      9.000    +0.000    feed trace, foot to the top of the bottom arm
L2       18.00     18.000    +0.000    bottom arm, feed trace's far edge to the right end
L3        3.00      3.000    +0.000    gap between meander arms
L4       38.00     38.000    +0.000    top arm, the full width of the antenna
L5        1.00      1.000    +0.000    ground plane edge to the foot of the feed trace
W         2.00      2.000    +0.000    trace width
X2       25.00     25.000    +0.000    ground plane edge to the top of the antenna

all 7 dimensions match SWRA227E Table 1 within 11 um: this is an exact copy
```

### Running it

```sh
python3 tools/gen_dn024_symbols.py     # library/TI_DN024.kicad_sym
python3 tools/gen_dn024_footprint.py   # the radiator, from Table 1
python3 tools/gen_dn024_project.py     # schematic + board + project
python3 tools/verify_against_swra227e.py
python3 tools/check_dn024.py
```

```
ok   library: TI_DN024 has 7 symbols and 1 footprints, all parsing cleanly
ok   schematic: 5 embedded symbols match their libraries, 13 pins on wires, netlist matches the intended one
ok   board: TI_DN024_Monopole_868_2440 matches all 7 dimensions of SWRA227E Table 1 within 11 um (exact copy), on B.Cu + F.Cu
ok   board: ground plane 43.0 x 63.0 mm on F.Cu and B.Cu, the size SWRA227E Table 3 measured the match on
ok   board: 11 pads, 14 tracks, 152 vias, every track end lands, keep-out above y = 91.0 clean, closest different-net tracks 0.36 mm
ok   pi network: Z62 series between RF_IN and ANT_FEED, Z61 shunt on the connector side, Z63 shunt on the antenna side; Z61 and Z63 laid out and unfitted, as Table 3 says
ok   pi network: both shunt ground pads reach the bottom plane through a via of their own
ok   board: 2 copper zone(s) carry no fill yet - press B in the PCB editor before DRC or any simulation

0 problem(s)
```

The two projects share `tools/gen_project.py`: parts name their symbol and
footprint libraries, so one generator serves both. Symbols are duplicated into
`TI_DN024.kicad_sym` rather than shared across libraries — a schematic embeds
a copy of every symbol it places and KiCad raises `lib_symbol_mismatch` on any
difference, so each project resolving everything it places inside one
in-project library is what keeps ERC quiet. Footprints are not compared that
way, so the DN024 board reuses the SMA and 0402 lands from the first library.

[`docs/dn024-board-drawing.svg`](docs/dn024-board-drawing.svg) is the drawing,
from the same renderer as the other two.

### Not done yet

No simulation and no RFsim project for this antenna. Two reasons, and the
second is the real one: 868 MHz needs a domain margin of λ/4 = **86 mm**
against the 37.5 mm the 2.4 GHz board needs, so the domain volume is about
12× larger and the run is correspondingly slower; and the pi network is a
lumped part of the answer here, so a full-wave run of the copper alone does
not give the S11 the note quotes — it gives the antenna's raw impedance, which
is then matched. Say the word and it is the same machinery as the first board.

## Reusing this on someone else's board

[`docs/antenna-integration-checklist.md`](docs/antenna-integration-checklist.md)
is the checklist these projects produced: 72 items across antenna placement,
feed, stitching, simulation setup, what to leave out of a model, bench
measurement, and tuning —
each one there because getting it wrong here cost a wrong answer. It is written to be applied to any printed
antenna, not just this one, and the "before you trust a simulation" section is
the part that has earned its place most.

[`docs/board-drawing.svg`](docs/board-drawing.svg) is generated by
`tools/board_to_svg.py` from the board file, so a review drawing can never
drift from the copper. Shapes carry class names rather than colours, so the
page embedding it can theme it.

## Reference

TI application note **SWRA117D (AN043)**, *Small Size 2.4 GHz PCB antenna*:
<https://www.ti.com/lit/an/swra117d/swra117d.pdf>

TI design note **SWRA227E (DN024)**, *Monopole PCB Antenna with Single or Dual
Band Option*: <https://www.ti.com/lit/an/swra227e/swra227e.pdf>

TI application note **SWRA161B (AN058)**, *Antenna Selection Guide*:
<https://www.ti.com/lit/an/swra161b/swra161b.pdf> — the methodology note the
other two point at, and the source for the bench procedure in the checklist.
Its Table 9 identifies these two antennas among TI's reference designs:

| | AN058 Table 9 | measured here |
|---|---|---|
| AN043 | "2.4 GHz PCB **Meandered** Inverted-F Antenna", 15 × 6 mm, *small size & small BW* | keep-out envelope 15.2 × 5.7 mm |
| DN024 board 6 | "Meandering Monopole", 39 × 25 mm, dual band 2.4 GHz & 868 MHz | copper envelope 38 × 25 mm |

Two things fall out of that table. The first antenna is **AN043**, not DN007 —
DN007 is a *different* inverted-F, 26 × 8 mm, which Table 9 describes as
*large BW & easy to tune* where AN043 is *small BW*. An earlier revision of
this file named the wrong one. The second is that both size columns land
within a millimetre of what the footprints here measure, which is a third
party's arithmetic agreeing with ours.
