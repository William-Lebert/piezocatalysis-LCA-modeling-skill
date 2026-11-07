# Evidence, Proxies, and Data Quality

## Contents

1. Evidence classes
2. Missing-data policy
3. Background mapping hierarchy
4. Data-quality scoring
5. Uncertainty and sensitivity
6. Provenance requirements

## 1. Evidence classes

Use one of five classes for every foreground value.

| Class | Definition | Reporting rule |
| --- | --- | --- |
| measured | directly measured in the present experiment | identify instrument, batch, and date when available |
| reported | copied from a supplied source or literature | cite exact table, figure, page, or dataset |
| calculated | derived only from measured/reported inputs | record equation and input identifiers |
| proxy | represented by another dataset or chemical route | state rationale, direction of expected bias, and sensitivity case |
| scenario | prospective or assumed operating condition | never merge with measured baseline without a label |

## 2. Missing-data policy

When a value is missing:

1. determine whether it is material to the decision;
2. search supplied experimental records and primary literature;
3. request the value if it could change the conclusion;
4. if work must continue, use a clearly labeled scenario or range;
5. test the value in sensitivity analysis;
6. never hide it inside a formula or process description.

Use laboratory-typical values only for exploratory screening. They are not publishable measurements unless verified.

## 3. Background mapping hierarchy

Apply this order:

1. exact chemical and technology dataset;
2. market dataset for the same chemical and grade;
3. stoichiometric construction from upstream chemicals;
4. chemically and functionally similar proxy;
5. mass- or energy-based generic proxy;
6. omission only with materiality evidence and an uncertainty bound.

For each mapping record:

- foreground flow and unit;
- selected dataset, database version, system model, geography, reference product, and unit;
- match type and evidence class;
- conversion factor;
- rationale and expected bias;
- alternative dataset for sensitivity analysis.

Do not select providers by name similarity alone. Inspect the reference product, production technology, geography, and sign convention.

The inventory template's `dataset_mapping` field may refer to a unique `mapping_id` in `dataset_mapping.template.csv`. For the inventory audit/scaling tool, use `exact`, `proxy` or `constructed` as match type, `pending` or `reviewed` as review status, and a conversion factor expressing dataset units per one foreground unit. The tool checks only a limited mass, volume and energy unit list; it does not establish that a dataset is scientifically appropriate or available. A reviewed status is supplied by the user, not verified by the script. Proxy and constructed mappings require a rationale and expected bias; record a sensitivity alternative where available. Old mapping CSVs need `mapping_id` and `rationale` columns before this tool can read them.

The tool reports unmapped included flows as warnings with null dataset amounts; an unknown mapping identifier or mismatched flow/unit is an error. A warning-bearing report is not a complete mapped inventory and must not be treated as one.

## 4. Data-quality scoring

Score reliability, completeness, temporal correlation, geographic correlation, and technological correlation. Use a pedigree matrix or an equivalent documented scheme. A proxy with high numerical precision is still low-confidence evidence.

Minimum publishable data-quality table:

- parameter/flow;
- value and unit;
- evidence class;
- source;
- year and geography;
- uncertainty distribution or range;
- data-quality score;
- influence on conclusions.

## 5. Uncertainty and sensitivity

Use distributions that reflect evidence:

- measured repeats: empirical, normal, or lognormal after checking support;
- reported ranges: triangular or uniform;
- positive background flows: lognormal is often appropriate;
- scenario values: discrete scenarios or wide bounded ranges.

Prioritize sensitivity for:

- equipment active power and utilization;
- synthesis yield;
- catalyst lifetime and recovery;
- electricity mix;
- solvent recovery;
- proxy dataset selection;
- treatment time and kinetic constant;
- scale-up energy intensity.

Do not run Monte Carlo merely to create error bars. First ensure that distributions, correlations, and structural scenarios are defensible.

## 6. Provenance requirements

Maintain:

- immutable raw-input archive;
- model specification version;
- assumptions log;
- dataset mapping table;
- software calculation manifest;
- process backup before automated writes;
- exported absolute result tables;
- script version or commit identifier.

Licensed databases, private experimental data, credentials, and license keys must not be included in a public release.
