# Verification report / 验证报告

## Environment and baseline

On 2026-11-16 the local development tree began clean at `ddec6a2c08f93f7c2fb31634c6145bab91f3d93f` (v1.4.0 with its DOI documentation). Tests ran on macOS 27.2.1, Python 3.9.6, in the local environment with optional matplotlib. The original baseline command `python -m unittest discover -s tests` ran 257 tests: 257 passed, 0 failed, 0 skipped. The final same command ran 263 tests: 263 passed, 0 failed, 0 skipped. Those counts do not include the separately run integration scripts below. Test logs are kept in the user's local diagnostics directory, not the repository.

Skill format validation and `git diff --check` passed. Matplotlib emitted upstream deprecation notices without test failures. The final code keeps the existing openLCA Java guard and its version/permission controls unchanged.

## Focused regression

- `test_evidence_chain.py` and `test_research_delivery.py`: changing the source or changing a synthetic scenario to `measured` in an inventory, even after recomputing the manifest's inventory SHA-256, now fails against the rebuilt foreground. Normal leading/trailing source whitespace follows the existing CSV parser normalization. Existing numerical and per-FU handoff checks remain in place.
- `test_workflow_state.py`: a changed upstream input blocks reuse of the dependent stage, missing outputs are blocked, an existing state file is not overwritten, and a file-integrity pass does not imply scientific review.
- Existing tests cover unit conversion, exact zero, missing and censored values, finite values, catalyst mass continuity, functional-unit scaling, mismatched contexts, pending proxies and unavailable openLCA startup. The scope of each is the exercised fixture and path, not proof for every model.

## End-to-end tests actually run

- A local synthetic experimental chain was rerun through evidence, domain review, per-FU inventory, mapping preflight, openLCA IPC calculation, coverage, plots and research delivery. The controlled temporary database copy uses locally licensed ecoinvent 3.9.1 cutoff background. Baseline and higher-power cases each matched all 32 impact categories from their previously saved synthetic calculation within `rel_tol=1e-9` and `abs_tol=1e-13`. The models still contain proxies and an unresolved catalyst destination; these are not valid comparative research conclusions.
- The separate candidate lookup used a controlled temporary copy of the installed ecoinvent database: four synthetic selections remain pending and five activities unresolved. A separate synthetic-only promoted mapping was used to exercise preflight and is not researcher approval.
- Final-code delivery and replay each verified 35 listed file hashes. Methods, LCIA table and two figures (SVG and PNG) were byte-identical across six files. Replay reassembles existing calculation data; it does not rerun openLCA. The report retains 21 warnings and `review_required`.
- `tests/integration_synthetic_cycle_workflow.py` ran both constant and `--case variable-exact` cases in independent fictional temporary databases. Both performed real openLCA baseline and parameter recalculation, with synthetic expected anchors and no change to their source database.
- `tests/integration_result_coverage.py`, `tests/integration_openlca_parameters.py` and `tests/integration_openlca_guard.py` each passed against temporary fictional openLCA databases. Checks included missing versus zero factors, unlinked flow, parameter changes, restricted writes, local-only binding and service cleanup after parent interruption. These five invocations are integration runs, not additional unittest test counts.
- A real local stage-state demonstration first checked the declared foreground and reporting files as `PASS` for integrity and `NOT_EVALUATED` for scientific review. A change to a copied synthetic source caused its dependent reporting state to return `BLOCKED`, preserving existing outputs.

The openLCA tests use an authorized temporary local service and cloned databases, terminated after testing. Original database path/size/mtime fingerprints before and after the ecoinvent-backed calls matched; this is a metadata fingerprint, not a full content hash. No licensed background database or generated background-derived results are published in this repository.

## Remaining limitations and status

| Area | Status | Basis |
|---|---|---|
| Automated scientific constraints | WARNING | Covered cases pass; assumptions, original measurements, provider suitability and complete method coverage still need domain review. |
| Engineering implementation | PASS | Listed unit and integration tests passed in the stated environment; no claim of universal platform coverage. |
| Workflow automation | WARNING | Stage state checks explicitly declared files/dependencies; it cannot discover omissions or automatically rerun downstream stages. |
| Software integration | WARNING | Real openLCA 2.7.0 and controlled local ecoinvent/synthetic copies were tested on this macOS host; other platforms and SimaPro were not tested. |
| Real scientific validation | NOT_EVALUATED | No authorized real experimental case supplied to this task. See `real-case-validation-protocol.md`. |

Brightway was not run in this iteration. No external write, Git commit, push or release was performed. Integrity hashes do not authenticate source measurements or constitute scientific approval.

## Follow-up review / 工程升级再次复核

A further review on 2026-11-16 reproduced a cycle-basis mismatch: equal-valued observations from two cycles could link a `cycle-2` source to a `cycle-1` target while the link's numeric match was reported. When a basis has the known `cycle-<cycle_id>` form, `evidence_chain.py` now rejects a different target cycle; custom basis labels remain user assertions. The duplicate-record test was retained using two same-cycle measurements. The current full test suite ran 264 tests, all passed, none skipped; Skill format and Git diff whitespace checks passed.

The complete synthetic workflow was independently rerun on a controlled local openLCA/ecoinvent copy: baseline and higher-power results matched all 32 earlier impact categories with `rel_tol=1e-9` and `abs_tol=1e-13`; four synthetic candidate selections were pending and five activities unresolved. Research delivery and replay each verified 35 files, and six methods/table/figure files matched. The delivery retained 21 warnings and `review_required`. A separate copied-source state exercise showed a changed declared upstream input makes the dependent reporting record `BLOCKED`, while scientific review stays `NOT_EVALUATED`. The service stopped after the run. The background-derived results remain local and subject to the database license.

This rerun tests the integration path, not a real experimental research claim. It does not establish that a custom sample basis, omitted workflow dependency, proxy selection, or full upstream supply chain is scientifically correct. Detailed local logs are kept outside the repository.
