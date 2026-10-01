# Football GNSS tracker — an EPTS pod in KiCad

A wearable player tracker for football: a pod worn between the shoulder blades
in a vest, logging position, speed and inertial data for training analysis. In
the paper's terms it is an EPTS, an Electronic Performance and Tracking System.

It builds out the **future work** of

> L.A. Oliveira, R. García, D. Melendi, R. Oliveira, *A low-cost GNSS-based
> electronic performance and tracking system for sports: Design, validation,
> and accuracy enhancement through signal processing techniques*, Results in
> Engineering 32 (2026) 112596,
> [doi:10.1016/j.rineng.2026.112596](https://doi.org/10.1016/j.rineng.2026.112596).

Their prototype (a Maduino Zero A9G with a GPS-only receiver logging at 1 Hz)
reached 0.21 m mean error after outlier removal and an 11-sample moving
average. They list the limits themselves: 1 Hz misses sprints and changes of
direction, GPS-only suffers multipath, there is no IMU, and satellite count
and DOP were never logged. Their conclusion asks for "higher-frequency GNSS
modules" plus IMUs and sensor fusion. This board is that hardware:

| limitation in the paper | this board |
|---|---|
| GPS only, logged at 1 Hz | **u-blox NEO-M9N**: GPS, Galileo, GLONASS and BeiDou, up to 25 Hz. It is the module the paper names as preferable. |
| no IMU ("does not eliminate the need for sensor fusion (IMU)") | **ST ISM330DHCX**: ±16 g, ±4000 dps, up to 6.67 kHz, on its own SPI bus |
| satellites and HDOP not stored | UBX over UART: `NAV-PVT` carries numSV, pDOP and hAcc/sAcc in every epoch |
| devices aligned afterwards by timestamp matching | **TIMEPULSE (PPS)** wired to the MCU, so every pod samples on GNSS time |
| microSD, raw CSV ("open data") | microSD kept, in SPI mode, for raw UBX + IMU logs |
| GPRS for live data, needs a SIM | **nRF52840** (Raytac MDBT50Q-1MV2): BLE for live status, USB for download |
| 3.7 V 1800 mAh Li-Po, > 20 h | same cell, with a **USB-C charger** and load sharing on board |
| 54 × 80 × 16 mm enclosure | 42 × 72 mm board, so it fits that same enclosure |

## What is in the repository

```
├── tracker/
│   ├── epts_football_tracker.kicad_pro   net classes: GNSS_50R, Power, USB
│   ├── epts_football_tracker.kicad_sch   A3, one sheet, 46 parts
│   ├── epts_football_tracker.kicad_pcb   4 layer, 42 x 72 mm, placed + RF routed
│   └── sym-lib-table / fp-lib-table      -> ../library/EPTS_Tracker.*
├── library/
│   ├── EPTS_Tracker.kicad_sym            19 symbols, from KiCad 9.0.9.1
│   └── EPTS_Tracker.pretty/              18 footprints from KiCad 9.0.9.1 + the patch
└── tools/
    ├── gen_tracker_library.py            fetches and flattens the library parts
    ├── gen_tracker_project.py            writes schematic, board and project
    ├── check_tracker.py                  netlist, ERC, electrical and RF checks
    ├── pcb_helpers.py                    KiCad s-expression writers
    ├── line_impedance.py                 microstrip / CPWG impedance
    └── sexpr.py                          KiCad s-expression reader/writer
```

**State of the board: placed, not fully routed.** The parts the GNSS
performance depends on are laid down and checked: the patch and its ground,
the 50 Ω feed, the matching pads, the via fences and the BLE antenna keep-out.
The remaining digital and power connections are ratsnest. Route them in KiCad,
where the interactive router and DRC can see them, then press **B** to fill
the four GND pours.

## Block diagram

```
 25 mm patch ── CPWG 50 Ω ── Z3/Z2/Z1 ── NEO-M9N ──UART + PPS + EXTINT + RESET──┐
                                                                              │
 ISM330DHCX ──────────── SPI (own bus) + INT1/INT2 ─────────────────── MDBT50Q (nRF52840)
                                                                              │  BLE, chip antenna
 microSD (SPI) ────────────────────── SPI + card detect ──────────────────────┤
                                                                              │
 USB-C ─ USBLC6 ─ D+/D- ──────────────────────────────────────────────────────┘
   │
   └─ VBUS ─ MCP73831 (500 mA) ─ VBAT ─ 1S Li-Po 1800 mAh
        └── D1 ─┐       Q1 ──────┘
                VSYS ─ AP2112K-3.3 ─ +3V3 → everything
```

## Parts

| ref | part | why this one |
|---|---|---|
| U1 | u-blox **NEO-M9N** | 4 constellations, 25 Hz. It shares the NEO footprint with the NEO-6M the paper used, so the result is directly comparable. |
| AE1 | 25 × 25 × 4 mm passive ceramic L1 patch | Sits on the top GND pour, sky side. The NEO-M9N has its own SAW and LNA, so no active antenna supply is needed. |
| Z1–Z3 | 0402 pi network | Z2 is fitted as a 0 Ω link; Z1 and Z3 are not fitted. It is there to retune the patch inside the case, a convention borrowed from the TI antenna boards in [Bouhafs-Aek/github.io](https://github.com/Bouhafs-Aek/github.io/tree/claude/wonderful-lovelace-52zxld/kicad). |
| U2 | Raytac **MDBT50Q-1MV2** (nRF52840) | BLE 5 plus native USB in a pre-certified module with its own antenna |
| U3 | ST **ISM330DHCX** | Industrial 6-axis IMU. At ±16 g it covers running and jumping; a slide tackle or a ball strike to the back can exceed it. |
| J3 | Hirose **DM3AT** microSD | The paper's open-data store, push-push with card detect |
| U4 | Microchip **MCP73831-2** | 4.20 V single-cell charger; R7 = 2.0 kΩ sets 500 mA (0.28 C) |
| Q1, D1 | AO3401A + B5819WS | Load sharing: the system runs from USB while the cell charges |
| U5 | Diodes **AP2112K-3.3** | 600 mA LDO, 55 µA quiescent |
| J1, U6 | GCT USB4105 USB-C + USBLC6-2SC6 | Sink-only (5.1 kΩ Rd on CC1/CC2), ESD on D+/D-/VBUS |
| J2 | JST-PH 2-pin SMD | Battery. Pin 1 is +. **Check your cell's cable**: Li-Po vendors do not agree on JST polarity. |
| J4 | Tag-Connect TC2030-NL | SWD with no header fitted (VCC, SWDIO, SWCLK, nRESET, SWO) |
| SW1, D2, D3 | button, status LED, charge LED | The button starts and stops a session and wakes the MCU from System OFF |

All symbols and footprints except the patch are copies of the official KiCad
library parts, pinned to tag `9.0.9.1`. Their pin tables are the ones the
checker reads. The one generated footprint is the patch, and it has one
part-specific dimension: **the feed pin's offset from the centre**
(`PATCH_FEED_OFFSET`, 1.5 mm). Set it from the drawing of the patch you buy
and regenerate the library and the board.

## Firmware pin map

Printed by `check_tracker.py` from the schematic itself, so it cannot go stale:

| nRF52840 | net | | nRF52840 | net |
|---|---|---|---|---|
| P0.08 | GNSS_TXD (UARTE RX) | | P0.20 | IMU_SCK |
| P0.06 | GNSS_RXD (UARTE TX) | | P0.21 | IMU_MOSI |
| P0.13 | GNSS_PPS | | P0.22 | IMU_MISO |
| P0.14 | GNSS_EXTINT | | P0.23 | IMU_CS |
| P0.15 | GNSS_RESET_N | | P0.24 / P0.25 | IMU_INT1 / IMU_INT2 |
| P0.26 | SD_SCK | | P0.02 (AIN0) | VBAT_SENSE = VBAT / 2 |
| P0.27 | SD_MOSI | | P1.06 | BTN (internal pull-up) |
| P0.07 | SD_MISO | | P1.07 | LED_K (active low) |
| P0.11 | SD_CS | | P0.18 | nRESET (SWD) |
| P0.12 | SD_DET (internal pull-up) | | P1.00 | SWO |

Before committing to this map, check it against the nRF52840 product
specification's table of GPIOs near the radio. Nordic recommends low-drive,
low-frequency use for some of those pins. The SD and IMU clocks were kept on
P0 pins for that reason, but the checker cannot read that table.

## The GNSS front end

* **The patch sits on the board's top GND pour**, which is part of the
  antenna. Nothing else is placed within 1 mm of it, and the checker enforces
  that. Vias under the ceramic are tented.
* **The feed runs on the bottom layer**, because the top copper under the
  patch is ground. From the feed pin it is a grounded coplanar waveguide on
  B.Cu over the In2 GND plane, then a via up to the top layer at the pi
  network, then into RF_IN (pad 11).
* **50 Ω on this stackup is w = 0.38 mm with a 0.30 mm gap.** The stackup is
  JLC04161H-7628, with a 0.2104 mm prepreg at εr 4.4 between each outer layer
  and its plane. `line_impedance.cpwg` gives 51.4 Ω, and the checker requires
  45–55 Ω. The gap is the netclass clearance of `GNSS_50R`, so the pour keeps
  it automatically.
* **Via fences** run along both sides of the feed. The total feed length is
  25 mm.
* **The BLE module's antenna overhangs nothing.** It sits on the right board
  edge, and a keep-out on all four copper layers runs from the module's own
  keep-out to the board edge.

## Power budget (estimate; check each figure against the data sheets)

| consumer | typical | note |
|---|---|---|
| NEO-M9N, continuous tracking | ~35 mA | depends on constellations and rate |
| nRF52840: logging, BLE advertising | ~3 mA | mostly asleep between samples |
| ISM330DHCX, high-performance mode | ~1 mA | |
| microSD, averaged over buffered writes | ~5 mA | card dependent |
| LDO quiescent, divider, leakage | < 0.1 mA | |
| **total** | **~45 mA** | 1800 mAh → **~35–40 h** |

A match is 90 minutes and a training session 2 hours, so this leaves days
between charges. The figure that dominates is the GNSS module's, so the
power-save modes in the u-blox integration manual are the place to start if
you need more.

## Running it

```sh
python3 tools/gen_tracker_library.py   # only to refresh the library (needs network)
python3 tools/gen_tracker_project.py   # schematic, board, project
python3 tools/check_tracker.py         # must end with "all checks passed"
```

`check_tracker.py` reads only the files KiCad reads and never imports the
generator. It is this project's stand-in for ERC, because CI has no KiCad
install, and it checks:

* **netlist**: every schematic pin's net is derived from the wires, labels and
  no-connect flags in the `.kicad_sch`, and must equal the net on the matching
  board pad
* **ERC**: no floating pins, no single-pin nets, every power input driven
  (PWR_FLAG on GND, VBUS and VSYS), at most one output per net
* **electrical**:
  * every supply pin within its absolute maximum
  * the full cell at the ADC at 2.10 V
  * charge current 500 mA = 0.28 C
  * USB-C Rd resistors present
  * u-blox requirements: VDD_USB to GND with USB unused, D_SEL open for
    UART, RF_IN reaching the patch only through the pi network
  * ISM330DHCX unused aux pins handled
  * SD pull-ups present
  * SWD on P0.18 / P1.00
* **board**:
  * one RF width at 50 Ω on both outer layers
  * an unbroken copper path from the patch feed through Z2 to RF_IN
  * no GND via inside the feed gap
  * no courtyard overlaps
  * nothing near the patch, nothing in the BLE keep-out
  * every via clear of other nets' pads

The checker was mutation-tested. Renaming one net label and widening one feed
segment each make it fail with the right message, and the generated files
pass. The checker caught one real bug during development: the pi network's
route assumed the C_0402 pad offset (0.48 mm) for an R_0402 (0.51 mm).

## Open items before ordering boards

1. **Route the ratsnest** in KiCad, fill zones, then run ERC and DRC.
2. **Patch feed offset**: set `PATCH_FEED_OFFSET` from the chosen part.
3. **Battery polarity** at J2: match the cell's cable.
4. **Enclosure and patch tuning**: a plastic case and the wearer's back detune
   the patch. Measure inside the case, and use Z1–Z3 if it has moved, the same
   procedure as for the TI antenna boards it was developed alongside.
5. **Firmware** is not part of this project. The hardware assumes UBX
   `NAV-PVT` at 10–25 Hz over UART, IMU FIFO reads on INT1, and logs written
   to microSD, with PPS-aligned timestamps so the paper's post-processing
   (outlier removal, then an 11-sample moving average, or IMU fusion) can run
   on the raw data.

## Origin

This project was developed in
[Bouhafs-Aek/github.io](https://github.com/Bouhafs-Aek/github.io), on
branch `claude/wonderful-lovelace-52zxld` under `kicad/tracker/`. That repo
also holds the TI SWRA117D and DN024 antenna designs; this one holds the
tracker alone. The KiCad library parts keep their original CC-BY-SA 4.0
license, which explicitly does not extend to designs that use them.
