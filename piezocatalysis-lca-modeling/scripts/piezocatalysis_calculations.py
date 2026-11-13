#!/usr/bin/env python3
"""Deterministic calculation helpers for piezocatalysis LCA and EE/O."""

from __future__ import annotations

import argparse
import math
import sys


def _finite(*values: float) -> None:
    if not all(math.isfinite(value) for value in values):
        raise ValueError("all inputs and results must be finite")


def _result(value: float) -> float:
    _finite(value)
    return value


def _nonzero_result(value: float, *inputs: float) -> float:
    value = _result(value)
    if value == 0 and all(item != 0 for item in inputs):
        raise ValueError("result is too small to calculate without underflow")
    return value


def removal_fraction(kobs_min_inv: float, time_min: float) -> float:
    _finite(kobs_min_inv, time_min)
    if kobs_min_inv <= 0 or time_min < 0:
        raise ValueError("kobs must be positive and time must be non-negative")
    return _nonzero_result(-math.expm1(-kobs_min_inv * time_min), kobs_min_inv, time_min)


def removed_mass_mg(c0_mg_l: float, volume_l: float, fraction: float) -> float:
    _finite(c0_mg_l, volume_l, fraction)
    if c0_mg_l < 0 or volume_l <= 0 or not 0 <= fraction <= 1:
        raise ValueError("invalid concentration, volume, or removal fraction")
    if c0_mg_l == 0 or fraction == 0:
        return 0.0
    return _nonzero_result(c0_mg_l * volume_l * fraction, c0_mg_l, volume_l, fraction)


def eeo_kwh_m3_order(power_kw: float, volume_l: float, kobs_min_inv: float) -> float:
    _finite(power_kw, volume_l, kobs_min_inv)
    if power_kw < 0 or volume_l <= 0 or kobs_min_inv <= 0:
        raise ValueError("power must be non-negative; volume and kobs must be positive")
    try:
        numerator = _result(1000.0 * math.log(10.0) * power_kw)
        denominator = _result(_result(60.0 * volume_l) * kobs_min_inv)
        if power_kw and numerator == 0:
            raise ValueError("EE/O numerator is too small to calculate")
        result = _result(numerator / denominator)
        if power_kw and result == 0:
            raise ValueError("EE/O result is too small to calculate")
        return result
    except ZeroDivisionError as exc:
        raise ValueError("EE/O denominator is too small to calculate") from exc


def batch_energy_kwh(power_kw: float, time_h: float) -> float:
    _finite(power_kw, time_h)
    if power_kw < 0 or time_h < 0:
        raise ValueError("power and time must be non-negative")
    return _nonzero_result(power_kw * time_h, power_kw, time_h)


def preparation_share(catalyst_dose_g: float, dry_batch_yield_g: float) -> float:
    _finite(catalyst_dose_g, dry_batch_yield_g)
    if catalyst_dose_g < 0 or dry_batch_yield_g <= 0:
        raise ValueError("dose must be non-negative and dry yield must be positive")
    return _nonzero_result(catalyst_dose_g / dry_batch_yield_g, catalyst_dose_g)


def treatment_scale(target_removed_mg: float, removed_per_run_mg: float) -> float:
    _finite(target_removed_mg, removed_per_run_mg)
    if target_removed_mg <= 0 or removed_per_run_mg <= 0:
        raise ValueError("removed masses must be positive")
    return _nonzero_result(target_removed_mg / removed_per_run_mg, target_removed_mg)


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
        total_share = _nonzero_result(runs * share, runs, share)
        print(f"runs_per_FU={runs:.12g}")
        print(f"batch_share_per_run={share:.12g}")
        print(f"batch_share_per_FU={total_share:.12g}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OverflowError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
