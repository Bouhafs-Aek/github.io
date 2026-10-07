# TI reference PCB antennas in KiCad — an evaluation kit, with checks and RF simulation

**[`kit/`](#the-evaluation-kit-three-antennas-two-ground-planes) is six boards:
three TI reference antennas, each built twice — once on the ground plane its
note publishes, once on a 45 × 60 mm plane shared by all three.** That is the
deliverable. Everything below it is what the kit is made of.

Three TI reference antennas, each as a complete self-contained KiCad project,
each an exact copy of its application note's dimension table and each with a
checker that fails the build if it stops being one:

* **TI SWRA117D**, a **2.45 GHz printed inverted-F** (left-hand layout) — the
  radiator fed from a 50 Ω SMA port through a pi network carrying a 0 Ω link,
  because the note publishes no matching values and AN058 asks for the pads.
* **TI DN024 / SWRA227E**, a **868 + 2440 MHz meandering monopole** — copper
  on both layers and a pi matching network at the feed, because this note says
  it needs one and gives the values. It comes in **two launches**: an
  edge-mount SMA in `dn024/`, and the note's own vertical through-hole jack
  with the top ground cut away around the feed in `dn024_ti_form/`.

* **TI DN023 / SWRA228C**, a **868 / 915 / 955 MHz printed inverted-F** —
  one layer, no ground beneath it, approximately 50 Ω with nothing fitted, and
  tuned by *trimming* `L6` rather than by matching.

Plus two RFsim projects — the inverted-F drawn the way its Figure 3
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
│   ├── TI_DN023.kicad_sym           the third antenna's symbols
│   └── TI_DN023.pretty/             TI_DN023_IFA_868.kicad_mod, from Table 1
│   ├── TI_DN024.pretty/
│   │   ├── TI_DN024_Monopole_868_2440.kicad_mod  the radiator, from Table 1
│   │   └── SMA_ThruHole_4Post.kicad_mod          P6, measured off Figure 2
│   └── SWRA117D_RF.pretty/
│       ├── Texas_SWRA117D_2.4GHz_Left.kicad_mod  antenna, as published
│       ├── SWRA117D_2G4_Left_retuned.kicad_mod   antenna, scaled x1.155
│       ├── SMA_EdgeMount_Generic.kicad_mod       50 Ω connector land
│       ├── U_FL_Hirose_U_FL_R_SMT_1_Vertical.kicad_mod  the kit's launch
│       ├── Chip_0402_RF_WideLand.kicad_mod     0402 pitch, 50 Ω-wide pads
│       ├── RF_Port_Land.kicad_mod                the same land, no connector
│       └── Chip_0402_1005Metric_RF.kicad_mod     spare 0402 land
├── kit/                             THE KIT: 6 boards, 3 antennas x 2 planes
│   ├── an043_ref/  an043_common/    2.45 GHz meandered inverted-F
│   ├── dn023_ref/  dn023_common/    868/915 MHz printed inverted-F
│   └── dn024_ref/  dn024_common/    868 + 2440 MHz meandering monopole
├── dn024/                           second antenna: TI DN024 monopole
│   └── dn024_monopole_868_2440.*    868 + 2440 MHz, edge-launch SMA
├── dn024_ti_form/                   the same antenna in the note's own form
│   └── dn024_monopole_ti_form.*     through-hole SMA inboard, ground opening
├── docs/
│   ├── board-drawing.svg            dimensioned drawing, generated from the PCB
│   ├── dn024-board-drawing.svg      the same, for the DN024 board
│   ├── dn024-ti-form-drawing.svg    the same, for the DN024 reference form
│   ├── dn024-sim-board-drawing.svg  the same, for the DN024 RFsim model
│   ├── sim-board-drawing.svg        the same, for the simulation board
│   └── antenna-integration-checklist.md   design review list for any project
├── sim/
│   ├── antenna_swra117d.lib         lumped antenna model (ngspice subckt)
│   ├── s11_antenna.cir              S11 / VSWR / Zin at the connector
│   ├── board/swra117d_2g4_sim.*     RFsim project: Figure 3, ground on layer 2
│   ├── board/dn024_monopole_sim.*   RFsim project: DN024, Z62 shorted, no pours
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

Two nets on the `RF_50R` net class (2.95 mm, 0.3 mm clearance): `RF_IN` from
the connector to the series position, `ANT_FEED` from there to the radiator.
Nothing *corrects* the antenna — SWRA117D says it is already a 50 Ω design and
publishes no values — but the pi network is laid out and linked with a 0 Ω, so
there is somewhere to compensate an enclosure later. See
[The pi network](#the-pi-network-pads-and-a-0-Ω-link) for what to do if the assembled
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

### The pi network: pads, and a 0 Ω link

Two TI documents, and they are not in conflict once you separate *values* from
*footprints*.

**SWRA117D on this antenna:** it is a 50 Ω design, and the note publishes no
matching BOM at all. So there is no value to fit, and inventing an L and a C
would be fitting copper to a guess — which this project did once, with an
0.8 nH that turned out to be fitted to its own model.

**AN058 section 3.4, as a general rule:** *"To avoid unnecessary mismatch
losses, it is recommended to add a pi-matching network so that the antenna can
always be matched. If the antenna design is adequately matched then it just
takes one zero ohm resistor or DC block cap to be inserted into the
pi-matching network."*

So the board carries the network, populated the way AN058 prescribes:

| | value | why |
|---|---|---|
| **Z2** | **0 Ω** | the link. The signal path is electrically what it was |
| **Z1** | not fitted | shunt, connector side |
| **Z3** | not fitted | shunt, antenna side |

Z1 and Z3 exist because AN058's own measurements show an enclosure only ever
pulls resonance *down*, and a board with nowhere to compensate that is a board
that gets respun. **A 100 pF is the drop-in alternative to the 0 Ω** where the
radio needs DC isolation — worth checking on this antenna in particular, since
its arm is a DC short to ground.

#### Why the pads are wider than an 0402

A 50 Ω microstrip on 1.6 mm FR4 is 2.95 mm wide; an 0402 land is 0.56 mm. The
two do not meet:

* **Butting the line onto an ordinary land does not work.** KiCad tracks have
  round caps, so a 2.95 mm track ending on a pad bulges 1.475 mm past its
  endpoint — straight across the opposite pad, which is 0.96 mm away. The
  checker caught exactly that, and KiCad's DRC would have too.
* **Necking the line down is worse than it looks.** 0.6 mm of track is ~100 Ω
  here, and the 6.5 mm it takes to taper down and back is **3.8 nH — j58 Ω at
  2.45 GHz**, in series with the antenna. That is a matching network nobody
  asked for.

So the series position uses `Chip_0402_RF_WideLand`: 0402 pitch, so the part
solders normally, but pads as wide as the line, which runs straight into them
with no step. The wide line still stops 2.0 mm short of the pad so its round
cap reaches 0.5 mm into its own pad and stays 0.7 mm clear of the other.

The two **shunt** positions keep the ordinary 0402 land, tapped by a 0.6 mm
stub off the side of the line. A short narrow stub into a shunt element is not
in the through path, so its inductance is part of what you tune with, not a
defect. Their ground pads reach the plane through a via of their own, because
the pour is cut away around the network — `PI_NETWORK_CLEARANCE`.

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
any routed feed, the matching parts' pads and the pour keep-away corridors all
come out of the `.kicad_pcb`, so the model cannot drift away from the layout.

Two details the pi network forced, and both are the kind of thing that fails
silently rather than loudly:

* **The feed is collected from every non-ground net**, not just the antenna's.
  A series part splits the path into two nets, and both halves are the same
  piece of RF path.
* **Track end caps are modelled.** KiCad tracks are round-capped, so copper
  reaches half a width past each endpoint — which is how the 50 Ω line reaches
  the series pad it deliberately stops short of. Model the tracks as bare
  rectangles and the feed quietly becomes three disconnected pieces that still
  produce a plausible answer. `--dry-run` now walks the modelled copper from
  the port and refuses to run if any of it is stranded. The KiCad
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
ground plane   : B.Cu, F.Cu, y = 0 .. 23.75 mm (antenna region 23.75 .. 30.0 mm is clear)
feed line      : 11 segments, 24.5 mm total, microstrip port launches along y from (24.00, 0.00) mm, feed pad at (24.00, 23.50) mm
                 ( 24.00,  0.00) -> ( 24.00, 12.00)  w = 2.95 mm
                 ( 24.00, 16.00) -> ( 24.00, 18.50)  w = 2.95 mm
                 ( 24.00, 10.50) -> ( 26.52, 10.50)  w = 0.6 mm
                 ( 24.00, 17.50) -> ( 26.52, 17.50)  w = 0.6 mm
                 ( 24.00, 18.50) -> ( 24.00, 19.25)  w = 2.746 mm
                 ( 24.00, 19.25) -> ( 24.00, 20.00)  w = 2.338 mm
                 ( 24.00, 20.00) -> ( 24.00, 20.75)  w = 1.929 mm
                 ( 24.00, 20.75) -> ( 24.00, 21.50)  w = 1.521 mm
                 ( 24.00, 21.50) -> ( 24.00, 22.25)  w = 1.113 mm
                 ( 24.00, 22.25) -> ( 24.00, 23.00)  w = 0.704 mm
                 ( 24.00, 23.00) -> ( 24.00, 23.50)  w = 0.5 mm
matching parts : 3 pad areas in the model (a fitted series link is modelled as metal across its two pads)
RF path        : 14 copper areas, all connected to the port
stitching vias : 43, 11 of them within 2 mm of the plane edge
top pour       : 15 boxes around 2 keep-away corridors
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
python3 tools/gen_rf_lands.py --width 2.95       # the 50 Ω-wide 0402 land
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
ok   library: 8 symbols, 6 footprints parse cleanly
ok   schematic: 6 embedded symbols all match library/SWRA117D_RF.kicad_sym (no lib_symbol_mismatch)
ok   schematic: 15 pins placed, 8 wires, netlist matches the intended one
ok   board: 12 pads, 13 tracks, 43 vias, clearances >= 0.15 mm, keep-out above y = 66.25 clean
ok   board: 28 antenna polygon vertices overlap the plane edge, all of them inside the antenna's own pads
ok   board: all 22 feed line ends sit over the B.Cu ground pour (reference plane present)
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
| **copper** | one layer | **both layers**, "this enables a lower resistive loss and gives a slightly wider bandwidth" — and stitched, see below |
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
| bandwidth | 73 MHz @ 868 (**820 – 893 MHz**), 354 MHz @ 2.4 GHz (**2386 – 2740 MHz**), both at SWR 2.0 | section 4.3.2 |
| efficiency | 94–95 %, gain 3.4–4.9 dBi | OTA summary, Table 4 |

One thing is inferred rather than stated: **which of Z61/Z63 sits on which
side of Z62.** Figure 2 draws Z63 above Z61 with the connector below both, and
the single band BOM — series 1.8 nH with a shunt 2.7 pF — is an L match that
only works with the shunt on the source side. Both readings put Z61 nearest
the connector, which is how it is laid out.

### Which radios this actually covers

The bands above are TI's measured −10 dB edges on the 43 × 63 mm plane, so the
question "does it do LoRa?" has an arithmetic answer rather than a marketing
one. **Dual band mode covers 820 – 893 MHz and 2386 – 2740 MHz.**

| radio / plan | band | dual band (`dn024/`, `dn024_ti_form/`) |
|---|---|---|
| **LoRaWAN EU868** | 863 – 870 MHz | **yes** — 43 MHz of margin below, 23 MHz above |
| LoRaWAN IN865 | 865 – 867 MHz | **yes** |
| LoRaWAN RU864 | 864 – 870 MHz | **yes** |
| Sigfox RC1, wM-Bus, generic 868 ISM | 868 MHz | **yes** |
| **LoRa 2.4 GHz** (SX128x) | 2400 – 2500 MHz | **yes** — the 2.4 GHz band is 354 MHz wide |
| BLE / 802.15.4 / Wi-Fi 2.4 | 2400 – 2483.5 MHz | **yes** |
| **LoRaWAN US915 / AU915** | 902 – 928 MHz | **no** — the band stops at 893 MHz |
| LoRaWAN AS923, KR920 | 920 – 923 MHz | **no** |
| LoRaWAN CN470 | 470 – 510 MHz | **no** — wrong antenna entirely |

For **915 or 920 MHz** the note says to use *single band* mode, with `L4`
*"shortened to the silkscreen marking"* — and dimensions that marking nowhere,
which is exactly the number this repo refuses to invent (see above). Single
band as built, with `L4` at its published 38.0 mm, measures 825 – 913 MHz:
that reaches the bottom 11 MHz of US915 and no further. So US915 is a real
re-tune, not a BOM change, and the honest answer is that the Gerber from the
CC-Antenna-DK is what settles it.

One thing to carry into the radio design if you use both bands at once, in
TI's own words: *"it is important to keep the 3rd harmonic of the 868 MHz
(2.604 GHz) underneath the regulatory limits since the 2.4 GHz antenna
(2.74 GHz to 2.38 GHz) will also radiate the 3rd harmonic as well."* The
antenna is efficient at 2.604 GHz by design, so it will happily radiate
whatever the sub-GHz PA leaves there. That is a filter problem at the radio,
not an antenna problem — but it is created by sharing one antenna across both
bands.

Measured efficiency, for the same reason of having numbers rather than
adjectives: **94.5 % at 868 MHz and 95.4 % at 2440 MHz**, gain 4.85 and
3.35 dBi (Table 4, full CTIA report in DN616).

### Two layers only count as one conductor if you stitch them

Section 3 puts the layout on both layers *"for lower resistive loss and
slightly wider bandwidth"*. Joining them at the feed alone does not deliver
that. Two identical traces 1.6 mm apart, shorted at one end and open at the
other, are a **150 mm parallel-plate line of about 140 Ω** — with resonances
of its own inside the band the antenna is supposed to work in.

So the radiator is stitched along its centre line at **2.8 mm**, which is
inside λ/20 in FR4 at 2.44 GHz (2.90 mm) — the same rule this repo uses for
ground stitching, applied to the top band of the dual-band build. 53 vias,
plus the plated feed hole.

**This is the one thing in the footprint that is not Table 1.** DN024 does not
dimension it and does not mention vias at all; the authoritative geometry is a
Gerber we do not have. The pitch is an engineering choice, and it is labelled
as one in the generator.

`check_dn024.py` holds it to the rule: every via inside the copper and clear
of the trace edge by its own radius, both layers reached, and the worst gap
under λ/20. Writing that check found three things — the feed pad being counted
as a stitch, a via landing exactly on the open tip with no copper around it,
and a first pitch of 3.0 mm that was over λ/20 while the comment next to it
claimed λ/19. The geometry was moved to meet the rule rather than the rule
relaxed to meet the geometry.

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
  53 vias tie the two layers together, no more than 2.80 mm apart

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
ok   library: TI_DN024 has 8 symbols and 1 footprints, all parsing cleanly
ok   schematic: 5 embedded symbols match their libraries, 13 pins on wires, netlist matches the intended one
ok   board: TI_DN024_Monopole_868_2440 matches all 7 dimensions of SWRA227E Table 1 within 11 um (exact copy), on B.Cu + F.Cu
ok   board: ground plane 43.0 x 63.0 mm on F.Cu and B.Cu, the size SWRA227E Table 3 measured the match on
ok   board: the radiator is on F.Cu and B.Cu, stitched by 53 vias no more than 2.80 mm apart (lambda/20 at 2.44 GHz is 2.90 mm), so the two layers are one conductor
ok   board: 64 pads, 14 tracks, 152 vias, every track end lands, keep-out above y = 91.0 clean, closest different-net tracks 0.36 mm
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

### The same antenna in the note's own form: `dn024_ti_form/`

`dn024/` uses an edge-mount SMA on the board edge, because that is the launch
the 2.45 GHz board in this repo already had and it keeps the two projects
comparable. SWRA227E's own Figure 2 does something different, and
`dn024_ti_form/dn024_monopole_ti_form.*` is that: **same antenna, same
43 × 63 mm ground plane, same Table 3 BOM**, different launch.

| | `dn024/` | `dn024_ti_form/` |
|---|---|---|
| connector | `SMA_EdgeMount_Generic`, edge mount | **`SMA_ThruHole_4Post`** — vertical jack, four ground posts on a 5.08 mm square |
| where | on the board edge, below the plane | **22 mm inboard**, with board on all four sides, as Figure 2 places P6 |
| top ground | solid, keep-away either side of the line | **cut away** in a tall chamfered opening around the feed and the network |
| bottom ground | solid | solid — unchanged, and it is what the line is referenced to |
| everything else | — | identical: radiator, plane, clearances, 2.95 mm feed, Z61/Z62/Z63 |

#### The connector is measured, not specified

SWRA227E names P6 and draws it, and gives no part number and no land pattern.
`tools/gen_sma_through_hole.py` therefore reads the plated barrels out of
Figure 2 at the figure's own scale — 7.86 px/mm, set by `X1` = 63 mm:

| | measured | used | why |
|---|---|---|---|
| post pitch | 5.15 mm in x, 5.06 mm in y | **5.08 mm** | 0.200" is the standard SMA flange square, and the reading lands on it from both axes independently — this number is certain |
| post drill | 1.21, 1.27, 1.21, 1.21 mm | **1.2 mm** | four readings of one feature, spread 0.06 mm |
| signal pin | 1.08 mm, centred to within a pixel | **1.1 mm** | |

That is about **±0.1 mm of reading error on a raster**, so the drills are a
starting point: *check them against the connector you actually buy before
ordering boards.* The generator's docstring says the same thing, so the
caveat travels with the file rather than living only here.

The bottom plane pulls back 0.5 mm around the signal pin. That clearance is
also a starting value, not a computed one — a coaxial launch through a plane
wants an anti-pad sized from the barrel diameter and the dielectric, which is
a tuning exercise on a real board and not something the note gives.

#### Why the top ground is cut away

The opening is the one feature of Figure 2 that could not be dimensioned:
it is a hatched raster fill with no dimension on it, read at about 11–12 mm
wide with chamfered corners. So it is **not** copied by eye — it is sized from
what it is for, and the figure only sets its shape:

* no top ground beside the 50 Ω line, so the line is a plain microstrip
  referenced to the bottom plane and its 2.95 mm width means 50 Ω;
* no top ground beside the pi network, whose lands are wider than an 0402 for
  the same reason;
* 11.5 mm wide, which puts the pour further from the line than the keep-away
  that keeps it 50 Ω, so the width is a consequence of the rule rather than of
  the reading.

It is an F.Cu-only keep-out named `PI_NETWORK_CLEARANCE`, chamfered 2.0 mm at
the corners, reaching from the plane edge down past the connector.

#### A 2.95 mm line does not fit between ground posts 5.08 mm apart

This is the one thing the new form broke, and it is worth writing down because
it is a trap on any through-hole SMA, not a quirk of this board.

A 50 Ω microstrip on 1.6 mm FR4 is **2.95 mm** wide. The posts are 5.08 mm
apart with 1.9 mm pads. Half the pitch, less half the line, less half a pad:

```
2.54 − 1.475 − 0.95 = 0.115 mm
```

— under the 0.15 mm rule, and the first draft of this board had exactly that. So
the line **necks down for the last 4 mm**: 2.5 mm of taper in five steps from
2.95 mm to 1.0 mm, then 1.5 mm of 1.0 mm line into the pin. That leaves
1.09 mm to each post, and a launch transition is what a vertical connector
wants anyway.

The cost is small and computed rather than asserted — `line_impedance.py` puts
1.0 mm at **84.5 Ω**, and against a 50 Ω line of the same 4.0 mm the whole
transition adds **j2.6 Ω at 868 MHz and j6.5 Ω at 2.44 GHz**, about 0.45 nH
either way. That is inside what Z61/Z62/Z63 exist to absorb.

`check_dn024.py` gained a **track-to-pad clearance rule** for this, since
nothing was looking: copper of one net against pads of another, not just track
against track. It was verified by mutation — removing the neck makes it fail
with the 0.115 mm above — and it now runs over both DN024 boards, which is why
the checker output below has two blocks.

#### Running it

```sh
python3 tools/gen_sma_through_hole.py     # the P6 land, from Figure 2
python3 tools/gen_dn024_ti_project.py     # schematic + board + project
python3 tools/check_dn024.py              # both DN024 projects
```

```
--- dn024_ti_form/dn024_monopole_ti_form.kicad_pcb
ok   library: TI_DN024 has 8 symbols and 2 footprints, all parsing cleanly
ok   schematic: 5 embedded symbols match their libraries, 13 pins on wires, netlist matches the intended one
ok   board: TI_DN024_Monopole_868_2440 matches all 7 dimensions of SWRA227E Table 1 within 11 um (exact copy), on B.Cu + F.Cu
ok   board: ground plane 43.0 x 63.0 mm on F.Cu and B.Cu, the size SWRA227E Table 3 measured the match on
ok   board: the radiator is on F.Cu and B.Cu, stitched by 53 vias no more than 2.80 mm apart (lambda/20 at 2.44 GHz is 2.90 mm), so the two layers are one conductor
ok   board: 65 pads, 20 tracks, 158 vias, every track end lands, keep-out above y = 91.0 clean, closest different-net tracks 0.36 mm, closest track to a foreign pad 0.35 mm
ok   pi network: Z62 series between RF_IN and ANT_FEED, Z61 shunt on the connector side, Z63 shunt on the antenna side; Z61 and Z63 laid out and unfitted, as Table 3 says
ok   pi network: both shunt ground pads reach the bottom plane through a via of their own
ok   board: 2 copper zone(s) carry no fill yet - press B in the PCB editor before DRC or any simulation

0 problem(s) across 2 project(s)
```

[`docs/dn024-ti-form-drawing.svg`](docs/dn024-ti-form-drawing.svg) is the
drawing.

**Which one to build.** The through-hole form is the one to compare against
the note's measurements, because it is the note's own layout and an inboard
connector loads the ground plane the way the reference does. The edge-launch
form is easier to fixture and keeps the connector body out of the antenna's
half-space. They share every dimension that sets the resonance, so the antenna
is the same antenna either way.

### Simulating it: `sim/board/dn024_monopole_sim.*`

Handing either fabrication board straight to a field solver produces a
confident, detailed, entirely wrong S11. Two reasons, neither of them about
the antenna, and both invisible in the PCB editor:

**1. KiCad stores zones unfilled.** A `.kicad_pcb` written by a script has
zone *outlines* and no `filled_polygon` at all until somebody presses **B**
and saves. A solver reads the file. For a microstrip that costs you the
reference; for a **monopole it is fatal**, because the plane is the other half
of the antenna — there is nothing to resonate against, and what comes back is
the feed line talking to itself.

**2. A field solver meshes copper, and Z62 is a 3.9 pF capacitor.** On the
fabrication board Z62 is an 0402 land: two pads with a **0.40 mm gap** between
them. The solver sees the gap, not the part that will be soldered across it —
a fraction of a picofarad where 3.9 pF belongs:

| | at 868 MHz | at 2.44 GHz |
|---|---|---|
| 3.9 pF, the real part | −j47 Ω | −j17 Ω |
| ~30 fF, a 0.40 mm gap | **−j6100 Ω** | **−j2200 Ω** |

−j6100 Ω is an open circuit. The antenna is **not connected to the port**, and
S11 sits at 0 dB across the sub-GHz band with the port looking into a stub.
That is not a bad match, it is no circuit.

So `tools/gen_dn024_sim_board.py` builds a third DN024 project that removes
both, and nothing else:

* **No zones at all.** The ground plane is *pads* — 43 × 63 mm solid on B.Cu,
  and the same plane on F.Cu minus the opening around the feed. Pads are solid
  copper in the file, so there is no fill step to forget and nothing that
  looks like a plane but is not one.
* **Z62 is a copper bridge.** One continuous `ANT_FEED` net from the port pad
  to the antenna.
* **No connector.** `P1` is a port land the width of the 50 Ω line, with the
  B.Cu plane directly underneath as its reference — RFsim attaches ports to
  pads and needs reference copper under the one it drives.
* Geometry is otherwise `dn024_ti_form` verbatim, imported rather than copied.

#### The point of shorting Z62 is that it gives you a number to check against

This is not a workaround, it is the configuration TI measured. SWRA227E 4.3.1:

> *"With no antenna match components (Z62: 0 ohm), at 868 MHz the match is poor
> with SWR 2.9 and excellent at 2.44 GHz with SWR 1.2."*

So a correct run of this board must land near:

| | SWR | S11 |
|---|---|---|
| **868 MHz** | 2.9 | **−6.2 dB** |
| **2440 MHz** | 1.2 | **−20.8 dB** |

**Not** Figure 13's matched −10 dB bands. Those include the 3.9 pF, and no
copper-only model can produce them — add the capacitor in a circuit simulator
afterwards, on top of the Zin this run gives you. A full-wave result you
cannot check against a measured number is not a result, and this is the only
DN024 number in the note that a copper-only model is entitled to reproduce.

The expectation is printed by the generator, written on the board's
`User.Comments` layer, put in the schematic note, and asserted by the checker,
so it is in front of you at the moment you read the plot.

#### Running it

```sh
python3 tools/gen_dn024_sim_board.py
python3 tools/check_dn024_sim.py
```

```
ok   board: no copper pours, so there is no fill step to forget - the ground plane is pads, which are solid copper in the file
ok   board: ground plane 43.0 x 63.0 mm as 1 B.Cu pad(s) (2709 mm2) and 3 F.Cu pad(s), the size SWRA227E Table 3 measured the match on
ok   board: port pad 2.95 x 2.0 mm at (122.5, 113.0) with solid B.Cu directly under it - attach RFsim port 1 here, as MSL
ok   board: one continuous ANT_FEED run of 11 tracks from the port pad to the antenna, with copper where the fabrication board puts Z62 - this is SWRA227E 4.3.1's 'Z62: 0 ohm' case
ok   board: closest ground copper to a signal track 0.38 mm (Z61.2 vs a ANT_FEED track)
ok   expect:    868 MHz  SWR 2.9  ->  S11 =  -6.2 dB  (SWRA227E 4.3.1, measured with Z62 = 0 ohm)
ok   expect:   2440 MHz  SWR 1.2  ->  S11 = -20.8 dB  (SWRA227E 4.3.1, measured with Z62 = 0 ohm)
ok   expect: NOT Figure 13's matched bands - those include the 3.9 pF, and no copper-only model can produce them

0 problem(s)
```

The checker was mutation-tested against the obvious mutant — the fabrication
board itself, which has both faults — and reports all four:

```
FAIL board: 2 copper pour(s) - this board must carry none. KiCad writes zones unfilled, a solver reads the file, and an unfilled pour is not a ground plane
FAIL board: no solid B.Cu ground copper - a monopole radiates against its plane, and without one there is nothing to resonate
FAIL board: expected exactly one P1 pad 1 to drive, found 0
FAIL board: an RF_IN net exists, so the feed is still split by a series matching land. A solver meshes copper: that land is a 0.40 mm gap, not 3.9 pF, and the antenna is left unconnected
```

#### Sweep and domain

Sub-GHz costs domain, and the rule is a quarter wavelength of free space at
the **lowest frequency you sweep**, not at the band of interest:

| sweep starts at | λ/4 margin the domain needs |
|---|---|
| 868 MHz | 86 mm |
| 0.6 GHz | 125 mm |
| 0.5 GHz | **150 mm** |

Starting at 0.5 GHz costs about 1.7× the domain volume of starting at 0.6 GHz
and tells you nothing — there is no band there. Start at 0.6 GHz.

[`docs/dn024-sim-board-drawing.svg`](docs/dn024-sim-board-drawing.svg) is the
drawing.

## The evaluation kit: three antennas, two ground planes

`kit/` is six boards. Three antennas, each built twice.

| | antenna | size | band | note |
|---|---|---|---|---|
| **AN043** | meandered inverted-F | 15 × 6 mm | 2.45 GHz | SWRA117D |
| **DN023** | printed inverted-F | 43 × 20 mm | 868 / 915 / 955 MHz | SWRA228C |
| **DN024** | meandering monopole | 38 × 25 mm | 868 + 2440 MHz | SWRA227E |

These three because AN058 Tables 9 and 10 — TI's own catalogue of reference
antennas — list a dozen, and these are the three whose application note is in
hand. Every one of them is an exact copy of a published dimension table,
checked by its own `verify_against_*` script. The rest of the catalogue needs
the note: `ti.com` is not reachable from this container, so the kit grows by
adding a PDF, not by drawing from memory.

### Why each antenna is built twice

**A PCB antenna is not a component.** The ground plane is part of the antenna,
so which plane you put it on decides what you measure. One board per antenna
cannot answer both of the questions you actually have, so each antenna gets
two:

| | plane | what it is for |
|---|---|---|
| `*_ref` | the plane the note publishes | reproduces the note's own numbers, so the measurement **validates the build** |
| `*_common` | **45 × 60 mm, shared by all three** | the three boards become **comparable with each other** — which is the question a customer asks |

The reference boards cannot be compared with each other, because they differ
in the one thing that matters most. The common boards do not reproduce
anybody's published numbers, and that is the point: on the common plane none
of these is the antenna its note measured, and the difference between the two
boards of a pair *is the ground plane sensitivity* — which is the single
most useful number to hand a customer whose enclosure is not yet fixed.

One honest exception, marked on the board and in the schematic note: **AN043
publishes no ground plane size at all.** SWRA117D only says plane size affects
performance. Its "reference" plane is this repo's own 40 × 23.75 mm, not TI's.

### Six separate boards, not one board with six antennas

Putting several antennas on one PCB would answer neither question: they would
share a plane and couple to each other. TI's own CC-Antenna-DK is a set of
separate boards for the same reason. The three common-plane boards share one
55 × 90 mm outline, so they panelise into one fabrication order and drop into
one fixture.

Everything that is not the antenna or the plane is held constant on purpose —
1.6 mm FR4, the same U.FL launch, the same 2.95 mm 50 Ω microstrip, the
same three matching sites at the feed. `check_kit.py` asserts that, because a
kit whose variables leak is not a kit:

```
ok   all 6 boards: one connector (SWRA117D_RF:U_FL_Hirose_U_FL_R_SMT_1_Vertical), one stackup (1.69 mm), one 50 ohm width (2.95 mm) - only the antenna and the plane are variables
ok   the 3 common-plane boards share one 55 x 90 mm outline and one 45 x 60 mm plane, so only the antenna differs
```

### The launch is a U.FL and a pigtail, not an SMA on the board edge

**The cable is the measurement problem, not the connector.** On a 45 × 60 mm
plane at 868 MHz — λ = 345 mm — the plane and whatever cable leaves it are one
conductor as far as common-mode current is concerned. The braid becomes part
of the antenna, and that shows up as an S11 null that *moves when you move the
cable*. Move the cable, sweep twice: if the null walks, you are measuring the
cable.

Nothing about the connector fixes that. What a U.FL does is let you fix it:

* the bulkhead SMA stays on the **jig**, so the connector body and its ground
  tabs are no longer copper sitting in the near field of a plane that is half
  the antenna;
* the pigtail is somewhere to put a **ferrite or a sleeve balun**, which is the
  only real cure;
* and it is what an actual IoT product carries, so the board under test is
  closer to the thing being designed.

The land pattern is Hirose's own, for the **U.FL-R-SMT-1(10)** — signal pad
1.05 × 1.00 mm, two ground pads 2.20 × 1.05 mm — taken from KiCad's
`Connector_Coaxial` library, which cites [Hirose's page for the
part](https://www.hirose.com/product/en/products/U.FL/U.FL-R-SMT-1%2810%29/).
It is regenerated from those dimensions rather than the file being copied, so
the provenance sits next to the geometry.

**A 1.05 mm pad will not take a 2.95 mm line** — the same trap the through-hole
SMA sprang with its ground posts. The line tapers 2.95 → 1.0 mm over 2.5 mm and
runs 1.5 mm into the pad. And the taper lands somewhere better than it did
there: the pour keep-away stops *above* the connector so the pour can close
around J1's ground pads, which turns the neck into a grounded coplanar line
rather than a microstrip —

| 1.0 mm neck | Z₀ |
|---|---|
| as microstrip, pour kept back | 84.5 Ω |
| **as CPWG, pour 0.2 mm away** | **53.9 Ω** |

— so the neck is near 50 Ω by construction instead of being a lump to absorb.
That is what a U.FL launch is supposed to look like.

Three rules exist for the launch alone, because **the general rules do not
cover it**: a track and the pad it runs to are the same net, so the clearance
check skips the pair, and a 2.95 mm line driven straight onto a 1.05 mm pad
reads as clean. `check_kit.py` additionally requires that the launch *lands on
the signal pad* (not on the footprint origin, which is 1.05 mm past it — a
mistake this generator made and the checker caught), that it is no wider than
the pad, that both ground pads sit on the pour rather than inside the keep-away
corridor, and that each has a stitching via within 3 mm.

One consequence worth naming: **AN043's reference plane grew from 23.75 mm to
28.0 mm.** The kit's standard feed — network, taper, a real run of 50 Ω line,
launch — needs 27.05 mm, and `gen_kit.py` refuses to build a board with less
rather than quietly shortening the line. SWRA117D publishes no plane size at
all, so that number was always this repo's to choose; it may as well be one the
standard feed fits in. Every other plane is the note's and is untouched.

### The boards

| board | outline | plane | antenna | 50 Ω run | drawing |
|---|---|---|---|---|---|
| `an043_ref` | 50 × 37.1 | 40 × 28 † | 14.4 × 5.4 | 3.95 mm | [svg](docs/kit/an043_ref.svg) |
| `an043_common` | 55 × 90 | 45 × 60 | 14.4 × 5.4 | 35.95 mm | [svg](docs/kit/an043_common.svg) |
| `dn023_ref` | 53 × 69 | 31 × 45 | 43 × 20 | 20.95 mm | [svg](docs/kit/dn023_ref.svg) |
| `dn023_common` | 55 × 90 | 45 × 60 | 43 × 20 | 35.95 mm | [svg](docs/kit/dn023_common.svg) |
| `dn024_ref` | 53 × 91 | 43 × 63 | 38 × 25 | 38.95 mm | [svg](docs/kit/dn024_ref.svg) |
| `dn024_common` | 55 × 90 | 45 × 60 | 38 × 25 | 35.95 mm | [svg](docs/kit/dn024_common.svg) |

† this repo's choice; SWRA117D publishes none.

Matching, per antenna, with nothing invented:

| | Z1 | Z2 | Z3 | why |
|---|---|---|---|---|
| AN043 | NF | **0 Ω link** | NF | the note publishes no values; AN058 asks for the pads |
| DN023 | NF | **0 Ω link** | NF | *"approximately matched to 50 ohm, no external matching components are needed… has included the option for one series and two shunt components"* |
| DN024 | NF | **3.9 pF** | NF | SWRA227E Table 3, dual band — the only one of the three with published values |

### Almost nothing on these boards is written down twice

The outline, the plane, where the antenna sits, where the connector goes and
where the schematic symbol is placed are all **derived** at generation time
from the footprints and symbols themselves. That is what keeps six boards
consistent — and it is also why they need checking, because a derivation that
is wrong is wrong six times.

The three antennas put their footprint origin in three different places, and
nothing in the generator may assume which:

| | origin relative to the plane edge | why |
|---|---|---|
| AN043 | **0.25 mm below** | the feed pad straddles the edge and the W1 strap's via lands in the plane behind it |
| DN023 | **on it** | SWRA228C measures `L1` = 20.0 mm *to* the plane edge, and the shorting leg merges into the plane there |
| DN024 | **1.0 mm above** | Table 1's `L5` is clear board between antenna and plane |

Writing the checker found three real faults, all of which look fine on screen:

* **DN023's shorting leg was shorted to nothing.** It is an SMD pad sitting
  exactly *on* the plane edge — and both pours stop at that line, so there was
  no copper for it to reach. It now runs 1.5 mm into the plane and vias down
  to B.Cu. An inverted-F with an open short is not a badly matched antenna, it
  is a different antenna.
* **The wide 0402 land was being turned the wrong way.** `Chip_0402_RF_WideLand`
  is drawn for a part lying *along* the line, and a series part stands *across*
  it, so at 90° its wide pads pointed the wrong way and sat 1.1 mm inside the
  neighbouring track. The kit uses the ordinary 0402 behind the taper, which is
  what the DN024 board already did.
* **The checker's own pad model was wrong.** Treating a pad as a circle of its
  longest half-dimension reads a track passing the short way as driving
  straight through it. Replaced with the exact rectangle distance — which is
  how the first fault above got found in the first place.

### Running it

```sh
python3 tools/gen_dn023_symbols.py      # library/TI_DN023.kicad_sym
python3 tools/gen_dn023_footprint.py    # the third antenna, from Table 1
python3 tools/verify_against_swra228c.py
python3 tools/gen_ufl_footprint.py      # the U.FL land, from Hirose's pattern
python3 tools/gen_kit.py                # all six boards
python3 tools/check_kit.py
python3 tools/mutate_kit.py             # does the checker actually bite?
```

```
0 problem(s) across 6 board(s)
11/11 mutations caught
```

The mutations are the mistakes that are easy to make here and invisible in the
editor: the antenna off centre, the board too narrow for the 5 mm either side
SWRA228C asks for, the shorting leg not reaching the plane, Z2 wired as a shunt
instead of in series, one common board quietly given a different plane, AE1
placed so its feed pin misses the bus, the antenna pushed down over the plane
edge, a ground pour going missing from the bottom layer, the 50 Ω line butting
straight onto the U.FL's 1.05 mm pad, the launch stopping at the connector's
origin instead of its signal pad, and the pour keep-away running past the U.FL
so its ground pads are stranded.

Two of those are caught by a rule written for them and one — the launch
stopping short — by the general "every track end lands on something", which is
worth saying rather than claiming three new rules were each proved.

### What to measure, and in what order

0. **Choke the cable first, then prove it.** Ferrite on the pigtail, sweep,
   move the cable, sweep again. If the null moves, the number is the cable's,
   not the antenna's — and every comparison below is then meaningless.
1. **Each `*_ref` board against its note.** DN024: SWR 1.2 at 868 and 1.6 at
   2.44 GHz (SWRA227E 4.3). DN023: reflection better than −25 dB once `L6` is
   trimmed. If a reference board does not reproduce its note, the build is
   wrong and nothing downstream means anything.
2. **Then the three `*_common` boards against each other.** Same plane, same
   launch, same stackup — so the difference is the antenna, and the comparison
   is honest.
3. **Then each pair against itself.** `ref` versus `common` for one antenna is
   that antenna's ground-plane sensitivity, measured rather than asserted.

### DN023's L6 is a trim, and the note gives it three values

SWRA228C tunes this antenna by cutting copper off, not by matching — and it
dimensions the cut three different ways:

| | `L6` | where |
|---|---|---|
| as drawn | **17.0 mm** | Table 1 |
| 868 MHz | 9 mm | section 3.1 text |
| 868 MHz | **11 mm** | Figure 12 caption, the measured plot |
| 915 MHz | 1 mm | section 3.1 text |
| 915 MHz | **3 mm** | Figure 13 caption, the measured plot |

The revision history says *"SWRA228C — Updated values in Table 1"*, so Table 1
moved at least once. The two captions sit exactly 2 mm — one `W2` — above the
text, which reads like two datums rather than one of them being wrong.

Nothing here picks between them. The board is built at Table 1's 17.0 mm,
which is the longest and therefore the only one you can still cut back from,
and the two **measured** lengths are marked on the silkscreen as a trim scale
next to the stub. `tools/gen_dn023_footprint.py --l6 11.0` builds any of them
if you would rather etch it than cut it.

## Fabrication: one panel, one order

The three `*_common` boards were given one 55 × 90 mm outline on purpose, so
they panelise. `kit/panel_common/` is the three of them butted in a row —
**165 × 90 mm, two V-score lines** — which means one order, one stackup and
one piece of laminate. For three boards whose entire purpose is being compared
with each other, that removes the last variable between them.

```
A  dn023_common    868 / 915 MHz printed inverted-F
B  dn024_common    868 + 2440 MHz meandering monopole
C  an043_common    2.45 GHz meandered inverted-F
```

[`docs/kit/kit_panel_common.svg`](docs/kit/kit_panel_common.svg) is the panel.

### A merge goes wrong quietly

`gen_panel.py` is not a copy-and-paste. Four things have to be rewritten, and
none of them is visible at a glance:

* **References become `A…`, `B…`, `C…`** — three boards each carrying `J1`
  make the pick-and-place file ambiguous, and nobody can tell which board a
  part belongs to.
* **Nets are renumbered and renamed per board.** Three `GND`s merged into one
  net tells DRC that three separate boards are connected. The zone's
  `net_name` is rewritten along with its number, because **KiCad believes the
  name**, so renumbering one without the other reattaches a zone to another
  board's net.
* **Every uuid is re-keyed**, since three copies of one board otherwise carry
  three copies of every identifier.
* **The boards' own `Edge.Cuts` are dropped** and become V-score lines on
  `User.Comments`. A fab reads `Edge.Cuts` as *route this* and would cut the
  panel into three before shipping it.

`check_panel.py` checks all of it against the source boards, and found two
real faults the moment it was written:

**`sexpr.find_all` searches direct children only.** Every uuid in a board is
nested inside a footprint or a track, so asking for them at the top level
returned an empty list — and an empty list has no duplicates. The check had
been passing while testing nothing. Fixed by adding `find_deep()` to the
parser, which two other files had each been working around with a private
copy.

**With that fixed it reported 28 duplicated uuids — and the fault was not in
the panel.** `gen_project.board_footprint` deep-copies a library footprint
including its uuids, so the three 0402 sites placed from one file carried
three copies of each. **Every board in the repository had it.** Fixed at the
source, and `check_kit.py` now has a uuid rule so it cannot come back.

### The export refuses to hand a fab house an empty ground plane

This is the same trap that made a full-wave run meaningless earlier in this
project, except that this time you pay for it. **KiCad stores zones
unfilled**, every board here is written by a script, and `kicad-cli pcb export
gerbers` does not warn you — it hands you a board with no copper pour at all.

So `make_fab.py` fills the zones with **KiCad's own filler** (`pcbnew`, the
only thing entitled to do it — an approximation written here would be copper
that disagrees with KiCad's DRC), then **refuses to export** if no
`filled_polygon` appears afterwards, then refuses again if any exported file
comes out empty. Without KiCad installed it says so and stops, rather than
producing something plausible and wrong.

```sh
python3 tools/gen_panel.py
python3 tools/check_panel.py
python3 tools/gen_bom.py
python3 tools/make_fab.py          # needs KiCad 9; CI does this for you
```

**Order as:** 2 layer, **1.6 mm FR4**, 1 oz copper, HASL or ENIG, **V-score on
the two marked lines** (`User.Comments`). The 5 mm of bare laminate either side
of each ground plane is checked against the scoring lines by `check_panel.py`.

### The BOM is six parts

Read out of the board files rather than the generator's tables, so it says
what is actually on the board. Unfitted sites stay visible *as* unfitted —
hiding them would hide the whole reason they are there.

| qty | value | where | part |
|---|---|---|---|
| 3 | U.FL receptacle | `AJ1 BJ1 CJ1` | Hirose U.FL-R-SMT-1(10) |
| 2 | 0 Ω link | `AZ2 CZ2` | any 0402 — no matching values are published for those two antennas |
| 1 | 3.9 pF | `BZ2` | Murata GRM1555C1H3R9CZ01D — SWRA227E Table 3 |
| 6 | not fitted | `AZ1 AZ3 …` | lands for compensating an enclosure later |

Not on the board but needed to measure: **3 × U.FL-to-SMA bulkhead pigtail**
(≤ 300 mm) and **3 × clamp ferrite** for them. The ferrite is not optional —
see the launch section above.

### CI builds the fabrication files

[`.github/workflows/pcb.yml`](../.github/workflows/pcb.yml) regenerates every
library, footprint, board and panel, then requires `git diff --exit-code`: **a
generated file edited by hand fails the build.** Then it verifies the three
antennas against their published tables, runs six checkers, runs both mutation
suites, and checks that every drawing matches its board. A second job installs
KiCad, rebuilds the panel, exports and uploads the gerbers, drill, position
file and BOM as a build artifact.

Only that second job needs KiCad. Everything else is pure Python with no
dependencies, on purpose — so the checks run anywhere, including on a machine
that has never had KiCad installed.

## Reusing this on someone else's board

[`docs/antenna-integration-checklist.md`](docs/antenna-integration-checklist.md)
is the checklist these projects produced: 85 items across antenna placement,
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
