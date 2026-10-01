#!/usr/bin/env python3
"""Generate the football GNSS tracker: schematic, 4-layer board and project.

A wearable EPTS pod (Electronic Performance and Tracking System) for team
sport, worn between the shoulder blades in a vest.  It is the next step that
Oliveira et al. (2026), "A low-cost GNSS-based electronic performance and
tracking system for sports", Results in Engineering 32, 112596,
doi:10.1016/j.rineng.2026.112596, set out as their future work - so each
block here answers one limitation that paper reports for its prototype:

  paper's prototype (Maduino Zero A9G)     this board
  ------------------------------------     ------------------------------------
  GPS only, 1 Hz logging                   u-blox NEO-M9N: GPS + Galileo +
                                           GLONASS + BeiDou, up to 25 Hz -
                                           the module the paper itself names
  no IMU ("does not eliminate the need     ISM330DHCX 6-axis IMU, +-16 g /
  for sensor fusion (IMU)")                +-4000 dps, on its own SPI bus
  satellites / HDOP not logged             UBX over UART: NAV-PVT carries
                                           numSV, pDOP and accuracy estimates
  devices aligned afterwards by            TIMEPULSE (PPS) into the MCU, so
  timestamp matching                       every pod samples on GNSS time
  microSD, raw CSV                         microSD kept: raw, open data
  GPRS for live data (unused)              nRF52840 BLE (Raytac MDBT50Q) and
                                           USB for download, no SIM needed
  3.7 V 1800 mAh Li-Po, >20 h              same cell, USB-C charging on board

The board is placed, not routed.  Everything that decides whether the GNSS
works - the patch, its ground plane, the 50 ohm feed, the matching pads, the
BLE antenna keep-out - is laid down here and checked by
``check_tracker.py``; the remaining digital and power connections are left as
ratsnest for routing in KiCad, where the router and DRC can see them.

    python3 kicad/tools/gen_tracker_project.py
"""

from __future__ import annotations

import copy
import json
import math
import pathlib
import sys
import uuid

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pcb_helpers as gp  # noqa: E402
from sexpr import Sym, dumps, find, find_all, num, parse  # noqa: E402

gp.NAMESPACE = uuid.UUID("3f6b2d0e-9c41-5a7e-b2d8-6a1c4e9f0b37")
gp.ROOT_UUID = gp.U("sheet", "root")
U = gp.U
LIB_NICK = "EPTS_Tracker"
PROJECT = "epts_football_tracker"
gp.PROJECT = PROJECT
gp.LIB_NICK = LIB_NICK

PRJ_DIR = gp.PRJ_DIR
LIB_DIR = gp.LIB_DIR
OUT_DIR = PRJ_DIR / "tracker"

TITLE = "Football GNSS tracker (EPTS pod) - NEO-M9N, ISM330DHCX, nRF52840, microSD"
DATE = "2026-10-01"

# ------------------------------------------------------------------- board
# 42 x 72 mm: inside the 54 x 80 mm enclosure the paper's prototype used,
# with the 25 mm patch across the top and the 1800 mAh cell behind the board.
BOARD_X0, BOARD_Y0 = 100.0, 60.0
BOARD_W, BOARD_H = 42.0, 72.0
BOARD_X1, BOARD_Y1 = BOARD_X0 + BOARD_W, BOARD_Y0 + BOARD_H


def B(x, y):
    """Board coordinates from the board's top-left corner."""
    return (round(BOARD_X0 + x, 4), round(BOARD_Y0 + y, 4))


# 4 layers, JLCPCB JLC04161H-7628 (1.6 mm): two GND planes, so the RF feed
# has a reference plane on whichever outer layer it runs.
PREPREG_H, PREPREG_ER = 0.2104, 4.4
CORE_H = 1.065
CU_OUTER, CU_INNER = 0.035, 0.0152
TAND = 0.02

# GNSS feed: grounded coplanar waveguide, 50 ohm on the 0.21 mm prepreg.
W_RF, GAP_RF = 0.38, 0.30
W_PWR = 0.4

# Patch antenna: AE1, footprint origin at the patch centre.
PATCH_C = (21.0, 15.0)
PATCH_HALF = 12.5
PATCH_KEEP = 1.0                 # nothing but ground within 1 mm of the patch

# RF chain, top layer, in board coordinates relative to the corner
RF_VIA = (21.0, 30.5)            # feed comes up from B.Cu here
Z3_AT = (22.6, 32.0)             # shunt, antenna side
Z2_AT = (21.0, 33.8)             # series, vertical
Z1_AT = (22.6, 35.4)             # shunt, receiver side
RF_CORNER_Y = 36.1               # level of U1 pad 11 after rotation
PI_GND_VIA_X = 24.1

NEO_AT = (10.5, 42.0, 180)       # pad 11 (RF_IN) lands at (16.5, 36.1)
MODULE_AT = (33.75, 58.0, 270)   # antenna end on the right board edge
SD_AT = (BOARD_W - 8.125, 41.0, 90)      # card slot opens on the right edge
USB_AT = (10.0, BOARD_H - 3.675, 0)      # receptacle face on the bottom edge
BAT_AT = (5.1, 56.0, 270)                # JST-PH opening on the left edge

NETCLASSES = {
    "GNSS_50R": dict(width=W_RF, clearance=GAP_RF, nets=["GNSS_ANT", "GNSS_RF"]),
    "Power": dict(width=W_PWR, clearance=0.2,
                  nets=["GND", "VBUS", "VBAT", "VSYS", "+3V3"]),
    "USB": dict(width=0.25, clearance=0.2, nets=["USB_DP", "USB_DN"]),
}


# ------------------------------------------------------------------- parts
def fp(name: str) -> str:
    return f"{LIB_NICK}:{name}"


R0402, C0402, C0603, C0805 = (fp("R_0402_1005Metric"), fp("C_0402_1005Metric"),
                              fp("C_0603_1608Metric"), fp("C_0805_2012Metric"))


def part(ref, sym, value, footprint, nets, sch, pcb=None, near=None, **kw):
    """One component.  *pcb* is a fixed (x, y, rot); *near* auto-places it
    next to (ref, pad) on the board.  Unlisted pins get a no-connect flag."""
    return dict(ref=ref, sym=sym, value=value, fp=footprint, nets=nets, sch=sch,
                pcb=pcb, near=near, **kw)


def rc(ref, sym, value, footprint, a, b, sch, near, **kw):
    """Two-terminal passive, drawn horizontally: pin 1 left, pin 2 right."""
    return part(ref, sym, value, footprint, {"1": a, "2": b},
                (sch[0], sch[1], 90), near=near, **kw)


PARTS = [
    # ---------------------------------------------------------------- GNSS
    part("U1", "NEO-M9N", "NEO-M9N-00B", fp("ublox_NEO"),
         {"1": "GNSS_SAFEBOOT_N", "3": "GNSS_PPS", "4": "GNSS_EXTINT",
          "7": "GND", "8": "GNSS_RESET_N", "10": "GND", "11": "GNSS_RF",
          "20": "GNSS_TXD", "21": "GNSS_RXD", "22": "+3V3", "23": "+3V3"},
         (76.2, 76.2, 0), pcb=NEO_AT,
         datasheet="https://www.u-blox.com/en/product/neo-m9n-module",
         desc="u-blox NEO-M9N, 92-channel GPS/GLONASS/Galileo/BeiDou, up to "
              "25 Hz navigation. UART for UBX/NMEA; D_SEL open selects "
              "UART + I2C; VDD_USB to GND because USB is not used"),
    part("AE1", "Antenna", "GNSS patch 25x25", fp("GNSS_Patch_25x25mm_SingleFeed"),
         {"1": "GNSS_ANT"}, (152.4, 114.3, 0), pcb=PATCH_C + (0,),
         desc="25 x 25 x 4 mm passive ceramic L1 patch, single feed pin, on "
              "the top GND pour. Feed offset per the chosen part's drawing"),
    rc("Z3", "C", "DNP", C0402, "GNSS_ANT", "GND", (152.4, 40.64), None, dnp=True,
       desc="Pi network, shunt on the antenna side. Not fitted; for "
            "retuning the patch inside the enclosure"),
    rc("Z2", "R", "0R", R0402, "GNSS_RF", "GNSS_ANT", (152.4, 50.8), None,
       desc="Pi network, series. 0 ohm link until a measured match says "
            "otherwise"),
    rc("Z1", "C", "DNP", C0402, "GNSS_RF", "GND", (152.4, 60.96), None, dnp=True,
       desc="Pi network, shunt on the receiver side. Not fitted"),
    rc("C1", "C", "100nF", C0402, "+3V3", "GND", (152.4, 71.12), ("U1", "23")),
    rc("C2", "C", "10uF", C0805, "+3V3", "GND", (152.4, 81.28), ("U1", "23")),
    part("TP1", "TestPoint", "SAFEBOOT_N", fp("TestPoint_Pad_D1.0mm"),
         {"1": "GNSS_SAFEBOOT_N"}, (152.4, 93.98, 0), pcb=(4.0, 20.0, 0),
         desc="u-blox SAFEBOOT_N: hold low at reset to recover the firmware"),

    # ------------------------------------------------------------------ MCU
    part("U2", "MDBT50Q-1MV2", "MDBT50Q-1MV2", fp("Raytac_MDBT50Q"),
         {"1": "GND", "28": "+3V3", "30": "+3V3", "32": "VBUS",
          "34": "USB_DN", "35": "USB_DP", "51": "SWDIO", "53": "SWDCLK",
          "40": "NRESET", "47": "SWO",
          "24": "GNSS_TXD", "22": "GNSS_RXD", "37": "GNSS_PPS",
          "36": "GNSS_EXTINT", "39": "GNSS_RESET_N",
          "44": "IMU_SCK", "43": "IMU_MOSI", "46": "IMU_MISO", "45": "IMU_CS",
          "48": "IMU_INT1", "49": "IMU_INT2",
          "19": "SD_SCK", "16": "SD_MOSI", "23": "SD_MISO", "27": "SD_CS",
          "29": "SD_DET", "11": "VBAT_SENSE", "57": "BTN", "58": "LED_K"},
         (254.0, 114.3, 0), pcb=MODULE_AT,
         datasheet="https://www.raytac.com/product/ins.php?index_id=89",
         desc="Raytac MDBT50Q-1MV2: nRF52840, BLE 5, USB, chip antenna. "
              "Normal voltage mode: VDD and VDDH both on 3V3, DCCH unused"),
    rc("C3", "C", "10uF", C0805, "+3V3", "GND", (325.12, 124.46), ("U2", "28")),
    rc("C4", "C", "100nF", C0402, "+3V3", "GND", (325.12, 132.08), ("U2", "28")),
    rc("C5", "C", "4.7uF", C0603, "VBUS", "GND", (325.12, 139.7), ("U2", "32")),
    rc("R10", "R", "1M", R0402, "VBAT", "VBAT_SENSE", (325.12, 147.32), ("U2", "11"),
       desc="Battery divider, top. 2.1 uA from the cell"),
    rc("R11", "R", "1M", R0402, "VBAT_SENSE", "GND", (325.12, 154.94), ("U2", "11"),
       desc="Battery divider, bottom: VBAT/2 into AIN0"),
    rc("C14", "C", "100nF", C0402, "VBAT_SENSE", "GND", (325.12, 162.56), ("U2", "11"),
       desc="Holds the divider for the SAADC's sample-and-hold"),
    part("J4", "Conn_ARM_SWD_TagConnect_TC2030-NL", "TC2030-IDC-NL",
         fp("Tag-Connect_TC2030-IDC-NL_2x03_P1.27mm_Vertical"),
         {"1": "+3V3", "2": "SWDIO", "3": "NRESET", "4": "SWDCLK", "5": "GND",
          "6": "SWO"},
         (370.84, 152.4, 0), pcb=(4.0, 9.0, 90),
         desc="SWD programming, no connector fitted"),
    rc("R12", "R", "470R", R0402, "+3V3", "LED_A", (325.12, 170.18), ("D2", "2")),
    part("D2", "LED", "green", fp("LED_0603_1608Metric"),
         {"1": "LED_K", "2": "LED_A"}, (325.12, 177.8, 0), pcb=(38.5, 17.0, 0),
         desc="Status LED, sunk by P1.07"),
    part("SW1", "SW_Push", "TL3342", fp("SW_SPST_TL3342"),
         {"1": "BTN", "2": "GND"}, (325.12, 187.96, 0), pcb=(38.5, 8.5, 90),
         desc="Start/stop and wake from System OFF (P1.06, internal pull-up)"),

    # ------------------------------------------------------------------ IMU
    part("U3", "ISM330DHCX", "ISM330DHCX",
         fp("LGA-14_3x2.5mm_P0.5mm_LayoutBorder3x4y"),
         {"1": "IMU_MISO", "2": "GND", "3": "GND", "4": "IMU_INT1",
          "5": "+3V3", "6": "GND", "8": "+3V3", "9": "IMU_INT2",
          "12": "IMU_CS", "13": "IMU_SCK", "14": "IMU_MOSI"},
         (76.2, 165.1, 0), pcb=(21.0, 45.0, 0),
         datasheet="https://www.st.com/resource/en/datasheet/ism330dhcx.pdf",
         desc="6-axis IMU, accelerometer to +-16 g and gyroscope to "
              "+-4000 dps, ODR to 6.67 kHz. SPI mode; the unused sensor-hub "
              "master pins SDx/SCx are tied to GND, OCS_Aux/SDO_Aux left open"),
    rc("C6", "C", "100nF", C0402, "+3V3", "GND", (139.7, 157.48), ("U3", "8")),
    rc("C7", "C", "100nF", C0402, "+3V3", "GND", (139.7, 165.1), ("U3", "5")),

    # -------------------------------------------------------------- microSD
    part("J3", "Micro_SD_Card_Det_Hirose_DM3AT", "DM3AT-SF-PEJM5",
         fp("microSD_HC_Hirose_DM3AT-SF-PEJM5"),
         {"1": "SD_DAT2", "2": "SD_CS", "3": "SD_MOSI", "4": "+3V3",
          "5": "SD_SCK", "6": "GND", "7": "SD_MISO", "8": "SD_DAT1",
          "9": "GND", "10": "SD_DET", "11": "GND"},
         (360.68, 76.2, 0), pcb=SD_AT,
         desc="microSD, SPI mode. Raw UBX + IMU logs, the open-data store"),
    rc("R1", "R", "47k", R0402, "+3V3", "SD_CS", (320.04, 25.4), ("J3", "2")),
    rc("R2", "R", "47k", R0402, "+3V3", "SD_DAT1", (320.04, 33.02), ("J3", "8"),
       desc="DAT1 unused in SPI mode: pulled up as the SD spec asks"),
    rc("R3", "R", "47k", R0402, "+3V3", "SD_DAT2", (320.04, 40.64), ("J3", "1"),
       desc="DAT2 unused in SPI mode: pulled up as the SD spec asks"),
    rc("R4", "R", "47k", R0402, "+3V3", "SD_MISO", (320.04, 48.26), ("J3", "7")),
    rc("C8", "C", "10uF", C0805, "+3V3", "GND", (383.54, 25.4), ("J3", "4")),
    rc("C9", "C", "100nF", C0402, "+3V3", "GND", (383.54, 33.02), ("J3", "4")),

    # ---------------------------------------------------------------- power
    part("J1", "USB_C_Receptacle_USB2.0_16P", "USB4105-GF-A",
         fp("USB_C_Receptacle_GCT_USB4105-xx-A_16P_TopMnt_Horizontal"),
         {"A1": "GND", "A4": "VBUS", "A5": "CC1", "A6": "USB_DP", "A7": "USB_DN",
          "B5": "CC2", "B6": "USB_DP", "B7": "USB_DN", "S1": "GND"},
         (50.8, 213.36, 0), pcb=USB_AT,
         desc="USB-C, USB 2.0 full speed: charging and log download"),
    rc("R5", "R", "5.1k", R0402, "CC1", "GND", (38.1, 269.24), ("J1", "A5"),
       desc="Rd: identifies the board as a USB-C sink"),
    rc("R6", "R", "5.1k", R0402, "CC2", "GND", (88.9, 269.24), ("J1", "B5"),
       desc="Rd: identifies the board as a USB-C sink"),
    part("U6", "USBLC6-2SC6", "USBLC6-2SC6", fp("SOT-23-6"),
         {"1": "USB_DP", "6": "USB_DP", "3": "USB_DN", "4": "USB_DN",
          "2": "GND", "5": "VBUS"},
         (114.3, 215.9, 0), pcb=(19.0, 66.2, 0),
         desc="ESD protection on D+/D- and VBUS"),
    part("U4", "MCP73831-2-OT", "MCP73831-2-OT", fp("SOT-23-5"),
         {"1": "CHG_STAT", "2": "GND", "3": "VBAT", "4": "VBUS", "5": "CHG_PROG"},
         (165.1, 215.9, 0), pcb=(14.5, 54.0, 0),
         desc="Single-cell Li-Po charger, 4.20 V. I_REG = 1000 V / R_PROG"),
    rc("C10", "C", "4.7uF", C0603, "VBUS", "GND", (139.7, 269.24), ("U4", "4")),
    rc("R7", "R", "2.0k", R0402, "CHG_PROG", "GND", (190.5, 269.24), ("U4", "5"),
       desc="R_PROG: 1000 V / 2.0 kohm = 500 mA, 0.28 C for 1800 mAh"),
    rc("C11", "C", "4.7uF", C0603, "VBAT", "GND", (241.3, 269.24), ("U4", "3")),
    part("D3", "LED", "orange", fp("LED_0603_1608Metric"),
         {"1": "CHG_LED", "2": "VBUS"}, (38.1, 281.94, 0), near=("U4", "1"),
         desc="Charging: STAT sinks while the charger is in fast charge"),
    rc("R8", "R", "1k", R0402, "CHG_LED", "CHG_STAT", (88.9, 281.94), ("U4", "1")),
    part("J2", "Conn_01x02_Pin", "Li-Po 1S", fp(
         "JST_PH_S2B-PH-SM4-TB_1x02-1MP_P2.00mm_Horizontal"),
         {"1": "VBAT", "2": "GND"}, (299.72, 218.44, 0), pcb=BAT_AT,
         desc="JST-PH battery connector, 3.7 V 1800 mAh cell with its own "
              "protection circuit. Check the cable's polarity: pin 1 is +"),
    part("Q1", "AO3401A", "AO3401A", fp("SOT-23"),
         {"1": "VBUS", "2": "VSYS", "3": "VBAT"},
         (205.74, 218.44, 0), pcb=(14.5, 59.5, 0),
         desc="Load sharing: off while VBUS is present, so the charger "
              "charges the cell instead of feeding the load through it"),
    rc("R9", "R", "100k", R0402, "VBUS", "GND", (139.7, 281.94), ("Q1", "1"),
       desc="Pulls Q1's gate low when USB is unplugged"),
    part("D1", "D_Schottky", "B5819WS", fp("D_SOD-323"),
         {"1": "VSYS", "2": "VBUS"}, (228.6, 200.66, 0), pcb=(19.5, 59.5, 0),
         desc="Feeds the system from USB while Q1 is off"),
    part("U5", "AP2112K-3.3", "AP2112K-3.3", fp("SOT-23-5"),
         {"1": "VSYS", "2": "GND", "3": "VSYS", "5": "+3V3"},
         (254.0, 218.44, 0), pcb=(21.5, 53.0, 0),
         desc="3.3 V 600 mA LDO, 55 uA quiescent"),
    rc("C12", "C", "4.7uF", C0603, "VSYS", "GND", (190.5, 281.94), ("U5", "1")),
    rc("C13", "C", "10uF", C0805, "+3V3", "GND", (241.3, 281.94), ("U5", "5")),
]

# nets that need an ERC power flag: nothing on them is a power output
PWR_FLAG_NETS = [("#FLG01", "GND", (350.52, 226.06)),
                 ("#FLG02", "VBUS", (365.76, 226.06)),
                 ("#FLG03", "VSYS", (381.0, 226.06))]

NOTES = [
    ((22.86, 17.78),
     "GNSS - u-blox NEO-M9N, 25 Hz max, four constellations\n"
     "UART (UBX-NAV-PVT) to the nRF52840; TIMEPULSE aligns every pod's\n"
     "samples to GNSS time, EXTINT and RESET_N are under MCU control.\n"
     "VDD_USB tied to GND: the module's USB is not used. D_SEL open.\n"
     "Passive 25 mm patch: the NEO-M9N has its own SAW + LNA.\n"
     "Z1-Z3: pi network, fitted as a 0R link, for tuning in the case."),
    ((22.86, 132.08),
     "IMU - ISM330DHCX on its own SPI bus, so 1-6.7 kHz IMU reads\n"
     "never wait for a microSD write. INT1/INT2 to the MCU."),
    ((198.12, 17.78),
     "MCU + BLE - Raytac MDBT50Q-1MV2 (nRF52840).\n"
     "BLE for live status/download, USB for bulk log download.\n"
     "P0.18 = nRESET, P1.00 = SWO (TC2030 Tag-Connect, no header).\n"
     "Battery: VBAT/2 on AIN0 (P0.02)."),
    ((294.64, 101.6),
     "microSD in SPI mode; DAT1/DAT2 pulled up, card detect\n"
     "switch to GND, read on P0.12 with the internal pull-up."),
    ((22.86, 246.38),
     "POWER - USB-C (5.1k Rd) -> MCP73831, 500 mA -> 1S Li-Po.\n"
     "Q1 + D1: load sharing, the system runs from USB when present.\n"
     "AP2112K-3.3 feeds everything; GNSS V_BCKP stays on 3V3 so\n"
     "System OFF keeps the ephemeris for a hot start."),
]

NC_SYMBOL_TYPES = {"no_connect"}


# ----------------------------------------------------------------- library
def load_library() -> dict:
    lib = parse((LIB_DIR / f"{LIB_NICK}.kicad_sym").read_text())
    return {str(c[1]): c for c in lib[1:] if isinstance(c, list) and c[0] == "symbol"}


SYMS = load_library()


def symbol_pins(name: str) -> list:
    """(number, name, type, x, y, angle, hidden) for every pin, library frame."""
    out = []

    def walk(node):
        for c in node:
            if isinstance(c, list):
                if c[0] == "pin":
                    at = find(c, "at")
                    hide = find(c, "hide")
                    out.append(dict(num=str(find(c, "number")[1]),
                                    name=str(find(c, "name")[1]), type=str(c[1]),
                                    x=float(at[1]), y=float(at[2]),
                                    angle=float(at[3]) if len(at) > 3 else 0.0,
                                    hidden=hide is not None and str(hide[1]) == "yes"))
                else:
                    walk(c)
    walk(SYMS[name])
    return out


def sch_pin(part, pin):
    """Sheet position of a pin's connection point, and its outward direction."""
    x, y, rot = part["sch"]
    r = math.radians(rot)
    rx = pin["x"] * math.cos(r) - pin["y"] * math.sin(r)
    ry = pin["x"] * math.sin(r) + pin["y"] * math.cos(r)
    out = math.radians(pin["angle"] + rot + 180)
    return ((round(x + rx, 3), round(y - ry, 3)),
            (round(math.cos(out)), -round(math.sin(out))))


def resolve_nets(part) -> dict:
    """Pin number -> net, with stacked pins sharing their location's net."""
    pins = symbol_pins(part["sym"])
    nets = dict(part["nets"])
    for pin in pins:
        if pin["num"] in nets:
            continue
        stacked = [p for p in pins if (p["x"], p["y"]) == (pin["x"], pin["y"])
                   and p["num"] in part["nets"]]
        if stacked:
            nets[pin["num"]] = part["nets"][stacked[0]["num"]]
    unknown = set(part["nets"]) - {p["num"] for p in pins}
    if unknown:
        raise SystemExit(f"{part['ref']}: no such pin(s) {sorted(unknown)}")
    return nets


for _p in PARTS:
    _p["all_nets"] = resolve_nets(_p)

NET_NAMES = sorted({n for p in PARTS for n in p["all_nets"].values()})
NETS = {"": 0}
NETS.update({name: i + 1 for i, name in enumerate(
    ["GND"] + [n for n in NET_NAMES if n != "GND"])})
gp.NETS = NETS


# --------------------------------------------------------------- schematic
def lib_symbols() -> list:
    used = sorted({p["sym"] for p in PARTS} | {"PWR_FLAG"})
    out = [Sym("lib_symbols")]
    for name in used:
        sym = copy.deepcopy(SYMS[name])
        sym[1] = f"{LIB_NICK}:{name}"
        out.append(sym)
    return out


def sch_symbol(part) -> list:
    x, y, rot = part["sch"]
    ref = part["ref"]
    # field positions: beside the body for ICs, above a horizontal passive
    if part["sym"] in ("R", "C"):
        ref_at, val_at = (x, y - 2.54, 0), (x, y + 2.54, 0)
        just = None
    else:
        top = max(p["y"] for p in symbol_pins(part["sym"]))
        ref_at = (x + 1.27, y - top - 1.27, 0)
        val_at = (x + 1.27, y - top + 1.27, 0)
        just = "left"
    node = [Sym("symbol"),
            [Sym("lib_id"), f"{LIB_NICK}:{part['sym']}"],
            [Sym("at"), num(x), num(y), num(rot)],
            [Sym("unit"), Sym("1")],
            [Sym("exclude_from_sim"), Sym("no")],
            [Sym("in_bom"), Sym("no" if part.get("dnp") else "yes")],
            [Sym("on_board"), Sym("yes")],
            [Sym("dnp"), Sym("yes" if part.get("dnp") else "no")],
            [Sym("uuid"), U("sym", ref)],
            gp.prop("Reference", ref, ref_at, justify=just),
            gp.prop("Value", part["value"], val_at, justify=just),
            gp.prop("Footprint", part["fp"], (x, y, 0), hide=True),
            gp.prop("Datasheet", part.get("datasheet", "~"), (x, y, 0), hide=True),
            gp.prop("Description", part.get("desc", ""), (x, y, 0), hide=True)]
    for pin in sorted(symbol_pins(part["sym"]), key=lambda p: p["num"]):
        node.append([Sym("pin"), pin["num"], [Sym("uuid"), U("pin", ref, pin["num"])]])
    node.append([Sym("instances"),
                 [Sym("project"), PROJECT,
                  [Sym("path"), f"/{gp.ROOT_UUID}",
                   [Sym("reference"), ref], [Sym("unit"), Sym("1")]]]])
    return node


def label(name, pos, direction, key):
    angle = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[direction]
    just = "left bottom" if angle in (0, 90) else "right bottom"
    return [Sym("label"), name,
            [Sym("at"), num(pos[0]), num(pos[1]), num(angle)],
            gp.effects(justify=just),
            [Sym("uuid"), U("label", key)]]


def wire(a, b):
    return [Sym("wire"),
            [Sym("pts"), [Sym("xy"), num(a[0]), num(a[1])],
             [Sym("xy"), num(b[0]), num(b[1])]],
            [Sym("stroke"), [Sym("width"), Sym("0")], [Sym("type"), Sym("default")]],
            [Sym("uuid"), U("wire", str(a), str(b))]]


STUB = 2.54


def pin_hookups(part):
    """Wire stub + label for every connected pin location, NC flag otherwise."""
    out = []
    seen = set()
    for pin in symbol_pins(part["sym"]):
        pos, direction = sch_pin(part, pin)
        if pos in seen:
            continue
        seen.add(pos)
        group = [p for p in symbol_pins(part["sym"])
                 if sch_pin(part, p)[0] == pos]
        nets = {part["all_nets"].get(p["num"]) for p in group}
        if len(nets) > 1:
            raise SystemExit(f"{part['ref']}: stacked pins at {pos} on {nets}")
        net = nets.pop()
        key = f"{part['ref']}.{pin['num']}"
        if net is None:
            if all(p["type"] in NC_SYMBOL_TYPES for p in group):
                continue
            out.append([Sym("no_connect"), [Sym("at"), num(pos[0]), num(pos[1])],
                        [Sym("uuid"), U("nc", key)]])
            continue
        end = (round(pos[0] + direction[0] * STUB, 3), round(pos[1] + direction[1] * STUB, 3))
        out.append(wire(pos, end))
        out.append(label(net, end, direction, key))
    return out


def pwr_flag(ref, net, pos) -> list:
    x, y = pos
    sym = [Sym("symbol"),
           [Sym("lib_id"), f"{LIB_NICK}:PWR_FLAG"],
           [Sym("at"), num(x), num(y), Sym("0")],
           [Sym("unit"), Sym("1")],
           [Sym("exclude_from_sim"), Sym("yes")],
           [Sym("in_bom"), Sym("no")],
           [Sym("on_board"), Sym("no")],
           [Sym("dnp"), Sym("no")],
           [Sym("uuid"), U("sym", ref)],
           gp.prop("Reference", ref, (x, y - 5.08, 0), hide=True),
           gp.prop("Value", "PWR_FLAG", (x, y - 3.81, 0)),
           gp.prop("Footprint", "", (x, y, 0), hide=True),
           gp.prop("Datasheet", "~", (x, y, 0), hide=True),
           gp.prop("Description", "ERC power source flag", (x, y, 0), hide=True),
           [Sym("pin"), "1", [Sym("uuid"), U("pin", ref, "1")]],
           [Sym("instances"),
            [Sym("project"), PROJECT,
             [Sym("path"), f"/{gp.ROOT_UUID}",
              [Sym("reference"), ref], [Sym("unit"), Sym("1")]]]]]
    end = (x, y + STUB)
    return [sym, wire((x, y), end), label(net, end, (0, 1), ref)]


def build_schematic() -> list:
    sch = [Sym("kicad_sch"),
           [Sym("version"), Sym("20250114")],
           [Sym("generator"), "gen_tracker_project.py"],
           [Sym("generator_version"), "9.0"],
           [Sym("uuid"), gp.ROOT_UUID],
           [Sym("paper"), "A3"],
           [Sym("title_block"),
            [Sym("title"), TITLE],
            [Sym("date"), DATE],
            [Sym("rev"), "A"],
            [Sym("comment"), Sym("1"), "After Oliveira et al. 2026, doi:10.1016/j.rineng.2026.112596 - their future work, built"],
            [Sym("comment"), Sym("2"), "Placed, RF routed; digital and power nets left as ratsnest"]],
           lib_symbols()]
    for i, (pos, text) in enumerate(NOTES):
        sch.append([Sym("text"), text,
                    [Sym("exclude_from_sim"), Sym("no")],
                    [Sym("at"), num(pos[0]), num(pos[1]), Sym("0")],
                    gp.effects(size=1.27, justify="left top"),
                    [Sym("uuid"), U("text", str(i))]])
    for p in PARTS:
        sch.extend(pin_hookups(p))
    for p in PARTS:
        sch.append(sch_symbol(p))
    for ref, net, pos in PWR_FLAG_NETS:
        sch.extend(pwr_flag(ref, net, pos))
    sch.append([Sym("sheet_instances"), [Sym("path"), "/", [Sym("page"), "1"]]])
    sch.append([Sym("embedded_fonts"), Sym("no")])
    return sch


# ------------------------------------------------------------------- board
def load_fp(name: str) -> list:
    return parse((LIB_DIR / f"{LIB_NICK}.pretty" / f"{name}.kicad_mod").read_text())


def xform(local, at):
    """Footprint-local point to board coordinates (KiCad: y down, CCW angle)."""
    x, y, rot = at
    r = math.radians(rot)
    return (round(x + local[0] * math.cos(r) + local[1] * math.sin(r), 4),
            round(y - local[0] * math.sin(r) + local[1] * math.cos(r), 4))


def courtyard(fp_node) -> list:
    """Courtyard bounding box corners, footprint-local."""
    xs, ys = [], []
    for c in fp_node:
        if not (isinstance(c, list) and c[0] in ("fp_line", "fp_rect", "fp_poly", "fp_circle")):
            continue
        if str(find(c, "layer")[1]) != "F.CrtYd":
            continue
        for key in ("start", "end", "center"):
            p = find(c, key)
            if p is not None:
                xs.append(float(p[1]))
                ys.append(float(p[2]))
        pts = find(c, "pts")
        if pts is not None:
            for xy in pts[1:]:
                xs.append(float(xy[1]))
                ys.append(float(xy[2]))
    return [(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))]


def bbox(points):
    return (min(p[0] for p in points), min(p[1] for p in points),
            max(p[0] for p in points), max(p[1] for p in points))


def overlaps(a, b, margin=0.0):
    return not (a[2] + margin <= b[0] or b[2] + margin <= a[0]
                or a[3] + margin <= b[1] or b[3] + margin <= a[1])


def pad_local(fp_node, number):
    for c in fp_node:
        if isinstance(c, list) and c[0] == "pad" and str(c[1]) == number:
            at = find(c, "at")
            return (float(at[1]), float(at[2]))
    raise KeyError(number)


# keep-out regions for the auto-placer, board-relative (x0, y0, x1, y1)
PATCH_BOX = (PATCH_C[0] - PATCH_HALF - PATCH_KEEP, PATCH_C[1] - PATCH_HALF - PATCH_KEEP,
             PATCH_C[0] + PATCH_HALF + PATCH_KEEP, PATCH_C[1] + PATCH_HALF + PATCH_KEEP)
RF_BOX = (16.0, 29.0, 25.0, 37.6)


def ble_keepout_rel():
    """The module's antenna keep-out, extended out to the board edge."""
    fpn = load_fp("Raytac_MDBT50Q")
    for z in find_all(fpn, "zone"):
        if find(z, "layers") is not None:
            pts = [(float(a[1]), float(a[2])) for a in find(find(z, "polygon"), "pts")[1:]]
            box = bbox([xform(p, MODULE_AT) for p in pts])
            return (box[0], box[1], BOARD_W + 0.5, box[3])
    raise SystemExit("MDBT50Q footprint has no all-layer keep-out")


BLE_BOX = ble_keepout_rel()


def place_parts():
    """Fixed parts first, then each passive as close as it fits to its pin."""
    placed = {}
    boxes = []
    for p in PARTS:
        p["fp_node"] = load_fp(p["fp"].split(":", 1)[1])
    for p in PARTS:
        if p["pcb"] is not None:
            placed[p["ref"]] = p["pcb"]
    # the pi network: pinned to the RF line
    placed["Z3"] = (Z3_AT[0], Z3_AT[1], 0)
    placed["Z2"] = (Z2_AT[0], Z2_AT[1], 90)
    placed["Z1"] = (Z1_AT[0], Z1_AT[1], 0)
    for ref, at in placed.items():
        p = next(q for q in PARTS if q["ref"] == ref)
        boxes.append((ref, bbox([xform(c, at) for c in courtyard(p["fp_node"])])))

    forbidden = [PATCH_BOX, RF_BOX, BLE_BOX]
    for p in PARTS:
        if p["ref"] in placed:
            continue
        ref_part, pad = p["near"]
        host = next(q for q in PARTS if q["ref"] == ref_part)
        if ref_part not in placed:
            raise SystemExit(f"{p['ref']}: place {ref_part} before it")
        target = xform(pad_local(host["fp_node"], pad), placed[ref_part])
        best = None
        step = 0.25
        for ring in range(0, 80):
            for i in range(-ring, ring + 1):
                for j in (-ring, ring) if abs(i) != ring else range(-ring, ring + 1):
                    for rot in (0, 90):
                        at = (round(target[0] + i * step, 3), round(target[1] + j * step, 3), rot)
                        box = bbox([xform(c, at) for c in courtyard(p["fp_node"])])
                        if (box[0] < 0.3 or box[1] < 0.3 or box[2] > BOARD_W - 0.3
                                or box[3] > BOARD_H - 0.3):
                            continue
                        if any(overlaps(box, f) for f in forbidden):
                            continue
                        if any(overlaps(box, b, 0.1) for _, b in boxes):
                            continue
                        d = math.dist(target, at[:2])
                        if best is None or d < best[0]:
                            best = (d, at, box)
            if best is not None and best[0] < (ring - 1) * step:
                break
        if best is None:
            raise SystemExit(f"{p['ref']}: no room near {ref_part}.{pad}")
        placed[p["ref"]] = best[1]
        boxes.append((p["ref"], best[2]))
    return placed


def board_footprint(p, at_rel) -> list:
    src = p["fp_node"]
    at = B(at_rel[0], at_rel[1]) + (at_rel[2],)
    x, y, rot = at
    out = [Sym("footprint"), f"{LIB_NICK}:{src[1]}",
           [Sym("layer"), "F.Cu"],
           [Sym("uuid"), U("fp", p["ref"])],
           [Sym("at"), num(x), num(y)] + ([num(rot)] if rot else [])]
    for child in src[2:]:
        head = child[0]
        if head in ("version", "generator", "generator_version", "layer", "embedded_fonts"):
            continue
        child = copy.deepcopy(child)
        if head == "property":
            if child[1] == "Reference":
                child[2] = p["ref"]
            elif child[1] == "Value":
                child[2] = p["value"]
            gp.rotate_at(child, rot)
        elif head == "fp_text":
            gp.rotate_at(child, rot)
        elif head == "pad":
            gp.rotate_at(child, rot)
            net = p["all_nets"].get(str(child[1]))
            if net is not None:
                child.append([Sym("net"), Sym(str(NETS[net])), net])
                child.append([Sym("pinfunction"), net])
                child.append([Sym("pintype"), "passive"])
        elif head == "attr" and p.get("dnp"):
            child.append(Sym("dnp"))
        elif head == "zone":
            # footprint rule areas are stored in board coordinates
            for pts in find_all(find(child, "polygon"), "pts"):
                for xy in pts[1:]:
                    bx, by = xform((float(xy[1]), float(xy[2])), at)
                    xy[1], xy[2] = num(bx), num(by)
        out.append(child)
    out += [[Sym("path"), f"/{U('sym', p['ref'])}"],
            [Sym("sheetname"), "Root"],
            [Sym("sheetfile"), f"{PROJECT}.kicad_sch"],
            [Sym("embedded_fonts"), Sym("no")]]
    return out


def seg(a, b, width, net, layer="F.Cu"):
    return gp.segment(B(*a), B(*b), width, net, layer)


def via(pos, net="GND"):
    node = gp.via(B(*pos), net)
    find(node, "layers")[1:] = ["F.Cu", "B.Cu"]
    return node


def zone(net, layer, points, name, priority=0):
    node = gp.gnd_zone(layer, [B(*p) for p in points])
    find(node, "net")[1] = Sym(str(NETS[net]))
    find(node, "net_name")[1] = net
    find(node, "uuid")[1] = U("zone", name)
    find(node, "name")[1] = name
    find(node, "priority")[1] = Sym(str(priority))
    find(node, "connect_pads")[1:] = [[Sym("clearance"), num(GAP_RF)]]
    return node


def rf_route():
    """Patch feed -> B.Cu CPWG -> via -> pi network -> NEO-M9N RF_IN."""
    patch = next(p for p in PARTS if p["ref"] == "AE1")
    feed = xform(pad_local(patch["fp_node"], "1"), PATCH_C + (0,))
    neo = next(p for p in PARTS if p["ref"] == "U1")
    rf_in = xform(pad_local(neo["fp_node"], "11"), NEO_AT)
    def pad(ref, number, at):
        node = next(p for p in PARTS if p["ref"] == ref)["fp_node"]
        return xform(pad_local(node, number), at)

    z2_rf, z2_ant = pad("Z2", "1", (*Z2_AT, 90)), pad("Z2", "2", (*Z2_AT, 90))
    z3_sig, z1_sig = pad("Z3", "1", (*Z3_AT, 0)), pad("Z1", "1", (*Z1_AT, 0))
    tracks = [
        (feed, RF_VIA, "GNSS_ANT", "B.Cu"),
        (RF_VIA, z2_ant, "GNSS_ANT", "F.Cu"),
        ((RF_VIA[0], Z3_AT[1]), z3_sig, "GNSS_ANT", "F.Cu"),
        (z2_rf, (Z2_AT[0], rf_in[1]), "GNSS_RF", "F.Cu"),
        ((Z2_AT[0], Z1_AT[1]), z1_sig, "GNSS_RF", "F.Cu"),
        ((Z2_AT[0], rf_in[1]), rf_in, "GNSS_RF", "F.Cu"),
    ]
    out = [seg(a, b, W_RF, net, layer) for a, b, net, layer in tracks]
    v = gp.via(B(*RF_VIA), "GNSS_ANT")
    find(v, "layers")[1:] = ["F.Cu", "B.Cu"]
    out.append(v)
    gnd_vias = []
    for ref, at in (("Z3", Z3_AT), ("Z1", Z1_AT)):
        out.append(seg(pad(ref, "2", (*at, 0)), (PI_GND_VIA_X, at[1]), W_PWR, "GND"))
        gnd_vias.append((PI_GND_VIA_X, at[1]))
    # via fence either side of the B.Cu run, and along the top-layer run
    fence = W_RF / 2 + GAP_RF + 0.7
    y = feed[1] + 2.0
    while y < RF_VIA[1] - 0.5:
        gnd_vias += [(feed[0] - fence, y), (feed[0] + fence, y)]
        y += 1.5
    gnd_vias += [(RF_VIA[0] - fence, RF_VIA[1]), (RF_VIA[0] - fence, Z3_AT[1]),
                 (RF_VIA[0] - fence, Z2_AT[1]), (RF_VIA[0] - fence, 35.0),
                 (18.5, rf_in[1] + fence), (18.5, rf_in[1] - fence)]
    return out, gnd_vias, feed, rf_in


def stitch_grid(placed, existing):
    """GND vias on a 3 mm grid wherever no part, RF line or keep-out is."""
    keep = []
    for p in PARTS:
        keep.append(bbox([xform(c, placed[p["ref"]]) for c in courtyard(p["fp_node"])]))
    keep += [RF_BOX, BLE_BOX,
             (PATCH_C[0] - 1.5, PATCH_C[1], PATCH_C[0] + 1.5, RF_VIA[1] + 1.0)]
    out = []
    y = 1.5
    while y < BOARD_H - 1.0:
        x = 1.5
        while x < BOARD_W - 1.0:
            free = not any(k[0] - 0.5 <= x <= k[2] + 0.5 and k[1] - 0.5 <= y <= k[3] + 0.5
                           for k in keep if k is not PATCH_BOX)
            # under the patch the vias are fine: the ceramic sits on tented copper
            in_patch = (PATCH_BOX[0] < x < PATCH_BOX[2] and PATCH_BOX[1] < y < PATCH_BOX[3])
            if in_patch:
                free = not any(k[0] - 0.5 <= x <= k[2] + 0.5 and k[1] - 0.5 <= y <= k[3] + 0.5
                               for k in keep[len(PARTS):])
                ae1 = xform((0, 0), PATCH_C + (0,))
                free = free and math.dist((x, y), (ae1[0], ae1[1] + 1.5)) > 2.5
            if free and all(math.dist((x, y), e) > 1.2 for e in existing):
                out.append((x, y))
            x += 3.0
        y += 3.0
    return out


def stackup():
    def layer(name, ltype, thickness=None, material=None, er=None, tand=None):
        node = [Sym("layer"), name, [Sym("type"), ltype]]
        if thickness is not None:
            node.append([Sym("thickness"), num(thickness)])
        if material:
            node.append([Sym("material"), material])
        if er is not None:
            node.append([Sym("epsilon_r"), num(er)])
        if tand is not None:
            node.append([Sym("loss_tangent"), num(tand)])
        return node

    return [Sym("stackup"),
            layer("F.SilkS", "Top Silk Screen"),
            layer("F.Paste", "Top Solder Paste"),
            layer("F.Mask", "Top Solder Mask", thickness=0.01),
            layer("F.Cu", "copper", thickness=CU_OUTER),
            layer("dielectric 1", "prepreg", PREPREG_H, "FR4", PREPREG_ER, TAND),
            layer("In1.Cu", "copper", thickness=CU_INNER),
            layer("dielectric 2", "core", CORE_H, "FR4", 4.6, TAND),
            layer("In2.Cu", "copper", thickness=CU_INNER),
            layer("dielectric 3", "prepreg", PREPREG_H, "FR4", PREPREG_ER, TAND),
            layer("B.Cu", "copper", thickness=CU_OUTER),
            layer("B.Mask", "Bottom Solder Mask", thickness=0.01),
            layer("B.Paste", "Bottom Solder Paste"),
            layer("B.SilkS", "Bottom Silk Screen"),
            [Sym("copper_finish"), "ENIG"],
            [Sym("dielectric_constraints"), Sym("no")]]


LAYERS = [(0, "F.Cu", "signal", None), (4, "In1.Cu", "signal", None),
          (6, "In2.Cu", "signal", None), (2, "B.Cu", "signal", None),
          (9, "F.Adhes", "user", "F.Adhesive"), (11, "B.Adhes", "user", "B.Adhesive"),
          (13, "F.Paste", "user", None), (15, "B.Paste", "user", None),
          (5, "F.SilkS", "user", "F.Silkscreen"), (7, "B.SilkS", "user", "B.Silkscreen"),
          (1, "F.Mask", "user", None), (3, "B.Mask", "user", None),
          (17, "Dwgs.User", "user", "User.Drawings"), (19, "Cmts.User", "user", "User.Comments"),
          (21, "Eco1.User", "user", "User.Eco1"), (23, "Eco2.User", "user", "User.Eco2"),
          (25, "Edge.Cuts", "user", None), (27, "Margin", "user", None),
          (31, "F.CrtYd", "user", "F.Courtyard"), (29, "B.CrtYd", "user", "B.Courtyard"),
          (35, "F.Fab", "user", None), (33, "B.Fab", "user", None)]


def build_board(placed) -> list:
    layer_nodes = [Sym("layers")]
    for number, name, ltype, alias in LAYERS:
        node = [Sym(str(number)), name, Sym(ltype)]
        if alias:
            node.append(alias)
        layer_nodes.append(node)
    pcb = [Sym("kicad_pcb"),
           [Sym("version"), Sym("20241229")],
           [Sym("generator"), "gen_tracker_project.py"],
           [Sym("generator_version"), "9.0"],
           [Sym("general"), [Sym("thickness"), num(1.6)],
            [Sym("legacy_teardrops"), Sym("no")]],
           [Sym("paper"), "A4"],
           [Sym("title_block"),
            [Sym("title"), TITLE],
            [Sym("date"), DATE],
            [Sym("rev"), "A"],
            [Sym("comment"), Sym("1"), "4 layer 1.6 mm (JLC04161H-7628): L2 and L3 solid GND"],
            [Sym("comment"), Sym("2"), f"GNSS feed: CPWG w = {W_RF} mm, gap {GAP_RF} mm, 50 ohm on the 0.21 mm prepreg"],
            [Sym("comment"), Sym("3"), "Placed and RF-routed only: route the ratsnest, then fill zones (B)"]],
           layer_nodes,
           [Sym("setup"), stackup(),
            [Sym("pad_to_mask_clearance"), Sym("0")],
            [Sym("allow_soldermask_bridges_in_footprints"), Sym("no")],
            [Sym("tenting"), Sym("front"), Sym("back")]]]
    for name, number in NETS.items():
        pcb.append([Sym("net"), Sym(str(number)), name])
    for p in PARTS:
        pcb.append(board_footprint(p, placed[p["ref"]]))

    corners = [(0, 0), (BOARD_W, 0), (BOARD_W, BOARD_H), (0, BOARD_H)]
    for i in range(4):
        pcb.append(gp.gr_line(B(*corners[i]), B(*corners[(i + 1) % 4]), "Edge.Cuts"))

    tracks, fence, _, _ = rf_route()
    pcb.extend(tracks)
    vias = fence + stitch_grid(placed, fence)
    for pos in vias:
        pcb.append(via(pos))

    inset = [(0.3, 0.3), (BOARD_W - 0.3, 0.3), (BOARD_W - 0.3, BOARD_H - 0.3),
             (0.3, BOARD_H - 0.3)]
    for layer in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"):
        pcb.append(zone("GND", layer, inset, f"GND_{layer.split('.')[0]}"))
    ble = gp.keepout_zone("BLE_ANTENNA_KEEPOUT",
                          [B(BLE_BOX[0], BLE_BOX[1]), B(BLE_BOX[2], BLE_BOX[1]),
                           B(BLE_BOX[2], BLE_BOX[3]), B(BLE_BOX[0], BLE_BOX[3])],
                          layers=("F.Cu", "In1.Cu", "In2.Cu", "B.Cu"))
    find(ble, "uuid")[1] = U("zone", "ble")
    pcb.append(ble)

    pcb.append(gp.gr_text("EPTS tracker rev A", B(1.0, BOARD_H - 9.5), "F.SilkS", size=0.8))
    pcb.append(gp.gr_text("+", B(1.2, BAT_AT[1] - 3.2), "F.SilkS", size=1.0))
    pcb.append(gp.gr_text("GNSS patch: sky side", B(PATCH_C[0], 0.9), "Cmts.User",
                          size=0.7, justify="center"))
    pcb.append(gp.gr_text("BLE antenna: no copper, any layer", B(BLE_BOX[0], BLE_BOX[1] - 0.6),
                          "Cmts.User", size=0.6))
    pcb.append([Sym("embedded_fonts"), Sym("no")])
    return pcb


# ----------------------------------------------------------------- project
def build_project() -> dict:
    gp.PROJECT = PROJECT
    gp.W50 = W_RF
    pro = gp.build_project()
    pro["meta"]["filename"] = f"{PROJECT}.kicad_pro"
    pro["sheets"] = [[gp.ROOT_UUID, "Root"]]
    rules = pro["board"]["design_settings"]["rules"]
    rules["min_clearance"] = 0.15
    pro["board"]["design_settings"]["track_widths"] = [0.0, 0.2, W_RF, W_PWR]
    classes = [c for c in pro["net_settings"]["classes"] if c["name"] == "Default"]
    patterns = []
    for priority, (name, nc) in enumerate(NETCLASSES.items()):
        cls = dict(classes[0])
        cls.update(name=name, clearance=nc["clearance"], track_width=nc["width"],
                   priority=priority)
        classes.append(cls)
        patterns += [{"netclass": name, "pattern": n} for n in nc["nets"]]
    pro["net_settings"]["classes"] = classes
    pro["net_settings"]["netclass_patterns"] = patterns
    return pro


def main() -> None:
    OUT_DIR.mkdir(exist_ok=True)
    placed = place_parts()
    sch_path = OUT_DIR / f"{PROJECT}.kicad_sch"
    pcb_path = OUT_DIR / f"{PROJECT}.kicad_pcb"
    pro_path = OUT_DIR / f"{PROJECT}.kicad_pro"
    sch_path.write_text(dumps(build_schematic()) + "\n")
    pcb_path.write_text(dumps(build_board(placed)) + "\n")
    pro_path.write_text(json.dumps(build_project(), indent=2) + "\n")
    (OUT_DIR / "sym-lib-table").write_text(
        "(sym_lib_table\n\t(version 7)\n"
        f'\t(lib (name "{LIB_NICK}")(type "KiCad")(uri "${{KIPRJMOD}}/../library/'
        f'{LIB_NICK}.kicad_sym")(options "")(descr "Football tracker parts, '
        'from the KiCad 9.0.9.1 libraries"))\n)\n')
    (OUT_DIR / "fp-lib-table").write_text(
        "(fp_lib_table\n\t(version 7)\n"
        f'\t(lib (name "{LIB_NICK}")(type "KiCad")(uri "${{KIPRJMOD}}/../library/'
        f'{LIB_NICK}.pretty")(options "")(descr "Football tracker footprints, '
        'from the KiCad 9.0.9.1 libraries plus the GNSS patch"))\n)\n')
    for path in (sch_path, pcb_path, pro_path):
        print(f"wrote {path.relative_to(PRJ_DIR.parent)}")


if __name__ == "__main__":
    main()
