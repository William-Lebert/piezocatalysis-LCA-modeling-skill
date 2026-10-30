# Lessons from the BiOX Piezocatalysis Project

These lessons are generalized from a completed openLCA/SimaPro workflow and should guide future piezocatalysis studies.

1. **Software edition is not automation entitlement.** A SimaPro Developer installation can open normally while COM returns `No license for COM`. Test authorization before designing an automated workflow.
2. **A manual-import architecture remains viable.** Validated Excel/CSV packages plus human confirmation can be more stable and lower-risk than direct database writes.
3. **Excel link format matters.** A simple legacy `.xls` workbook succeeded where a richer `.xlsx` workbook produced a sheet-index error. Always perform a one-cell compatibility probe.
4. **openLCA IPC is database-context dependent.** The user must open the correct database and start the server; UUIDs and LCIA methods must be checked against that active database.
5. **Back up before foreground updates.** Export process JSON and store a manifest before changing exchanges or providers.
6. **Use kinetics for the active treatment model.** When measured `kobs` values are available, derive removal and EE/O directly rather than substituting unrelated five-cycle retention data.
7. **Separate LCA energy from EE/O power.** Hydrothermal synthesis and centrifugation affect LCA but not the EE/O treatment-power term.
8. **Illumination is a boundary decision.** A natural-light deployment scenario can exclude laboratory lamp electricity, but the exclusion must be explicit and should be tested against an artificial-light case.
9. **Route-specific separation matters.** Extra ethanol washing and centrifugation cycles can materially change preparation impacts and must not be copied across routes.
10. **Proxy models need visible labels.** Bismuth salts, PVP, mannitol, halide salts, and specialty chemicals may require transparent baseline proxies and sensitivity tests.
11. **Preparation rankings are not treatment rankings.** A comparison per gram of catalyst cannot establish the best catalyst per pollutant removed without activity and lifetime modeling.
12. **Identical normalized trends are a warning.** Check for shared processes, repeated result columns, normalization of normalized data, and incorrect reference-product links.
13. **Keep absolute results.** The absolute LCIA table is the audit trail; normalized figures alone cannot support scientific conclusions.
14. **Clean obsolete models deliberately.** Record removed model versions and boundary changes so outdated light-energy or reuse assumptions do not re-enter the active calculation.
