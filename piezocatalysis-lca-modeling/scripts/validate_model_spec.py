#!/usr/bin/env python3
"""Validate the software-neutral piezocatalysis LCA model specification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REQUIRED_TOP = {
    "schema_version",
    "study",
    "functional_unit",
    "system_boundary",
    "systems",
    "lcia",
    "data_policy",
}
MODES = {"PZC", "PC", "PPC"}
EVIDENCE = {"measured", "reported", "calculated", "proxy", "scenario"}


def validate_parameter(value: object, path: str, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"{path}: parameter must be an object")
        return
    if "value" not in value or "unit" not in value or "evidence_class" not in value:
        errors.append(f"{path}: requires value, unit, and evidence_class")
        return
    if value["evidence_class"] not in EVIDENCE:
        errors.append(f"{path}: invalid evidence_class {value['evidence_class']!r}")
    if isinstance(value["value"], (int, float)) and value["value"] < 0:
        errors.append(f"{path}: value must be non-negative")


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    missing = REQUIRED_TOP - set(data)
    if missing:
        errors.append(f"missing top-level fields: {', '.join(sorted(missing))}")

    fu = data.get("functional_unit", {})
    for key in ("name", "amount", "unit", "service_definition"):
        if key not in fu:
            errors.append(f"functional_unit.{key} is required")
    if isinstance(fu.get("amount"), (int, float)) and fu["amount"] <= 0:
        errors.append("functional_unit.amount must be positive")

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
        if not name:
            errors.append(f"{prefix}.name is required")
        elif name in names:
            errors.append(f"{prefix}.name duplicates {name!r}")
        else:
            names.add(name)
        if system.get("mode") not in MODES:
            errors.append(f"{prefix}.mode must be PZC, PC, or PPC")
        inventory = system.get("foreground_inventory")
        if not isinstance(inventory, list) or not inventory:
            errors.append(f"{prefix}.foreground_inventory must be non-empty")
        else:
            for item_index, item in enumerate(inventory):
                validate_parameter(item, f"{prefix}.foreground_inventory[{item_index}]", errors)
                if isinstance(item, dict) and not item.get("flow_name"):
                    errors.append(f"{prefix}.foreground_inventory[{item_index}].flow_name is required")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("model_spec", type=Path)
    args = parser.parse_args()
    data = json.loads(args.model_spec.read_text(encoding="utf-8"))
    errors = validate(data)
    for item in errors:
        print(f"ERROR: {item}")
    if errors:
        print(f"FAILED: {len(errors)} error(s)")
        return 1
    print("PASS: model specification is structurally valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
