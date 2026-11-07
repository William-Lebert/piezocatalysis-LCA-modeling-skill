# Model Specification Schema

Use the JSON template in `assets/templates/model_spec.template.json` as the software-neutral source of truth.

## Automated structural checks and limitations

Run `python scripts/validate_model_spec.py path/to/model.json`. The validator checks only a structural subset: required top-level fields and object types; functional-unit name, unit, service definition and finite positive amount; nonempty systems with unique names, mode and foreground inventory; and each inventory item's flow name, stage, direction, finite non-negative numeric value, unit, evidence class and source. The supplied draft template is structurally valid but contains placeholders and is not a complete study.

Recognized `replace-me` and `YYYY-MM-DD` placeholders produce warnings. Add `--reject-placeholders` to treat those warnings as errors. This option cannot identify all incomplete or illustrative data and does not verify scientific validity, functional-unit comparability, source quality, provider mappings, database licenses, lifetime assumptions, or results. Carry out the workflow's independent scientific and software QA even when the command passes.

Compared with the original 1.0.0 validator, foreground inventory entries must now include nonempty `stage`, `direction`, and `source` in addition to flow name, value, unit and evidence class. Update older files before validation; values must be JSON numbers, not numeric strings or booleans. The version-1.0 template already has these fields. Invalid JSON and non-standard NaN/Infinity constants are rejected.

## Required top-level fields

- `schema_version`
- `study`
- `functional_unit`
- `system_boundary`
- `systems`
- `lcia`
- `data_policy`

## Study

Record title, model tag, version, status, goal, decision context, geography, temporal scope, and intended application.

## Functional unit

Record name, amount, unit, service definition, reference flow, and calculation rule. A treatment functional unit must state influent conditions and the removal/outlet criterion.

## System boundary

Record included stages, excluded stages, cutoff rules, allocation, recycling approach, electricity scenario, and illumination decision.

## Systems

Each system must include:

- name and mode (`PZC`, `PC`, or `PPC`);
- catalyst identity;
- dry batch yield;
- preparation batch inventory;
- treatment-run inventory when applicable;
- kinetic data and source when applicable;
- catalyst lifetime/recovery;
- evidence class for every parameter.

## LCIA

Record software, version, database, database version, system model, LCIA methods, method versions, and calculation date.

## Data policy

Record allowed evidence classes, proxy policy, missing-data rule, confidentiality status, and public-release exclusions.
