#!/usr/bin/env python3
"""Deterministic calculation helpers for piezocatalysis LCA and EE/O."""

from __future__ import annotations

import argparse
import math


def removal_fraction(kobs_min_inv: float, time_min: float) -> float:
    if kobs_min_inv <= 0 or time_min < 0:
        raise ValueError("kobs must be positive and time must be non-negative")
    return 1.0 - math.exp(-kobs_min_inv * time_min)


def removed_mass_mg(c0_mg_l: float, volume_l: float, fraction: float) -> float:
    if c0_mg_l < 0 or volume_l <= 0 or not 0 <= fraction <= 1:
        raise ValueError("invalid concentration, volume, or removal fraction")
    return c0_mg_l * volume_l * fraction


def eeo_kwh_m3_order(power_kw: float, volume_l: float, kobs_min_inv: float) -> float:
    if power_kw < 0 or volume_l <= 0 or kobs_min_inv <= 0:
        raise ValueError("power must be non-negative; volume and kobs must be positive")
    return 1000.0 * math.log(10.0) * power_kw / (60.0 * volume_l * kobs_min_inv)


def batch_energy_kwh(power_kw: float, time_h: float) -> float:
    if power_kw < 0 or time_h < 0:
        raise ValueError("power and time must be non-negative")
    return power_kw * time_h


def preparation_share(catalyst_dose_g: float, dry_batch_yield_g: float) -> float:
    if catalyst_dose_g < 0 or dry_batch_yield_g <= 0:
        raise ValueError("dose must be non-negative and dry yield must be positive")
    return catalyst_dose_g / dry_batch_yield_g


def treatment_scale(target_removed_mg: float, removed_per_run_mg: float) -> float:
    if target_removed_mg <= 0 or removed_per_run_mg <= 0:
        raise ValueError("removed masses must be positive")
    return target_removed_mg / removed_per_run_mg


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    eeo = sub.add_parser("eeo")
    eeo.add_argument("--power-kw", type=float, required=True)
    eeo.add_argument("--volume-l", type=float, required=True)
    eeo.add_argument("--kobs-min-1", type=float, required=True)

    removal = sub.add_parser("removal")
    removal.add_argument("--kobs-min-1", type=float, required=True)
    removal.add_argument("--time-min", type=float, required=True)
    removal.add_argument("--c0-mg-l", type=float, required=True)
    removal.add_argument("--volume-l", type=float, required=True)

    energy = sub.add_parser("energy")
    energy.add_argument("--power-kw", type=float, required=True)
    energy.add_argument("--time-h", type=float, required=True)

    scale = sub.add_parser("scale")
    scale.add_argument("--target-removed-mg", type=float, required=True)
    scale.add_argument("--removed-per-run-mg", type=float, required=True)
    scale.add_argument("--catalyst-dose-g", type=float, required=True)
    scale.add_argument("--dry-batch-yield-g", type=float, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "eeo":
        print(f"{eeo_kwh_m3_order(args.power_kw, args.volume_l, args.kobs_min_1):.12g}")
    elif args.command == "removal":
        fraction = removal_fraction(args.kobs_min_1, args.time_min)
        mass = removed_mass_mg(args.c0_mg_l, args.volume_l, fraction)
        print(f"removal_fraction={fraction:.12g}")
        print(f"removed_mass_mg={mass:.12g}")
    elif args.command == "energy":
        print(f"{batch_energy_kwh(args.power_kw, args.time_h):.12g}")
    else:
        runs = treatment_scale(args.target_removed_mg, args.removed_per_run_mg)
        share = preparation_share(args.catalyst_dose_g, args.dry_batch_yield_g)
        print(f"runs_per_FU={runs:.12g}")
        print(f"batch_share_per_run={share:.12g}")
        print(f"batch_share_per_FU={runs * share:.12g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
