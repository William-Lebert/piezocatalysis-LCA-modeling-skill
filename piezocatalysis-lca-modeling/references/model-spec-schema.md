# Model Specification Schema

Use the JSON template in `assets/templates/model_spec.template.json` as the software-neutral source of truth.

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
