# 2.45 GHz PCB antenna (TI SWRA117D) — KiCad symbol, schematic, board and RF simulation

A complete, self-contained KiCad project built around the TI SWRA117D
**2.4 GHz printed inverted-F antenna** (left-hand layout): the radiator fed
straight from a 50 Ω SMA port, with no matching network in the path. Plus a
second, simulation-only board carrying the antenna and nothing else, and two
simulation flows — a lumped **ngspice** return-loss testbench and a full-wave
**openEMS** model that reads its geometry out of whichever board file you
point it at.

```
kicad/
├── swra117d_2g4_antenna.kicad_pro   project (net classes, design rules)
├── swra117d_2g4_antenna.kicad_sch   schematic: SMA → 50 Ω line → antenna
├── swra117d_2g4_antenna.kicad_pcb   2 layer, 40 × 30 mm, 1.6 mm FR4
├── sym-lib-table / fp-lib-table     point KiCad at the project libraries
├── library/
│   ├── SWRA117D_RF.kicad_sym        antenna, SMA, GND, PWR_FLAG (+ C, L spare)
│   └── SWRA117D_RF.pretty/
│       ├── Texas_SWRA117D_2.4GHz_Left.kicad_mod   antenna, as published
│       ├── SWRA117D_2G4_Left_retuned.kicad_mod     antenna, scaled x1.155
│       ├── SMA_EdgeMount_Generic.kicad_mod        50 Ω test port
│       └── Chip_0402_1005Metric_RF.kicad_mod      spare 0402 land
├── docs/
│   ├── board-drawing.svg            dimensioned drawing, generated from the PCB
│   ├── sim-board-drawing.svg        the same, for the simulation board
│   └── antenna-integration-checklist.md   design review list for any project
├── sim/
│   ├── antenna_swra117d.lib         lumped antenna model (ngspice subckt)
│   ├── s11_antenna.cir              S11 / VSWR / Zin at the connector
│   ├── board/swra117d_2g4_sim.*     the antenna alone, direct port — see below
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
| **domain margin** | **≥ 31 mm** (λ/4 at 2.45 GHz) | At the 4 mm default the absorbing boundary sits inside the antenna's near field — λ/31 away — so it truncates the fields that make the antenna an antenna. `sim/openems/swra117d_openems.py` uses 30 mm for the same reason. |
| **port** | attached to the feed line, **Coplanar (CPW)** at the launch — or, on the simulation board below, the direct port with no line at all | The dialog showed *Port 1 [No Track]*, *Feed: No Line*, Lumped, width 3.114 mm. The width was never the problem: 3.11 mm is the 50 Ω width for this stackup with copper thickness ignored, and the board's 2.95 mm is the same width with it. *No Track* and *No Line* were the problem — a lumped port that is not attached to anything excites nothing. |

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

Three full-wave runs so far. The frequency a run reports is only as good as
the setup behind it, so the setup is recorded with it:

| run | ground plane | substrate | domain | resonance |
|---|---|---|---|---|
| 1 | **absent** (pours unfilled) | 1.6 mm (preset) | **4 mm** | 2.83 GHz |
| 2 | present | 1.6 mm (mid-plane caption read 0.80 mm) | **4 mm** | 2.02 GHz |
| 3 | to confirm | to confirm | to confirm | 2.82 GHz, VSWR 1.2 |
| 4 | present | 1.6 mm (mid-plane caption again read 0.80 mm) | **4 mm**, bright field on the boundary | 2.65 GHz |

The substrate column is no longer bolded as a fault: the board owner has since
confirmed 1.6 mm, so the simulator's preset was right and this project's
0.8 mm assumption was the error. What remains wrong in every one of these runs
is the 4 mm domain, and in run 1 the missing ground plane.

Four runs on a board whose copper has not meaningfully changed, spanning
**2.02 – 2.83 GHz: 810 MHz, or 33% of the target frequency.** No geometry
moved by 33%. That spread is the measurement, not the antenna — and it is the
strongest argument for fixing the setup before reading another number off a
plot. A converged model gives the same answer twice; this one has not given
the same answer twice yet.

Runs 1 and 3 agree, and that agreement means nothing on its own: run 1 had no
ground plane at all, which is a different antenna, and it landed on the same
number as a run that had one. Two setups this different agreeing is a
coincidence, not a convergence. Only the setup behind run 3 can make its
number usable.

**The gate before retuning.** Applying a scale factor is a two-line change, so
the cost is not in the edit — it is in scaling on a bad measurement, which has
already happened once here. Confirm all four before flipping it:

1. copper pours filled in the exported geometry,
2. substrate 1.6 mm, εr 4.5 (check the field-plot mid-plane caption reads
   0.80 mm),
3. domain margin ≥ 31 mm (check the field plot extends ~31 mm past the copper
   and is dark at the boundary),
4. port attached to the feed line, coplanar at the launch.

With run 3 confirmed, k = 2.82 / 2.45 = **1.151** — within 0.3% of the x1.155
copy already in the library, which is inside the first-order accuracy of the
method, so no regeneration is needed. Set `ANT_SCALE = 1.155` and
`ANT_FOOTPRINT = "SWRA117D_2G4_Left_retuned"` in `tools/gen_project.py`,
regenerate, and expect resonance near 2.45 GHz.

One encouraging detail from run 3 independent of its frequency: VSWR at the
null is about 1.2, so the antenna is genuinely matched at whatever frequency
it resonates. The feed tap sits in the right place relative to the short, and
uniform scaling preserves that ratio — so the match should survive the retune.

`SWRA117D_2G4_Left_retuned.kicad_mod` is still in the library at x1.155 as an
example; the board is back on the published geometry. `ANT_ORIGIN` stays at
66.5 mm — 0.9 mm of board beyond the antenna's keep-out box, which is routing
margin, and the ground plane edge follows the footprint automatically either
way.

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
        --board sim/board/swra117d_2g4_sim.kicad_pcb   # the antenna alone
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

and on the simulation board, where there is no line to report:

```
board file     : swra117d_2g4_sim.kicad_pcb
board          : 40.0 x 30.0 mm, 1.6 mm FR4 (er 4.5, tan d 0.02)
ground plane   : y = 0 .. 23.75 mm (antenna region 23.75 .. 30.0 mm is clear)
feed           : direct - no line.  Lumped port, 50 ohm, 0.50 mm wide x 0.40 mm gap at (24.00, 23.05) mm
stitching vias : 48, 16 of them within 2 mm of the plane edge
top pour       : 5 boxes around 1 keep-away corridors
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
(On the simulation board there is no launch and no line — see
[The simulation board](#the-simulation-board-the-antenna-and-nothing-else).)

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
python3 tools/gen_sim_board.py       # rebuild the simulation board
python3 tools/check_sim_board.py     # check it: no connector, no line, real ground
python3 tools/mutate_sim_board.py    # prove those checks actually fail when they should
python3 tools/verify_against_swra117d.py   # the footprint against Table 1, dimension by dimension
python3 tools/line_impedance.py      # microstrip and CPWG impedance, read from the board
python3 tools/stitching_span.py      # largest patch of pour with no via in it
python3 tools/gen_sma_footprint.py   # regenerate the SMA land for the stackup
python3 tools/scale_footprint.py     # retune the antenna by uniform scaling
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

`check_sim_board.py` does the same job for the simulation board, asking a
different question: is what the solver sees actually the antenna alone? See
[The simulation board](#the-simulation-board-the-antenna-and-nothing-else).

```
ok   library: 6 symbols, 4 footprints parse cleanly
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

## The simulation board: the antenna and nothing else

`sim/board/swra117d_2g4_sim.kicad_pcb` is a second board, and it exists
because of a question the fabrication board cannot answer cleanly: *what does
this antenna do?*

Simulate `swra117d_2g4_antenna.kicad_pcb` and the answer includes 23.5 mm of
microstrip, a six-step taper and an end-launch footprint. That is the right
answer to *what will the VNA read on the connector* — it is the board that
gets built — but it is not the antenna's own S11, and when the number comes
out wrong there is no way to tell which of the four things moved it.

So the simulation board is SWRA117D Figure 3 and Table 1, and nothing else:

| | fabrication board | simulation board |
|---|---|---|
| antenna | `Texas_SWRA117D_2.4GHz_Left`, exact Table 1 copy | **the same file**, unchanged |
| substrate | 1.6 mm FR4, εr 4.5 | the same |
| outline, ground plane, plane edge | 40 × 30 mm, plane from y = 66.25 | the same, so the two are comparable |
| connector | `SMA_EdgeMount_Generic` | **none** |
| feed | 23.5 mm of 50 Ω microstrip + taper | **none** — the port is at the antenna |
| port | microstrip / CPW at the board edge | **lumped, 50 Ω, in the 0.4 mm gap at the feed pad** |
| stitching | 41 vias | 48, including 5 within 2 mm of the port |
| schematic | yes | no — there is nothing to schematise |

Everything the two boards share is shared by construction:
`tools/gen_sim_board.py` imports `tools/gen_project.py` and reads the outline,
the stackup, the plane edge and the antenna footprint from it, so the only
differences are the ones in that table.

### The port is a gap, and the gap has two jobs

The direct feed is the gap between the radiator's bottom bar and the ground
pour, held open by an F.Cu keep-out called `RF_PORT_GAP`. A keep-out rather
than KiCad's pour clearance, because the pour clearance is a design setting:
change it, re-fill the zones, and the port you simulated is no longer the port
on the board. 0.4 mm rather than KiCad's 0.2 mm, because 0.2 mm is under two
cells at the mesh resolution the openEMS script defaults to.

The second job is less obvious and matters more. **Anywhere the pour touches
the bottom bar is a short to ground.** If the cut ended anywhere left of the
short pad, the pour would ground the bar closer to the feed than the short pad
does — and Table 1's **D5 = 1.40 mm**, the feed-to-short distance that sets
the input impedance, would silently become whatever the pour happened to touch
first. So the cut ends exactly at the short pad's left edge, and
`check_sim_board.py` fails if it does not:

```
ok   board: one footprint (the radiator), no connector, no tracks - the model is the antenna and the ground plane, nothing else
ok   board: Texas_SWRA117D_2.4GHz_Left matches all 14 dimensions of SWRA117D Table 1 within 11 um (exact copy) - the same footprint file the fabrication board uses
ok   board: bottom ground plane 39.6 x 23.5 mm, same outline as the top pour, both on GND
ok   port: 0.40 mm gap between the radiator and the ground pour, held open by RF_PORT_GAP; the pour meets the radiator at the short pad only, so D5 is 1.40 mm
ok   port: 5 ground vias within 2.0 mm of the feed pad, nearest at 0.85 mm
ok   board: 48 ground vias total, all F.Cu -> B.Cu
ok   board: every via clears the port pad by at least 0.55 mm (minimum 0.15 mm)
ok   board: antenna keep-out runs down to the plane edge at y = 66.25, on F.Cu and B.Cu
ok   board: 2 copper zone(s) carry no fill yet - open the board and press B before simulating, or the model has no ground plane

0 problem(s)
```

Those checks are mutation-tested, and the test is in the repo:
`tools/mutate_sim_board.py` breaks a scratch copy of the board 14 different
ways and asserts the checker catches each one — a connector put back, a track
put back, the bottom ground deleted or shrunk, the gap closed to 0.2 mm, the
cut stopped short of the short pad or not clearing the bar, the cut reaching
through to B.Cu, the port vias removed, a via on the pad, a via off GND, a via
that does not reach B.Cu, the keep-out stopping short of the plane edge.

```
$ python3 tools/mutate_sim_board.py
caught      a connector footprint back in the model
              board: the simulation model still carries X:SMA - a connector inside the model is part of the answer it gives
...
14/14 mutations caught
```

### Using it

```sh
python3 tools/gen_sim_board.py    # rebuild it
python3 tools/check_sim_board.py  # check it
python3 sim/openems/swra117d_openems.py --board sim/board/swra117d_2g4_sim.kicad_pcb
```

Open `sim/board/swra117d_2g4_sim.kicad_pro` and press **B** first: the zones
are stored unfilled here too, and an unfilled pour is not a ground plane. In
RFsim, nominate **AE1 pad 1** as the port and choose **Lumped** — there is no
line for a microstrip port to launch into, which is the whole point. The four
settings above still apply; only the port row changes.

The result is the antenna's own S11. Compare it with the fabrication board's
and the difference is the feed line and the launch — which is a useful number
in its own right, and the one to quote when someone asks what their layout is
costing them.

[`docs/sim-board-drawing.svg`](docs/sim-board-drawing.svg) is the drawing,
generated from this board by the same renderer as the other one.

## Reusing this on someone else's board

[`docs/antenna-integration-checklist.md`](docs/antenna-integration-checklist.md)
is the checklist this project produced: 50 items across antenna placement,
feed, stitching, simulation setup, what to leave out of a model, and tuning —
each one there because getting it wrong here cost a wrong answer. It is written to be applied to any printed
antenna, not just this one, and the "before you trust a simulation" section is
the part that has earned its place most.

[`docs/board-drawing.svg`](docs/board-drawing.svg) is generated by
`tools/board_to_svg.py` from the board file, so a review drawing can never
drift from the copper. Shapes carry class names rather than colours, so the
page embedding it can theme it.

## Reference

TI application note SWRA117D, *2.4 GHz Inverted F Antenna*:
<https://www.ti.com/lit/an/swra117d/swra117d.pdf>
