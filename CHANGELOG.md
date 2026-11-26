# Changelog

## 1.7.6 — 2026-11-26

- Apply the calculation readiness budget to openLCA IPC status polling, discard ready responses received after the deadline, and attempt to dispose of the result after a timeout.
- Validate the readiness budget before making calculation IPC calls, including when a saved scenario suite supplies the value.

## 1.7.5 — 2026-11-24

- Reuse result-reference metadata in the verified local openLCA guard for up to 32 calls per worker and database, while encoding each calculation's values separately.
- Verify repeated calculations in the same guarded session produce fresh LCIA impacts and contributions.
- Look up a small number of openLCA descriptors by ID in the verified local guard, with the upstream full map used for larger reference sets.
- Reuse a bounded set of entity responses within a guarded scenario suite. Read the product system and its parameters before and after each calculation, and use fresh reads for external IPC.

## 1.7.3 — 2026-11-22

- Use indexed exchange ID lookups for product-system snapshots in the verified macOS openLCA 2.7.0 launcher. Preserve both snapshot reads, upstream JSON output, and the original query for larger exchange sets and other compatible builds.

## 1.7.2 — 2026-11-22

- Validate the exact files included in a research delivery and publish the complete directory in one step. A failed assembly can be retried at the same output path.
- Require an evidence specification and report for attached evidence sources. Check portable artifact names and reject symbolic links when verifying a package.
- Look up foreground activity bindings and exchange IDs directly, preserve support for older bindings without exchange IDs, and reject duplicate IDs within a foreground process.

## 1.7.1 — 2026-11-21

- Read mapped openLCA processes and location codes by ID. Reuse the process snapshots already captured on each side of a scenario calculation.
- Index selected LCIA factors and calculated inventory entries once per audit. Keep each flow's factor status, reference basis and inventory occurrences.
- Verify complete research deliveries against their replay specification, including evidence sources, result tables and plots. Keep older scenario captures usable across generator revisions while checking their original digests.
- Refresh the optional Brightway example's installation requirements for Python 3.12 with patched dependency versions.
- Dispose of openLCA calculation results after interruption. Reject duplicate impact categories and inventory rows without a flow identifier.
- Match saved scenario factor checks to the selected flows. Check that a delivery's source and replay specifications describe the same study, and reject evidence names that would collide on case-insensitive file systems.

## 1.7.0

- Trace end-of-campaign catalyst disposal to a declared route, source and dry mass, and verify the linked waste reference in openLCA.
- Import cycle observations from CSV with sample identities, replicate choices, detection limits and energy measurement bases.
- Preserve published H₂O₂ production as a distinct functional-unit basis and audit selected flow–category coverage against the stored inventory unit.
- Recalculate fixed-exchange cyclic and H₂O₂ scenarios in openLCA, verify actual provider links, and package the inputs, results and figures for replay.

## 1.6.0 — 2026-11-18

- Check the actual product-system reference process, reference exchange and unit during scenario capture, and repeat mapping preflight after calculation. Bound records now use version 2; older captures need to be recreated.

- Rebuild and verify bound scenario figures and additive sensitivity figures within research deliveries; add explicit required stage inputs and a real-case intake checklist.

- Capture scenario-specific openLCA model, linked exchanges, background provider and parameter snapshots around calculation; bind comparisons to both scenario plans and disable unsupported linear estimates.

- Add explicit campaign/sample/cycle evidence links and provisional per-cycle service threshold checks, retaining the existing apparent-removal inventory basis.

- Extend evidence-chain and research-delivery checks to H2O2 product foregrounds, preserving product basis, declared definition, source links and allocation trace.

## 1.5.0 — 2026-11-16

- Reject evidence links that use a known cycle's basis for a different foreground cycle, even if the values match.
- Check cyclic inventory evidence class and source against the rebuilt foreground during evidence auditing and research delivery.
- Add task routing and optional file-hash stage records for resuming declared workflows; scientific review remains separate.

## 1.4.0 — 2026-11-16

- Cross-check pollutant and service declarations against the cyclic foreground; retain existing mapping IDs and stop when an ID is shared across activities.

- Assemble and verify local research deliveries from linked foreground, evidence, mapping, openLCA and plot artifacts; include an explicit methods draft, gaps and replay specification.

- Record read-only openLCA mapping alternatives, geography and reference details, reviewer decisions and proxy rationale; export selected candidates as pending mappings.

- Link synthetic or user-prepared evidence CSV records to cyclic foreground quantities and checked per-functional-unit inventory; review piezocatalysis energy, oxidant, catalyst and water-sample declarations.

- Add agent-callable engineering scenario reporting, including explicit measurement ranges and background changes.
- Do not infer a censored interval from a missing or contradictory observation; require independent review before ranking scenarios.

- Add versioned plot-data preparation and editable SVG/PNG/CSV figures for cyclic performance, traceable stage contributions, comparable scenarios and one-at-a-time sensitivity.

- Add domain service and evidence review for water treatment, apparent pollutant removal, H2O2 products and dry catalyst production, with censored-sample intervals and explicit comparability limits.

- Add a literature-informed piezocatalytic H2O2 product foreground with explicit net-accumulation versus recovered-product bases, catalyst allocation and functional-unit inventory handoff.

- Audit batch and cycle data quality, missing and censored values, paired settings, catalyst destinations and selected openLCA uncertainty fields; extend finite-state synthetic convergence diagnostics.

- Compare independently calculated cycle scenarios against rebuilt per-functional-unit inventories, declared study contexts and a labeled linear contribution estimate.

- Add read-only cycle mapping preflight and result interpretation for intervention flows, system link records, selected LCIA factors and signed contributions.
- Extend the guarded openLCA 2.7.0 service with total inventory retrieval; distinguish technical flows from elementary flows and dispose temporary results.

- Declare cycle inventory functional-unit basis, generate a paired provenance manifest and reject a second scaling by the existing batch/run scaler.
- Add a traceable, user-reviewed dataset mapping handoff with explicit missing amounts, unit and direction issues, and catalyst loss warnings.

## 1.3.0 — 2026-11-15

- Review selected openLCA process reference exchanges, product-system links and LCIA factor coverage, including missing units and formula-based factors.
- Build functional-unit inventories from cycle-by-cycle catalyst reuse records, preserving missing values, detection limits, dry/wet basis and unreconciled catalyst losses.
- Check declared scenario comparability and uncertainty evidence; add a seeded joint-state synthetic example rather than claiming a native Monte Carlo implementation.
- Verify the cycle inventory through a fictional linked openLCA model and actual parameter recalculation; document tests, scientific boundaries and rollback.
- Extend the guarded localhost service to permit single-entity `data/get` reads; local clients can access individual entities while the service runs.

## 1.2.0 — 2026-11-14

- Add reviewed process-candidate searches, optional openLCA IDs and source metadata for inventory mappings; preserve existing mapping files.
- Build traceable experimental foreground inventories and scale catalyst-production and pollutant-removal functional units, including missing values and detection-limit ranges.
- Recalculate one-parameter scenarios in openLCA and record model context, input/code hashes, results and redacted summaries; retain the separate additive approximation.
- Restore guarded automatic startup after the macOS GUI generates bundle caches by verifying a temporary cache-free application copy; modified signed resources are still rejected.
- Preserve zero-removal observations without attempting treatment scaling, and handle process descriptors without a location.

## 1.1.1 — 2026-11-13

- Discover an already-running local openLCA IPC service on bounded candidate ports; ambiguous matches require an explicit port. Discovery does not authenticate the service. On the verified macOS 2.7.0 distribution, optionally start a guarded temporary local server on an APFS clone of an existing database.
- Reject header-only inventories and normalize direction and evidence-class casing consistently between validation and scaling.
- Reject nonzero calculation results that underflow to zero, including combined preparation shares; legitimate zero inputs remain valid.
- Use relative tolerance without a fixed, unit-independent absolute tolerance for sensitivity and openLCA contribution reconciliation; near-zero results may require human review.
- Add the v1.1.0 version-specific Zenodo citation and document architecture and verification limits.
- Check two synthetic workflows from inventory validation and scaling to partial-impact sensitivity reporting against hand calculations.

## 1.1.0 — 2026-11-08

- Preserve baseline and scenario evidence separately for sensitivity adjustments; replacement values now require their own evidence class. Older `replace` inputs must add `replacement_evidence_class`.

- Document a separately pinned Brightway feasibility experiment and an isolated, fictional cross-engine example; advanced engines are not added as core dependencies.

- Add sourced single-factor sensitivity and absolute-result reporting with compatibility gates, contribution reconciliation, ranking-change detection, CSV export, and a synthetic seven-variable example. This is an additive approximation, not a replacement for LCA recalculation.
- Add a localhost-only openLCA 2.x JSON-RPC read-only adapter for descriptor listing, existing-system calculations, absolute impacts, contributions, reconciliation, and temporary-result disposal. Database identity and user-supplied unit labels require independent confirmation; mock tests are not real-engine validation.
- Add an auditable pollutant-removal inventory scaling workflow with sourced parameters, explicit reuse assumptions, unit conversion checks, mapping IDs, and a fully synthetic example. Unmapped flows remain visible with null dataset amounts.
- Expand inventory source and malformed-row checks; mapping templates add `mapping_id` and `rationale` columns.
- Reject non-finite foreground inventory amounts and add regression tests.
- Check finite values, physical boundaries and non-finite outputs in calculation helpers; improve small-rate removal precision and CLI error handling.
- Harden the model-spec structural validator against malformed JSON, invalid types, non-finite values and missing foreground provenance; warn about recognized placeholders and offer `--reject-placeholders`.
- Structural validation is not a scientific-completeness assessment. Existing model specifications may need stage, direction and source fields added to each foreground inventory item.
