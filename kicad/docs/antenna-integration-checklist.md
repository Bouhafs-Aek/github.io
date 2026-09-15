# PCB antenna integration: design review checklist

A printed antenna is cheap in BOM and expensive in mistakes. Everything below
is checkable from a layout before anything is fabricated, and each item exists
because getting it wrong costs a board spin or a failed range test. Numbers in
brackets are for 2.45 GHz on 1.6 mm FR4 (εr 4.5) — recompute for your stackup
with `tools/line_impedance.py`, which reads it out of the board file.

## 1. The antenna is not just the antenna

- [ ] **The ground plane is half the radiator.** An inverted-F radiates
      against the plane it is fed from. Fix the plane size and shape *before*
      tuning: changing it later re-tunes the antenna.
- [ ] **Keep-out respected on every layer.** No pour, track, via, component or
      shield inside the manufacturer's clear area. Not "mostly" — a via in the
      near field detunes the antenna.
- [ ] **Plane edge is where the datasheet says**, and it is a straight, clean
      edge. This edge is the antenna's ground reference.
- [ ] **Antenna on a board edge or corner**, radiating outward, with ≥ 10 mm
      of clear space in front of it inside the enclosure.
- [ ] **Board not extended past the antenna.** Dielectric alongside the arm
      loads it and pulls resonance down. Keep only routing margin (~1 mm).
- [ ] **Nothing metal nearby**: battery, display, camera, screws, shield cans,
      hand or wrist position on a wearable.

### What TI actually specifies (DN023 / SWRA228C, quoted)

Sourced rules beat remembered ones. From the 868/915/955 MHz IFA design note,
which states its implementation explicitly — the same antenna family and the
same topology as a 2.4 GHz IFA:

- **"The antenna was implemented on a 0.8 mm thick FR-4 substrate."**
- **"Since there is no ground plane beneath the antenna the PCB thickness is
  not critical, but if a different thickness is being used it might be
  necessary to tune the length of the antenna."** Worth internalising: for
  this topology the substrate is a second-order effect, because the radiator
  has air on one side and no ground under it. Do not reach for substrate
  thickness to explain a large frequency error.
- **"To obtain optimum performance it is important to make an exact copy of
  the antenna dimensions."** Implement the published geometry. Tune by the
  element the note nominates, not by redrawing the antenna.
- **Tuning is one segment, not a global scale.** DN023 tunes the open stub:
  with its 31 × 45 mm ground plane, that leg is ~9 mm at 868 MHz and ~1 mm at
  915 MHz. Uniform scaling preserves the feed-tap ratio and so the impedance,
  but it is a departure from the published copy — prefer the nominated trim
  where the note gives one.
- **"Avoid placing components or having a ground plane close (minimum 5 mm) to
  each side of the antenna."** A hard number for the side clearance.
- **"The size of the ground plane affects the impedance of the antenna"**, and
  the radiation pattern with it. The plane is a design input, not a leftover.
- **"Since the impedance of this antenna is approximately matched to 50 ohm,
  no external matching components are needed."** And in the same paragraph:
  the reference design **still includes pads for one series and two shunt
  components** at the feed, "to compensate for detuning caused by plastic
  encapsulation and other objects in the vicinity". Both halves are the
  guidance: fit nothing by default, but leave the sites.

## 2. Feed

- [ ] **Line impedance computed for the real stackup**, not assumed
      [1.49 mm for 50 Ω; a 1.5 mm line is 71 Ω if the board is 1.6 mm].
- [ ] **Feed as short as the layout allows**, no stubs, no unnecessary corners.
      Length does not change |S11| but every mm adds loss and rotation.
- [ ] **Continuous reference under the whole line.** No plane splits, no
      slots, no crossing a pour gap.
- [ ] **Top pour kept back from the line** if you want microstrip behaviour
      [1.0 mm keeps 1.5 mm at 49.8 Ω; 0.5 mm pulls it to 46.4 Ω].
- [ ] **Launch referenced.** An end-launch connector is coplanar by
      construction — give it ground either side *and* ground beneath, with
      vias at the launch, not 3 mm away.
- [ ] **Matching pads present even if unpopulated.** Three 0402 sites cost
      nothing on the BOM and turn a re-spin into a component swap.

## 3. Ground stitching

- [ ] **Beside every layer-changing signal via**, within 1–2 mm. The return
      current changes layers too.
- [ ] **Fence along the edges of the plane pair** at ≤ λ/20 [2.9 mm].
- [ ] **Both gaps of any coplanar line** stitched, or the coplanar ground
      floats and supports its own modes.
- [ ] **No floating pour island.** Every piece of pour left by a keep-away or
      a split needs a via. A 22 mm island is half-wave resonant at 3.25 GHz.
- [ ] **Two or more vias on any ground that matters.** One 0.3 mm via through
      1.6 mm FR4 is about 1.30 nH — 20 Ω at 2.45 GHz (0.54 nH and 8.3 Ω
      through 0.8 mm): via inductance scales with board thickness.
- [ ] **No stitching inside the antenna keep-out.**

## 4. Before you trust a simulation

Every one of these has produced a confidently wrong answer in practice.

- [ ] **Copper pours filled** in the exported geometry. Unfilled zones mean no
      ground plane — a different antenna, not a small error.
- [ ] **Stackup matches the board**: thickness, εr, loss tangent, copper.
      Cross-check by asking the tool what width it thinks 50 Ω is.
- [ ] **Air/domain margin ≥ λ/4 at the LOWEST frequency in the sweep**, not at
      the design frequency. This catches people out: λ/4 is 31 mm at 2.45 GHz
      but 75 mm at 1 GHz, and the domain volume grows with the cube — from a
      5 mm margin, ×26 to reach 31 mm and ×223 to reach 75 mm. Runtime follows.
      The cheap fix is to start the sweep at 2 GHz rather than 1 GHz, and to
      state plainly that anything below the start is not modelled.
- [ ] **Port type matches the physical launch** (microstrip / coplanar /
      lumped) and is actually attached to the feed line.
- [ ] **Mesh resolves the narrowest copper** and the substrate thickness.
- [ ] **Separate the match from the frequency before you act on either.** A
      deep null in the wrong place and a shallow null in the right one are
      different faults with different fixes. The null's *depth* is the feed tap
      against the short; its *position* is the radiator's electrical length.
      Uniform scaling moves the second and preserves the first, so read them
      apart before touching copper.
- [ ] **Ask whether the error is bigger than the model's own uncertainty.**
      FR4 εr is quoted 4.2–4.8; solder mask over the radiator is typically
      absent from the model and pulls resonance down about a percent; etch
      tolerance moves a narrow strip by a few percent of its width. A few
      percent of frequency error is inside that envelope, and scaling copper to
      cancel it is fitting geometry to an uncertainty. Measure a board first.
- [ ] **Read the note you are copying, not the one you copied last time.**
      Two TI reference antennas, two opposite answers: SWRA117D says the
      inverted-F is a 50 Ω design and wants nothing in the path, while DN024
      says the monopole needs a pi network at the feed and publishes its
      values. "No matching network" is a finding about one antenna, not a
      principle.
- [ ] **Check whether the radiator is one layer or two.** DN024 puts its
      copper on both, "for lower resistive loss and slightly wider bandwidth".
      A model or a fabrication drawing that carries only the top layer is a
      different antenna.
- [ ] **Sanity-check against physics.** If a result implies εr,eff < 1, or a
      quarter-wave length that beats the speed of light, the setup is wrong,
      not the antenna.
- [ ] **A DC short at the port is normal** for an inverted-F: the arm is
      shorted to ground by design. A circuit-level extractor sees only that
      short and reports VSWR → ∞.

## 4a. Choosing the port model

Every field solver offers two or three port models, and they differ in what
they assume about the structure. Picking the wrong one produces a plausible
answer that is wrong, so the rule is: **the port model must match the physical
launch.**

| model | what it does | reference plane | use it when |
|---|---|---|---|
| **Lumped** | a voltage source with a series resistance across one gap, a few mesh cells wide | undefined — wherever the gap is | the structure has no transmission line: a gap-fed antenna, a lumped component, a quick look |
| **Microstrip (MSL)** | excites the microstrip *mode* over the line cross-section, with a feed shift and a measurement plane so incident and reflected waves separate | defined, and de-embedded to it | a trace with a solid ground plane directly beneath |
| **Coplanar (CPW / GCPW)** | the same, for the coplanar mode: strip to the side grounds, plus the plane below if there is one | defined, and de-embedded to it | a trace with ground either side on the same layer |

What the lumped port costs you: the excitation is a localised, non-physical
field at one gap; the 50 Ω is a number you declared rather than the line's
actual impedance; and nothing is de-embedded, so S11 mixes the port's own
behaviour with the circuit's. It is sensitive to the local mesh in a way the
mode-launched ports are not.

**The field plot tells you which one is active.** A lumped port leaves an
isolated hot blob at the pads; a mode-launched port produces a field that
flows smoothly out of the port and down the line. If the launch is far
brighter than the line, check the port model before believing the result.

**For an end-launch SMA** the footprint is coplanar by construction — signal
pad with ground either side — so the gap decides which model describes it
better. Compute both and compare:

| stackup | gap | as GCPW | as microstrip |
|---|---|---|---|
| 1.6 mm FR4, 2.95 mm line | 2.0 mm | 49.8 Ω | 50.2 Ω |
| 0.8 mm FR4, 1.50 mm line | 0.8 mm | 48.8 Ω | 49.7 Ω |

Where the two agree to a fraction of an ohm, either model works and the choice
stops mattering. Where they diverge, the gap is tight enough that the coplanar
ground really is carrying return current, and CPW is the honest answer.

## 4b. Read the solver's settings back out of its own output

Dialog boxes lie by omission — a preset you forgot to change looks identical
to one you set deliberately. Every solver hands you the settings back in its
results if you know where to look, and checking takes seconds:

- [ ] **Field-plot caption.** A cut described as the *substrate mid-plane* at
      z = 0.80 mm is the mid-plane of a **1.6 mm** board; a 0.8 mm board would
      say 0.40 mm. Halve the number and compare it to your stackup.
- [ ] **Field-plot extent.** The coloured region ends at the domain boundary.
      Measure it against the board outline on the axes: if the field stops a
      few mm past the copper, the margin is a few mm, whatever you meant to
      set. Bright field sitting *on* that boundary means the absorber is
      inside the near field and the result is not trustworthy.
- [ ] **Step the phase of a field animation.** This is the sharpest test for a
      domain that is too small, and it costs nothing. At the phases where the
      board's own field passes through a null, the boundary should go dark
      too. If the absorbing boundary is ever the *brightest thing in the
      frame*, it is holding energy that should have left — the domain is
      inside the near field and the resonance it reports is not the antenna's.
- [ ] **Port width the tool proposes.** A solver that offers a 50 Ω width is
      telling you which stackup it believes. Compare with your own
      calculation — 3.11 mm means 1.6 mm FR4, 1.49 mm means 0.8 mm.
- [ ] **Layer list / copper shown in the geometry preview.** If the pours are
      missing from the picture, they are missing from the model.
- [ ] **Sanity of the result itself.** εr,eff below 1, a quarter-wave arm that
      beats the speed of light, or VSWR → ∞ across an entire sweep are setup
      faults, not antenna behaviour.

## 4c. Repeatability before belief

A single plot is not a result. Before any number leaves the solver and turns
into a design change:

- [ ] **Run it twice** and get the same answer. A model whose boundary sits in
      the near field, or whose mesh is too coarse, will happily produce a
      different resonance each time the geometry is nudged.
- [ ] **Change one thing per run**, and write down what changed. Two settings
      moving at once is how two errors cancel and look like confirmation.
- [ ] **Converge the mesh**: refine once and check the answer does not move.
      If it moves, the earlier answer was mesh, not antenna.
- [ ] **Converge the domain**: enlarge the air box and check the answer does
      not move.
- [ ] **Track the spread.** If successive runs on an unchanged board disagree
      by more than the bandwidth you are designing for, none of them is
      usable. Log the setup with every number so the spread is visible.

## 4d. Decide what is *in* the model before you run it

A simulation answers a question about a geometry, and the geometry is a
choice. Two boards, both correct, answer different questions:

| the model contains | it answers |
|---|---|
| antenna + ground plane only, port at the feed | what does this antenna do? |
| + feed line | what does the antenna plus my routing do? |
| + connector footprint | what will the VNA on the connector read? |

Run only the third and a wrong number has three suspects. Start from the
first and each thing you add afterwards, you can price. The middle one is
usually the practical choice: most solvers want a transmission line to launch
a port into, and a short line with a defined impedance is far better behaved
than a gap port.

- [ ] **Know which of the three you are running**, and say so when you quote
      the result. "Resonance is at 2.4 GHz" without this is not a claim anyone
      can check.
- [ ] **Strip the connector for the antenna-only model.** Its pads are copper
      in the model and the port's return current runs through them; the bright
      field around them is real, not an artefact, and it is not the antenna's.
- [ ] **Take the connector out before you blame the antenna.** Its pads are
      copper in the model and the port's return current runs through them; the
      bright field around them is real and is not the antenna's. Replace the
      connector land with a bare port land — signal pad, ground pad under it,
      nothing else — and it stops being a suspect without changing anything
      else.
- [ ] **Give the port a pad, and give the pad reference copper.** Most tools
      attach a port to a *pad*, not to a track end, and refuse to launch if
      there is no copper on the reference layer beneath it. Put that copper in
      as a **pad**, not a zone: zones are stored unfilled, so a reference that
      depends on a fill is missing the first time anyone opens the project.
      Left without one, the tool picks some other pad — often the antenna's own
      feed pad, which by design has no plane under it.
- [ ] **Change the port model when you remove the connector.** An end-launch
      footprint makes the line coplanar, so a CPW port fits it. With the
      footprint gone there is no coplanar ground beside the line and it is a
      plain microstrip — an MSL port is then the one that matches.
- [ ] **Check which layers the ground is actually on, and model only those.**
      A reference design that puts the ground on one layer is making a choice:
      a top pour beside the feed turns a microstrip into a coplanar line, and
      adding one to the model answers a different question than the figure
      asks. Read the layer off the drawing, not off habit.
- [ ] **Count the vias in the reference drawing.** If it has one, a model with
      forty has copper the design does not. With the ground on a single layer
      there is nothing to stitch, and stitching vias are then a source of
      geometry rather than a fix for it.
- [ ] **A gap port needs a gap you control.** If you do feed with no line at
      all, the port is a lumped port across the gap between the radiator and
      the ground pour. Cut that gap as a *keep-out*, not as the zone's pour
      clearance: pour clearance is a design setting, so anyone who re-fills the
      zones with a different one has changed the port without touching the
      antenna.
- [ ] **Make the gap wider than two mesh cells.** A 0.2 mm clearance under a
      0.25 mm mesh is not a port, it is a rounding error. Widen the gap or
      refine the mesh locally, and check the field plot resolves it.
- [ ] **Do not let the pour decide where the short is.** On an inverted-F the
      feed-to-short distance sets the input impedance (SWRA117D calls it D5 and
      gives it as 1.40 mm). Anywhere the ground pour touches the radiator is a
      short, so if the pour reaches the arm before the short pad does, that
      dimension is silently something else. End the cut exactly at the short
      pad, and have a checker assert it.
- [ ] **Stitch at the port, not just on the board.** Everything between the
      port and the nearest via to the bottom plane is series inductance in
      front of the antenna. A few millimetres of detour across the top pour is
      worth far more than the 0.5–1.3 nH of the via itself.
- [ ] **Put the stitching vias in the model.** A top pour with no vias is a
      sheet of copper floating over the plane — which is not the board, and
      will not behave like it.
- [ ] **Keep the two boards comparable.** Same outline, same stackup, same
      plane edge, same antenna file. If the simulation board is also a
      different size, the difference between the two results is not the feed
      line any more.

## 5. Tuning and validation

- [ ] **Tune on the assembled, enclosed product**, not the bare board.
      Housing, battery and hand loading move resonance by tens of MHz.
- [ ] **De-embed the feed** or keep it short enough not to matter, and choke
      the measurement cable — cable currents on the ground plane will lie to
      you.
- [ ] **Measure efficiency, not only S11.** A perfectly matched antenna can be
      a perfectly matched resistor. −10 dB return loss says nothing about how
      much power radiates.
- [ ] **Check the whole band**, plus harmonics if you have a compliance limit.
- [ ] **Retune by uniform scaling** where possible: it moves resonance as 1/k
      and preserves the feed-tap ratio, so the impedance survives.
- [ ] **Golden sample kept** and re-measured on every stackup or vendor change.
