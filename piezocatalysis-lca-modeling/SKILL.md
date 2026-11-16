---
name: piezocatalysis-lca-modeling
description: Help research agents build, audit, calculate, and report life-cycle assessments of piezocatalysis, photocatalysis, and piezo-photocatalysis systems using experimental evidence and LCA software.
---

# Piezocatalysis LCA Modeling

## Purpose

Help the agent carry out the requested part of a transparent, reproducible piezocatalysis LCA. Use the scripts, templates and references as needed; keep the research model independent of openLCA and SimaPro. This is an agent skill package.

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

## Task routing

| Request | Route |
| --- | --- |
| Check available experiment data or LCA readiness | Quick Audit: use only applicable evidence, inventory, domain and uncertainty checks; report unexamined inputs as `NOT_EVALUATED`. |
| Build or calculate an LCA, or compare PZC/PC/PPC | Guided LCA: define service and boundaries, validate inputs and mapping, then use an authorized software path; check comparability before interpreting results. |
| Organize existing results and methods | Research Delivery: assemble existing artifacts; do not rerun openLCA unless expressly requested. |
| One specific calculation or ambiguous request | Use the relevant existing tool or the smallest non-destructive check, and state missing prerequisites. |

For stage inputs, output gates, human review and optional dependency-aware records, read `references/task-routing.md`. Its `PASS` covers only the specified automatic check; scientific approval is separate.

## Workflow

### 1. Intake and evidence audit

Choose the relevant stages for the user’s request; do not require a complete LCA for a narrower task.

- Collect experimental recipes, yields, washing and separation steps, equipment power, run time, catalyst dose, pollutant concentration and volume, kinetic constants, reuse data, and end-of-life assumptions.
- Create an assumptions log and dataset-mapping table from `assets/templates/`.
- Run `scripts/validate_inventory.py` before software import.
- Read `references/evidence-and-data-quality.md` whenever data are incomplete, literature-derived, or represented by a proxy.
- Use `scripts/domain_review.py` for service, experimental boundary, sampling, catalyst and waste evidence declarations; verify scientific suitability using `references/domain-quality-checklist.md`.
- For auditable numeric evidence, link a normalized local CSV to cyclic foreground quantities with `scripts/evidence_chain.py`; compare the generated inventory when available. Verify original spreadsheet cells or document pages separately; hashes and declared locators alone do not verify them. See `assets/examples/synthetic-evidence/README.md`.
- Use `scripts/piezocatalysis_checks.py` to review ultrasound energy basis, auxiliary and illumination energy, oxidants, pH adjustment, catalyst destination, byproducts and mineralization claims, and reconcile the specified cycle’s water measurements with the domain declaration. Missing evidence stays visible.

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
- For a piezocatalytic H2O2 product function, use `scripts/h2o2_foreground.py` and document product basis, catalyst allocation and product consumption; see `references/domain-literature.md`.
- For a pollutant-removal service with equal performance per run and a justified effective-use assumption, `scripts/audit_and_scale_inventory.py` can audit and scale the foreground inventory; see `assets/examples/synthetic-treatment/README.md`. Treat warnings and unmapped flows as unresolved, and use cycle-by-cycle modeling when those assumptions do not hold.
- For traceable experiment records, two functional-unit families, below-quantification limits and inventory CSV export, use `scripts/experimental_foreground.py`; see `assets/examples/synthetic-foreground/README.md`. The concentration difference is an apparent aqueous removal, not proof of mineralization.

### 4. Map background datasets

- Prefer exact substance and technology matches, then stoichiometric construction, then transparent functional proxies.
- Record dataset name, database version, system model, geography, unit, provider, proxy rationale, and expected bias.
- Before uncertainty simulation, use `scripts/uncertainty_readiness.py` to inventory declarations, missing distributions, censoring and dependencies; distinguish review from represented background uncertainty. `scripts/synthetic_joint_uncertainty.py` is only a seeded finite-state synthetic demonstration, not a general or native openLCA Monte Carlo engine.
- Before interpreting scenarios from separate contexts, run `scripts/scenario_comparability.py` and resolve missing or differing declarations; a text match is not proof of scientific equivalence.
- For newly exported cycle inventories use `scripts/inventory_handoff.py` and the paired manifest to review per-functional-unit basis, mappings, missing amounts and unaccounted catalyst losses; see `assets/examples/synthetic-handoff/README.md`. Unmarked legacy CSV basis cannot be inferred.
- Use `scripts/cycle_model_plan.py` for read-only openLCA verification of cycle mappings and per-functional-unit quantities; unresolved items and proxies require review.
- Use `scripts/result_coverage.py` to inspect intervention-flow types, technical link records, selected LCIA factors and contribution offsets; restrict sharing according to database licenses.
- Compare cycle-level scenario inputs with `scripts/cycle_scenario_compare.py`, independently verify each calculated model exchange, and review comparability before interpreting results.
- Use `scripts/experimental_quality.py` to review cyclic observations, censoring and paired measurements, and `scripts/openlca_uncertainty_inventory.py` for scoped read-only background field counts before uncertainty analysis.
- For varying catalyst reuse cycles, use `scripts/cyclic_foreground.py`; see `assets/examples/synthetic-cycles/README.md`. The CSV is already scaled to the treatment functional unit. Its evidence class describes the underlying activity input; the per-functional-unit amount itself is calculated and also depends on the FU and other allocation inputs. Keep missing quantities, censoring, catalyst loss and final recovery destination explicit.
- Use `scripts/dataset_candidates.py` for read-only candidate discovery and review; see `assets/examples/synthetic-mapping/README.md`. Confirm reference flows, units and IDs before updating the mapping table.
- For multi-candidate openLCA mapping review, use `scripts/mapping_review.py` and `assets/examples/synthetic-mapping-review/README.md` to record geography, reference product, unit, competing choices and proxy rationale. It exports selected mappings as pending; review and verify provider links before use.
- Use `scripts/mapping_coverage.py` to inspect a selected process reference exchange, a specified product-system link and selected elementary-flow factors in specified LCIA categories; see `assets/examples/synthetic-coverage/README.md`. Record the review separately: a matching reference is not automatic approval, and selected factors do not prove full model coverage.
- Do not silently omit unmatched chemicals. Flag them for sensitivity analysis.
- Validate unit conversion and reference-product direction before linking providers.

### 5. Execute in the selected software

- For openLCA, read `references/openlca-workflow.md` and use the UI or IPC only after confirming the active database and LCIA methods.
- For local read-only discovery or calculation of existing product systems, use `scripts/openlca_readonly.py` only after confirming database, UUIDs, functional unit and software context. It does not verify user-supplied database or unit labels; review warnings and verify result metadata independently.
- For the verified macOS openLCA 2.7.0 distribution, the adapter can start a guarded temporary localhost server on an APFS clone of an existing closed database with `--start-local --workspace PATH --database NAME`; check the launcher constraints and local-access risks in `references/openlca-workflow.md`. Discovery of an already running server does not authenticate it, and automatic startup on other versions or platforms is unsupported.
- For SimaPro, read `references/simapro-workflow.md`. Probe Direct Import, Excel external links, and COM authorization separately; a Developer installation does not by itself prove COM entitlement.
- Keep a software-neutral model specification as the authoritative record.

### 6. Calculate and audit

- Calculate absolute midpoint results and energy-demand results first.
- Verify reference flows, target units, provider links, signs, scaling factors, mass balance, energy balance, and contribution totals.
- Compare at least one manually calculated anchor against the software result.
- Run sensitivity cases for dominant equipment energy, catalyst lifetime, yield, electricity mix, solvent recovery, proxy choice, and scale-up assumptions.
- For cycle scenarios and engineering assumptions, use `scripts/engineering_scenarios.py` and `assets/examples/synthetic-engineering/README.md`; retain sources, measurement ranges and missing impact results. Do not infer engineering performance or ranking from declarations.
- For a documented additive approximation based on existing absolute impact results, use `scripts/sensitivity_report.py`; follow its scope checks and require complete, non-overlapping contributions. Use separate LCA recalculation when scaling assumptions are not justified.
- For actual one-at-a-time parameter recalculation of an existing openLCA product system, use `scripts/parameter_sensitivity.py` and check `assets/examples/synthetic-parametric/README.md`; keep its results distinct from additive approximations.
- Read `references/calculation-and-qa.md` for formulas and stop conditions.

### 7. Interpret and report

- Separate observed results from mechanistic hypotheses about piezoelectric response, charge separation, kinetics, or electronic structure.
- Report hotspots, trade-offs, uncertainty, limitations, and conditions under which route rankings change.
- Read `references/reporting-and-figures.md` before producing manuscripts, SI tables, or figures.
- For an auditable local delivery, use `scripts/research_delivery.py` with the applicable existing foreground, evidence, mapping, calculation and figure artifacts; see `assets/examples/synthetic-delivery/README.md`. It checks and organizes supplied artifacts, reports gaps and provides a replay specification; it does not run openLCA or prove scientific validity.
- Use `scripts/plot_data.py` and `scripts/plot_report.py` for traceable cycle, stage, scenario and one-at-a-time sensitivity figures; preserve units, partial-model warnings and database license notes.

## Software routing

| Situation | Route |
| --- | --- |
| Reproducible scripted model creation and result export | openLCA IPC with separately verified permissions; the guarded adapter only reads descriptors and calculates existing systems |
| Stable human-confirmed workflow with limited automation rights | SimaPro Direct Import or Excel external links |
| SimaPro COM error or uncertain license | Stop COM writes, document capability result, use the manual-import route |
| Database mapping remains uncertain | Build an auditable proxy table before calculation |
| Preparation-only catalyst comparison | Use a dry-catalyst functional unit and do not claim treatment superiority |
| Treatment comparison | Use equal pollutant-removal or outlet-quality service and allocate catalyst preparation by lifetime |

## Required deliverables

For a complete LCA, produce the applicable artifacts below. For a narrower request, provide only relevant outputs and identify missing prerequisites; never invent results:

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

For the requested scope, check the applicable items below. When a prerequisite is missing, report it and avoid presenting the corresponding result as complete:

- all required flows have evidence classes and units;
- the model reproduces after a fresh run;
- no software error is hidden by a fallback zero;
- absolute results and normalized figures agree;
- dominant contributors have plausible providers;
- exclusions and proxies are visible in the final methods;
- software-specific outputs match the software-neutral specification.
