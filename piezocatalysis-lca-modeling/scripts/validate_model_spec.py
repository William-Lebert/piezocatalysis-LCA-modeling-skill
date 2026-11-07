#!/usr/bin/env python3
"""Validate the structural subset of the software-neutral model specification."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REQUIRED_TOP = {"schema_version", "study", "functional_unit", "system_boundary", "systems", "lcia", "data_policy"}
MODES = {"PZC", "PC", "PPC"}
EVIDENCE = {"measured", "reported", "calculated", "proxy", "scenario"}


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _finite_number(value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_parameter(value: object, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: parameter must be an object")
        return
    for key in ("flow_name", "unit", "source", "stage"):
        if not _text(value.get(key)):
            errors.append(f"{path}.{key}: nonempty text is required")
    if value.get("direction") not in ("input", "output"):
        errors.append(f"{path}.direction: must be input or output")
    evidence = value.get("evidence_class")
    if not isinstance(evidence, str) or evidence not in EVIDENCE:
        errors.append(f"{path}.evidence_class: invalid evidence class")
    amount = value.get("value")
    if not _finite_number(amount) or amount < 0:
        errors.append(f"{path}.value: must be a finite, non-negative number")


def validate(data: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["model specification must be an object"]
    missing = REQUIRED_TOP - set(data)
    if missing:
        errors.append(f"missing top-level fields: {', '.join(sorted(missing))}")
    if not _text(data.get("schema_version")):
        errors.append("schema_version: nonempty text is required")
    for key in ("study", "functional_unit", "system_boundary", "lcia", "data_policy"):
        if not isinstance(data.get(key), dict):
            errors.append(f"{key}: must be an object")
    fu = data.get("functional_unit")
    if isinstance(fu, dict):
        for key in ("name", "unit", "service_definition"):
            if not _text(fu.get(key)):
                errors.append(f"functional_unit.{key}: nonempty text is required")
        amount = fu.get("amount")
        if not _finite_number(amount) or amount <= 0:
            errors.append("functional_unit.amount: must be a finite, positive number")
    systems = data.get("systems")
    if not isinstance(systems, list) or not systems:
        errors.append("systems must be a non-empty list")
        return errors
    names: set[str] = set()
    for index, system in enumerate(systems):
        prefix = f"systems[{index}]"
        if not isinstance(system, dict):
            errors.append(f"{prefix}: must be an object")
            continue
        name = system.get("name")
        if not _text(name):
            errors.append(f"{prefix}.name: nonempty text is required")
        elif name in names:
            errors.append(f"{prefix}.name duplicates {name!r}")
        else:
            names.add(name)
        mode = system.get("mode")
        if not isinstance(mode, str) or mode not in MODES:
            errors.append(f"{prefix}.mode must be PZC, PC, or PPC")
        inventory = system.get("foreground_inventory")
        if not isinstance(inventory, list) or not inventory:
            errors.append(f"{prefix}.foreground_inventory must be non-empty")
        else:
            for item_index, item in enumerate(inventory):
                validate_parameter(item, f"{prefix}.foreground_inventory[{item_index}]", errors)
    return errors


def placeholders(data: object, path: str = "$") -> list[str]:
    if isinstance(data, dict):
        return [result for key, value in data.items() for result in placeholders(value, f"{path}.{key}")]
    if isinstance(data, list):
        return [result for index, value in enumerate(data) for result in placeholders(value, f"{path}[{index}]")]
    if isinstance(data, str) and ("replace-me" in data.lower() or data == "YYYY-MM-DD"):
        return [path]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("model_spec", type=Path)
    parser.add_argument("--reject-placeholders", action="store_true", help="reject recognized placeholder strings")
    args = parser.parse_args()
    try:
        def reject_constant(value: str) -> None:
            raise ValueError(f"non-standard JSON numeric constant {value}")
        data = json.loads(args.model_spec.read_text(encoding="utf-8"), parse_constant=reject_constant)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        print(f"ERROR: cannot read model specification: {exc}", file=sys.stderr)
        return 1
    errors = validate(data)
    missing = placeholders(data)
    for path in missing:
        print(f"WARNING: placeholder at {path}")
    if args.reject_placeholders and missing:
        errors.append("recognized placeholders remain")
    for item in errors:
        print(f"ERROR: {item}")
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        return 1
    print("PASS: checked structural subset; scientific completeness is not assessed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
