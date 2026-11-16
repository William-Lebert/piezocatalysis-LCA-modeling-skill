# Engineering audit / 工程审计

## Baseline / 基线

2026-11-16, development checkout at `ddec6a2c08f93f7c2fb31634c6145bab91f3d93f` (v1.4.0 plus DOI documentation). The checkout was clean. macOS, Python 3.9, with optional matplotlib in a local virtual environment. `python -m unittest discover -s tests` executed 257 tests: 257 passed, 0 failed, 0 skipped; log retained locally under `.hermes/diagnostics/20261116_工程质量基线/baseline-tests.log`. Four `tests/integration_*.py` scripts are not collected by the default discovery; they require separately prepared openLCA fixtures and are not counted in that result. There are 31 Python files under the Skill scripts directory and 29 `test*.py` files. Counts are not evidence of scientific validity.

The standard-library workflow uses Python 3.9 or later as exercised here; plotting additionally uses matplotlib (see the plotting example); Brightway uses a separate optional environment. openLCA local startup is limited to the documented verified macOS/openLCA version. Absolute host paths are configuration defaults or local test evidence, not a portable requirement.

## Confirmed findings / 已确认问题

| ID | Priority | Evidence and consequence | Resolution |
|---|---|---|---|
| E1 | P1 | `research_delivery.assemble` and `evidence_chain.audit`: alter a cyclic inventory row's `evidence_class` from `scenario` to `measured`, change its `source`, then update only `inventory_sha256` in its manifest. Both paths accepted the inconsistent pair and reported a rebuilt foreground check. This can misrepresent provenance even though numerical quantities match. | Fixed in both checks: compare rebuilt source and evidence class with every inventory row; regression tests exercise a rehashed manifest. |
| E2 | P2 | `SKILL.md` has detailed procedures but no compact entry for three requested task modes or a durable dependency-aware resume protocol. A user or agent can reuse stale intermediate artifacts without a unified workflow-level decision. | Implemented lightweight routing and explicit state records; only declared dependencies are checked and scientific review is not evaluated. |
| E4 | P2 | Cyclic inventory amounts are scaled to the FU while `evidence_class` retains the underlying activity input class; without explanation a `measured` class could be mistaken for a directly measured per-FU result. | Documented both meanings in the Skill and cycle example; input dependencies remain in the evidence trace. The existing field is not silently redefined. |
| E3 | P3 | The bilingual manual describes the broad workflow but does not distinguish the three task modes or clarify that delivery replay reorganizes saved outputs without rerunning openLCA. | Added matching concise routing and limitations to the manual and README. |

## Workflow inventory / 流程清单

| Stage | Existing inputs and entry | Outputs and stop or review points |
|---|---|---|
| Experiment and evidence | normalized CSV and foreground JSON; `evidence_chain.py`, `experimental_quality.py` | Evidence audit with source and value links; missing, censored and source-locator claims remain reviewable. |
| Goal and scope | domain declaration, foreground and protocol; `domain_review.py`, `piezocatalysis_checks.py` | Service, pollutant and boundary checks; human checks scientific equivalence, origin and endpoint. |
| Foreground LCI | cycle or batch JSON; `cyclic_foreground.py`, `experimental_foreground.py` | Inventory and optional cycle manifest; unknown values remain missing, cycle inventory is already per FU. |
| Background | inventory/manifest, mapping decisions; `inventory_handoff.py`, `mapping_review.py`, `cycle_model_plan.py` | Candidate and preflight records; provider, proxies, database version and suitability remain human decisions. |
| Calculation and coverage | existing product system, method and controlled connection; `openlca_readonly.py`, `result_coverage.py` | Absolute LCIA and selected-factor/link checks; connection alone is not proof of model completeness. |
| Interpretation | contexts, recalculation or contribution inputs; `scenario_comparability.py`, `parameter_sensitivity.py`, `uncertainty_readiness.py` | Declared comparability and bounded analysis; no invented distributions or unsupported rankings. |
| Delivery | pre-existing artifacts; `research_delivery.py` | Local bundle, source hashes, methods draft and replay; verification checks file consistency, not authenticity or scientific approval. |

Many dependencies are already bound by SHA-256 inside existing specialized artifacts. Those bindings do not authenticate sources, and not all legacy formats declare every database or scientific parameter. Review the relevant artifact and missing-value warnings before reuse. A shell redirection such as `> output.json` can overwrite an existing file; select a new output path rather than redirecting to user data.

## Implementation and verification / 实施与验证

E1 is fixed in both evidence and delivery reconstruction; the new regression tests cover both source and evidence-class alteration with an updated manifest hash. E2 adds only optional explicit file-state records and a routing reference; it cannot discover dependencies an agent has not listed, and does not rerun calculations. E3 and E4 are documentation changes that preserve the original data contract. Test counts, executed real-engine synthetic paths, remaining limitations and separate scientific status are in [verification-report.md](verification-report.md); stricter provenance handling is described in [migration-notes.md](migration-notes.md).

### Follow-up finding E5 / 再次复核发现

**P1 — known cycle basis and target could disagree.** A source record labeled `cycle-2` with the same concentration as a `cycle-1` measurement could previously be linked to the first cycle and still receive `source_matches_declaration`. A duplicate source might generate a separate warning, but that did not explain the cycle mismatch. The evidence audit now rejects a basis of the recognized `cycle-<cycle_id>` form when it names a different known target cycle. A synthetic regression reproduces the equal-value case; arbitrary sample-basis labels still need independent review. See the follow-up section of the verification report for test and real-engine results.
