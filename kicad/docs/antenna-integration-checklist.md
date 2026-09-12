# PCB antenna integration: design review checklist

A printed antenna is cheap in BOM and expensive in mistakes. Everything below
is checkable from a layout before anything is fabricated, and each item exists
because getting it wrong costs a board spin or a failed range test. Numbers in
brackets are for 2.45 GHz on 0.8 mm FR4 (εr 4.4) — recompute for your stackup
with `tools/line_impedance.py`.

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
      0.8 mm FR4 is 0.54 nH — 8.3 Ω at 2.45 GHz.
- [ ] **No stitching inside the antenna keep-out.**

## 4. Before you trust a simulation

Every one of these has produced a confidently wrong answer in practice.

- [ ] **Copper pours filled** in the exported geometry. Unfilled zones mean no
      ground plane — a different antenna, not a small error.
- [ ] **Stackup matches the board**: thickness, εr, loss tangent, copper.
      Cross-check by asking the tool what width it thinks 50 Ω is.
- [ ] **Air/domain margin ≥ λ/4** [31 mm]. A margin of a few mm puts the
      absorbing boundary inside the antenna's near field.
- [ ] **Port type matches the physical launch** (microstrip / coplanar /
      lumped) and is actually attached to the feed line.
- [ ] **Mesh resolves the narrowest copper** and the substrate thickness.
- [ ] **Sanity-check against physics.** If a result implies εr,eff < 1, or a
      quarter-wave length that beats the speed of light, the setup is wrong,
      not the antenna.
- [ ] **A DC short at the port is normal** for an inverted-F: the arm is
      shorted to ground by design. A circuit-level extractor sees only that
      short and reports VSWR → ∞.

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
- [ ] **Port width the tool proposes.** A solver that offers a 50 Ω width is
      telling you which stackup it believes. Compare with your own
      calculation — 3.11 mm means 1.6 mm FR4, 1.49 mm means 0.8 mm.
- [ ] **Layer list / copper shown in the geometry preview.** If the pours are
      missing from the picture, they are missing from the model.
- [ ] **Sanity of the result itself.** εr,eff below 1, a quarter-wave arm that
      beats the speed of light, or VSWR → ∞ across an entire sweep are setup
      faults, not antenna behaviour.

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
