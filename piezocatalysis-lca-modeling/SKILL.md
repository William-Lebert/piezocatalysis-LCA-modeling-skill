---
name: piezocatalysis-lca-modeling
description: Research-grade life-cycle assessment workflows for piezocatalysis, photocatalysis, and piezo-photocatalysis studies. Use when Codex must define a functional unit and system boundary, convert laboratory catalyst-synthesis and pollutant-treatment data into a traceable LCI, calculate EE/O from kinetics, map foreground inputs to licensed background databases, build or audit models in openLCA or SimaPro, compare PZC/PC/PPC routes or catalysts, run sensitivity and uncertainty analyses, troubleshoot IPC/COM/Excel-link workflows, or prepare SCI-quality LCA methods, tables, figures, and supporting information.
---

# Piezocatalysis LCA Modeling

## Purpose

Build transparent and reproducible LCA models for piezocatalytic materials and water-treatment systems. Support both openLCA and SimaPro while keeping the scientific model independent of either software.

## Non-negotiable rules

1. Preserve raw experimental files and model a copy.
2. Classify every value as `measured`, `reported`, `calculated`, `proxy`, or `scenario`.
3. Never present a proxy, scenario, or literature value as an experimental measurement.
4. Never preselect the environmentally preferred catalyst or force a narrative.
5. Do not compare results unless functional unit, boundary, database system model, LCIA method, geography, and allocation rules are compatible.
6. Keep absolute LCIA results as the source of truth. Use normalized plots only as visualization aids.
7. Separate preparation electricity, treatment electricity, and EE/O power terms.
8. Include or exclude illumination only through an explicit causal boundary decision; document both the decision and a sensitivity case when it can affect conclusions.
9. Back up processes and record stable identifiers before automated software writes.
10. Do not modify proprietary database files directly or redistribute licensed databases.

## Workflow

### 1. Intake and evidence audit

- Collect experimental recipes, yields, washing and separation steps, equipment power, run time, catalyst dose, pollutant concentration and volume, kinetic constants, reuse data, and end-of-life assumptions.
- Create an assumptions log and dataset-mapping table from `assets/templates/`.
- Run `scripts/validate_inventory.py` before software import.
- Read `references/evidence-and-data-quality.md` whenever data are incomplete, literature-derived, or represented by a proxy.

### 2. Define the comparison

- Select one functional-unit family:
  - catalyst production: mass of dry catalyst at the factory/laboratory gate;
  - treatment service: mass of pollutant removed under a defined influent and treatment condition;
  - water service: volume treated to a defined outlet quality;
  - kinetic electricity metric: one order of pollutant reduction for EE/O.
- Define whether the study compares PZC, PC, PPC, catalyst chemistries, synthesis routes, or scale-up scenarios.
- Read `references/piezocatalysis-methodology.md` before finalizing functional unit, energy boundary, catalyst lifetime, or mode-specific power terms.

### 3. Build the foreground LCI

- Convert each synthesis recipe into a batch process with an explicit dry catalyst output.
- Record precursors, solvents, washing media, hydrothermal/annealing/drying energy, centrifugation or filtration, yield, recovery, and waste treatment.
- Build treatment processes separately from catalyst preparation.
- Scale preparation burden through catalyst demand and lifetime; scale treatment burden through pollutant removal or treated-water service.
- Use `scripts/piezocatalysis_calculations.py` for kinetic removal, EE/O, batch energy, and functional-unit scaling checks.
- For a pollutant-removal service with equal performance per run and a justified effective-use assumption, `scripts/audit_and_scale_inventory.py` can audit and scale the foreground inventory; see `assets/examples/synthetic-treatment/README.md`. Treat warnings and unmapped flows as unresolved, and use cycle-by-cycle modeling when those assumptions do not hold.

### 4. Map background datasets

- Prefer exact substance and technology matches, then stoichiometric construction, then transparent functional proxies.
- Record dataset name, database version, system model, geography, unit, provider, proxy rationale, and expected bias.
- Do not silently omit unmatched chemicals. Flag them for sensitivity analysis.
- Validate unit conversion and reference-product direction before linking providers.

### 5. Execute in the selected software

- For openLCA, read `references/openlca-workflow.md` and use the UI or IPC only after confirming the active database and LCIA methods.
- For local read-only discovery or calculation of existing product systems, use `scripts/openlca_readonly.py` only after confirming database, UUIDs, functional unit and software context. It does not verify user-supplied database or unit labels; review warnings and verify result metadata independently.
- For SimaPro, read `references/simapro-workflow.md`. Probe Direct Import, Excel external links, and COM authorization separately; a Developer installation does not by itself prove COM entitlement.
- Keep a software-neutral model specification as the authoritative record.

### 6. Calculate and audit

- Calculate absolute midpoint results and energy-demand results first.
- Verify reference flows, target units, provider links, signs, scaling factors, mass balance, energy balance, and contribution totals.
- Compare at least one manually calculated anchor against the software result.
- Run sensitivity cases for dominant equipment energy, catalyst lifetime, yield, electricity mix, solvent recovery, proxy choice, and scale-up assumptions.
- For a documented additive approximation based on existing absolute impact results, use `scripts/sensitivity_report.py`; follow its scope checks and require complete, non-overlapping contributions. Use separate LCA recalculation when scaling assumptions are not justified.
- Read `references/calculation-and-qa.md` for formulas and stop conditions.

### 7. Interpret and report

- Separate observed results from mechanistic hypotheses about piezoelectric response, charge separation, kinetics, or electronic structure.
- Report hotspots, trade-offs, uncertainty, limitations, and conditions under which route rankings change.
- Read `references/reporting-and-figures.md` before producing manuscripts, SI tables, or figures.

## Software routing

| Situation | Route |
| --- | --- |
| Reproducible scripted model creation and result export | openLCA IPC, after the user starts the IPC server |
| Stable human-confirmed workflow with limited automation rights | SimaPro Direct Import or Excel external links |
| SimaPro COM error or uncertain license | Stop COM writes, document capability result, use the manual-import route |
| Database mapping remains uncertain | Build an auditable proxy table before calculation |
| Preparation-only catalyst comparison | Use a dry-catalyst functional unit and do not claim treatment superiority |
| Treatment comparison | Use equal pollutant-removal or outlet-quality service and allocate catalyst preparation by lifetime |

## Required deliverables

Produce these artifacts unless the user narrows the scope:

1. model specification with version, scope, functional unit, and exclusions;
2. foreground LCI table;
3. dataset-mapping and proxy register;
4. assumptions and uncertainty register;
5. software import or automation artifact;
6. absolute LCIA table and contribution table;
7. sensitivity/uncertainty outputs;
8. calculation manifest with software, database, method, date, and identifiers;
9. methods and limitations text suitable for SI.

## Resource map

- Domain decisions: `references/piezocatalysis-methodology.md`
- Evidence, proxies, uncertainty: `references/evidence-and-data-quality.md`
- openLCA UI/IPC: `references/openlca-workflow.md`
- SimaPro import/link/COM: `references/simapro-workflow.md`
- Equations and QA: `references/calculation-and-qa.md`
- Manuscript and figure output: `references/reporting-and-figures.md`
- Lessons from completed BiOX work: `references/project-lessons.md`
- Machine-readable specification: `references/model-spec-schema.md`
- Templates and a synthetic example: `assets/`

## Completion gate

Do not declare completion until:

- all required flows have evidence classes and units;
- the model reproduces after a fresh run;
- no software error is hidden by a fallback zero;
- absolute results and normalized figures agree;
- dominant contributors have plausible providers;
- exclusions and proxies are visible in the final methods;
- software-specific outputs match the software-neutral specification.
