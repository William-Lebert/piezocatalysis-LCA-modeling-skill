#!/usr/bin/env python3
"""Validate a piezocatalysis foreground inventory CSV."""

from __future__ import annotations

import argparse
import csv
import math
import sys
from pathlib import Path


REQUIRED = {
    "system",
    "stage",
    "flow_name",
    "amount",
    "unit",
    "direction",
    "evidence_class",
    "source",
    "dataset_mapping",
    "included",
    "note",
}
EVIDENCE = {"measured", "reported", "calculated", "proxy", "scenario"}
DIRECTIONS = {"input", "output"}
BOOLEAN = {"true", "false", "1", "0", "yes", "no"}


def validate(path: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = set(reader.fieldnames or [])
        if len(reader.fieldnames or []) != len(fields):
            return ["duplicate column names"], []
        missing = REQUIRED - fields
        if missing:
            return [f"missing required columns: {', '.join(sorted(missing))}"], []

        for row_no, row in enumerate(reader, start=2):
            if None in row or any(value is None for value in row.values()):
                errors.append(f"row {row_no}: incorrect number of columns")
                continue
            label = f"row {row_no} ({row.get('system','?')} / {row.get('flow_name','?')})"
            try:
                amount = float(row["amount"])
                if not math.isfinite(amount):
                    errors.append(f"{label}: amount must be finite")
                elif amount < 0:
                    errors.append(f"{label}: negative amount requires an explicit credit workflow")
            except ValueError:
                errors.append(f"{label}: amount is not numeric")

            if row["direction"].strip().lower() not in DIRECTIONS:
                errors.append(f"{label}: direction must be input or output")
            evidence = row["evidence_class"].strip().lower()
            if evidence not in EVIDENCE:
                errors.append(f"{label}: invalid evidence_class {evidence!r}")
            if row["included"].strip().lower() not in BOOLEAN:
                errors.append(f"{label}: included must be a boolean value")
            if not row["unit"].strip():
                errors.append(f"{label}: unit is blank")
            for field in ("system", "stage", "flow_name", "source"):
                if not row[field].strip():
                    errors.append(f"{label}: {field} is blank")
            if "replace-me" in row["source"].lower():
                warnings.append(f"{label}: source contains placeholder")
            if evidence == "proxy" and not row["dataset_mapping"].strip():
                errors.append(f"{label}: proxy value requires dataset_mapping")
            if row["included"].strip().lower() in {"false", "0", "no"} and not row["note"].strip():
                warnings.append(f"{label}: excluded flow has no rationale in note")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("inventory", type=Path)
    args = parser.parse_args()
    try:
        errors, warnings = validate(args.inventory)
    except (OSError, UnicodeError, csv.Error) as exc:
        print(f"ERROR: cannot read inventory: {exc}", file=sys.stderr)
        return 1
    for item in warnings:
        print(f"WARNING: {item}")
    for item in errors:
        print(f"ERROR: {item}")
    if errors:
        print(f"FAILED: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"PASS: 0 errors, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
