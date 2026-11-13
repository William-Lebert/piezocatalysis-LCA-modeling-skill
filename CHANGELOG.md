# Changelog

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
