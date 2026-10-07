# PCB antennas, done the way a supplier should document them

A working demonstration of integrating printed antennas into an IoT product:
three TI reference antennas built as **exact copies of their published
dimension tables**, each with a program that re-measures the finished file and
fails the build if it has stopped being an exact copy — plus the ground-plane
study, the matching, the simulation models and the bench procedure that turn a
copied shape into a design you can defend.

## [`kicad/kit/`](kicad/kit) — the deliverable: six boards

Three antennas, each built twice. **A PCB antenna is not a component: the
ground plane is part of the antenna**, so which plane you put it on decides
what you measure. One board per antenna cannot answer both questions, so each
gets two.

| | antenna | size | band | note |
|---|---|---|---|---|
| **AN043** | meandered inverted-F | 15 × 6 mm | 2.45 GHz | SWRA117D |
| **DN023** | printed inverted-F | 43 × 20 mm | 868 / 915 / 955 MHz | SWRA228C |
| **DN024** | meandering monopole | 38 × 25 mm | 868 + 2440 MHz | SWRA227E |

* `*_ref` sits on the plane its note publishes — so the measurement
  **validates the build** against TI's own numbers.
* `*_common` sits on a 45 × 60 mm plane shared by all three — so the three
  become **comparable with each other**, which is the question a customer
  actually asks.
* The difference between the two boards of a pair is that antenna's
  **ground-plane sensitivity**, measured rather than asserted.

Everything that is not the antenna or the plane is held constant: 1.6 mm FR4,
the same U.FL launch, the same 2.95 mm 50 Ω line, the same three matching
sites. A checker asserts it, because a kit whose variables leak is not a kit.

<p align="center">
<img src="kicad/docs/kit/dn023_common.svg" width="30%">
<img src="kicad/docs/kit/dn024_common.svg" width="30%">
<img src="kicad/docs/kit/an043_common.svg" width="30%">
</p>

## What is actually in here

| | |
|---|---|
| `kicad/kit/` | the six evaluation boards |
| `kicad/dn024/`, `kicad/dn024_ti_form/`, `kicad/swra117d_*` | standalone fabrication projects, including DN024 drawn the way its own Figure 2 draws it |
| `kicad/sim/board/` | two RFsim projects, built so a full-wave run can produce a meaningful answer |
| `kicad/sim/openems/`, `kicad/sim/*.cir` | full-wave and lumped simulation flows that read their geometry out of the board file |
| `kicad/library/` | symbols and footprints, every antenna generated from its published table |
| `kicad/tools/` | 30 programs: generators, four checkers, three independent verifiers, two mutation suites |
| `kicad/docs/antenna-integration-checklist.md` | 85 items, every one of them there because getting it wrong here cost a wrong answer |

## The rule the whole repository follows

**Nothing is invented, and everything is checked by something that did not
build it.**

* Each antenna is re-measured out of the written file by a `verify_against_*`
  program that re-derives the note's table by scanline, with no knowledge of
  how the shape was built. It is what found a real bug: a ribbon capped flat
  at its last centre-line point left one stub half a trace short.
* Matching values are copied where a note publishes them (DN024's 3.9 pF) and
  **left unfitted where none does** — the pads are laid out because AN058 asks
  for them, not with numbers made up to fill them.
* Where a note contradicts itself, both readings are written down rather than
  one being chosen in silence. DN023 gives its trim dimension `L6` three
  different values; the board is built at the longest, the two measured ones
  are marked on the silkscreen as a cut scale.
* The checkers are themselves tested: `mutate_*` breaks the boards on purpose
  — **29 faults, 29 caught**.

## Two things worth reading even if you never open KiCad

**[Why a meandered radiator tied to the bottom layer still
radiates](kicad/README.md#two-layers-only-count-as-one-conductor-if-you-stitch-them)** —
and why two unstitched layers are a 140 Ω parallel-plate line that traps the
field instead.

**[The two faults that make a full-wave run
meaningless](kicad/README.md#simulating-it-simboarddn024_monopole_sim)** — a
ground pour stored unfilled, and a 3.9 pF capacitor that a field solver reads
as a 0.40 mm gap, which is −j6100 Ω at 868 MHz. Both look fine on screen, and
both produce a confident, detailed, entirely wrong S11.

Full detail: **[kicad/README.md](kicad/README.md)**.
