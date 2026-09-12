#!/usr/bin/env python3
"""Characteristic impedance of this board's transmission lines.

Two geometries matter on an RF board like this one:

  microstrip  a track over a solid plane, which is the feed line
  CPWG        a track with coplanar ground either side *and* a plane below,
              which is what an end-launch SMA footprint makes at the launch

Both are closed-form.  Microstrip uses Hammerstad's synthesis/analysis pair
with Wheeler's thickness correction; CPWG uses the conformal mapping result
(Ghione/Naldi), with the complete elliptic integral K(k) evaluated exactly by
the arithmetic-geometric mean rather than a series approximation.

    python3 line_impedance.py                 # this board
    python3 line_impedance.py -w 1.2 -s 0.5   # try other dimensions
"""

from __future__ import annotations

import argparse
import math

Z_FREE_SPACE = 376.730313668


def agm(a: float, b: float, tol: float = 1e-15) -> float:
    while abs(a - b) > tol * abs(a):
        a, b = (a + b) / 2, math.sqrt(a * b)
    return (a + b) / 2


def ellipk(k: float) -> float:
    """Complete elliptic integral of the first kind, modulus k."""
    return math.pi / (2 * agm(1.0, math.sqrt(1.0 - k * k)))


def k_ratio(k: float) -> float:
    """K(k) / K(k'), the ratio conformal mapping formulas are written in."""
    return ellipk(k) / ellipk(math.sqrt(1.0 - k * k))


def microstrip(w: float, h: float, er: float, t: float = 0.0) -> tuple[float, float]:
    """Hammerstad analysis, Wheeler thickness correction. -> (Z0, eps_eff)"""
    if t > 0:
        w = w + (t / math.pi) * (1 + math.log(2 * h / t))
    u = w / h
    if u >= 1:
        eps = (er + 1) / 2 + (er - 1) / 2 / math.sqrt(1 + 12 / u)
        z0 = Z_FREE_SPACE / math.sqrt(eps) / (u + 1.393 + 0.667 * math.log(u + 1.444))
    else:
        eps = (er + 1) / 2 + (er - 1) / 2 * (
            1 / math.sqrt(1 + 12 / u) + 0.04 * (1 - u) ** 2)
        z0 = 60 / math.sqrt(eps) * math.log(8 / u + u / 4)
    return z0, eps


def cpwg(w: float, s: float, h: float, er: float) -> tuple[float, float]:
    """Coplanar waveguide with a lower ground plane. -> (Z0, eps_eff)"""
    k1 = w / (w + 2 * s)
    k3 = (math.tanh(math.pi * w / (4 * h))
          / math.tanh(math.pi * (w + 2 * s) / (4 * h)))
    r1, r3 = k_ratio(k1), k_ratio(k3)
    q = r3 / r1                      # [K(k1')/K(k1)] * [K(k3)/K(k3')]
    eps = (1 + er * q) / (1 + q)
    z0 = 60 * math.pi / (math.sqrt(eps) * (r1 + r3))
    return z0, eps


def synthesise_microstrip(z_target: float, h: float, er: float, t: float) -> float:
    """Track width that gives *z_target* ohm, by bisection on the analysis."""
    lo, hi = 0.05 * h, 20 * h
    for _ in range(200):
        mid = (lo + hi) / 2
        if microstrip(mid, h, er, t)[0] > z_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-w", "--width", type=float, default=1.5, help="track width [mm]")
    ap.add_argument("-s", "--gap", type=float, default=0.8,
                    help="coplanar ground gap at the launch [mm]")
    ap.add_argument("--h", type=float, default=0.8, help="dielectric height [mm]")
    ap.add_argument("--er", type=float, default=4.4, help="relative permittivity")
    ap.add_argument("--t", type=float, default=0.035, help="copper thickness [mm]")
    ap.add_argument("--freq", type=float, default=2.45e9, help="frequency [Hz]")
    args = ap.parse_args()
    w, s, h, er, t = args.width, args.gap, args.h, args.er, args.t

    print(f"stackup        : {h} mm, er {er}, {t * 1000:.0f} um copper, "
          f"{args.freq / 1e9:.2f} GHz\n")
    for label, (z0, eps) in (
            ("microstrip, no thickness", microstrip(w, h, er)),
            (f"microstrip, t = {t} mm", microstrip(w, h, er, t)),
            (f"CPWG, gap {s} mm", cpwg(w, s, h, er)),
    ):
        lam = 299792458.0 / (args.freq * math.sqrt(eps)) * 1e3
        print(f"  {label:26s} w = {w} mm -> Z0 = {z0:5.1f} ohm   "
              f"eps_eff = {eps:.3f}   lambda_g = {lam:.1f} mm")
    print(f"\n  50 ohm microstrip width      -> {synthesise_microstrip(50, h, er, t):.2f} mm")


if __name__ == "__main__":
    main()
