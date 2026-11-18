# Task routing and resumable records / 任务路由与恢复

Choose the smallest route matching the request. Preserve raw inputs and choose new output paths. A request for only one operation can use its existing script directly. The stage record below is optional and records only files the agent actually lists: it is not an orchestrator, a mandatory questionnaire, or automatic scientific approval.

## Quick Audit / 快速审查

For an experiment CSV, a parameter JSON, an LCI or model specification, inspect what is actually supplied. Use `validate_inventory.py` for a compatible inventory, `validate_model_spec.py` for its structural subset, `evidence_chain.py` for explicitly linked normalized CSV and cycle foreground, `experimental_quality.py` for cycle observations, and `piezocatalysis_checks.py` or `domain_review.py` for relevant declarations. Use `uncertainty_readiness.py` when an uncertainty inventory exists. Report units, sources and evidence, FU and boundary, energy and materials, catalyst losses, uncertainty gaps and blocking items; label anything without inputs as `NOT_EVALUATED`. Do not infer an LCIA result.

## Guided LCA / 引导建模

Use the stages that the question needs. Reuse a prior artifact only after its relevant inputs, declared stage records and scientific assumptions have been checked. The status examples below are workflow-level summaries, not changes to existing script JSON schemas.

| Stage (state key) | Minimum input and automated check | Output and human gate |
|---|---|---|
| Intake (`intake`) | Available copied records and research question; list omissions | Input list; agree intended service and data permissions. |
| Evidence (`evidence`) | Foreground plus normalized sources; `evidence_chain.py`, `experimental_quality.py` | Evidence report; check original cells, qualifiers and origins. |
| Goal and scope (`scope`) | Defined service, FU and boundaries; `domain_review.py`, `piezocatalysis_checks.py` | Scope and domain checks; confirm service quality, exclusions and endpoints. |
| Foreground LCI (`foreground`) | Batch or per-cycle observations; `experimental_foreground.py` or `cyclic_foreground.py` | Inventory and applicable manifest; check mass loss, treatment performance and cycle assumptions. |
| Background mapping (`mapping`) | Inventory and manifest, available database; `inventory_handoff.py`, `mapping_review.py` | Candidates and pending decisions; review provider, geography, unit and proxy rationale. |
| Model validation (`validation`) | Mapping and accessible existing system; `cycle_model_plan.py`, `mapping_coverage.py` | Preflight and selected links/factors; independently confirm unresolved connections and model scope. |
| Software execution (`execution`) | Verified context, method and existing system; `openlca_readonly.py` | Absolute calculated results; connection alone does not imply model completeness. Writes require separate authorization. |
| LCIA QA (`lcia_qa`) | Calculation plus applicable links/factors; `result_coverage.py` | Coverage and contribution checks; verify units, signs, totals and remaining gaps. |
| Sensitivity (`sensitivity`) | Explicit parameters, assumptions and uncertainty evidence; `parameter_sensitivity.py`, `sensitivity_report.py`, `uncertainty_readiness.py` | Clearly distinguish recalculation, scenario and additive approximation; review correlations and absent distributions. |
| Reporting (`reporting`) | Existing checked outputs; `research_delivery.py` and plotting tools | Delivery and method draft; scientific conclusions require independent human review. |

`PASS` means the stated automatic check passed, `WARNING` means a non-blocking issue, `REVIEW_REQUIRED` requires a human decision, `BLOCKED` means a prerequisite is missing or invalid, and `NOT_EVALUATED` means the check was not performed. These labels do not prove the truth of measurements, suitability of proxies, full method coverage, or comparability. Existing script-specific statuses must retain their documented meanings rather than being automatically promoted to `PASS`.

## Research Delivery / 科研交付

For organizing existing records use `research_delivery.py assemble` and `verify`; see `assets/examples/synthetic-delivery/README.md`. It does not calculate or connect to openLCA. It can include supported cyclic, stage, bound-scenario and additive-sensitivity figures when the full source groups are supplied. Preserve absent materials as gaps. Replay reassembles the saved inputs; it does not reproduce a new LCIA calculation.

## Optional stage state / 可选阶段状态

`workflow_state.py` records hashes of **explicitly specified** existing input/output files and earlier stage-record files. `record` creates a new state file exclusively and refuses an already-stale upstream record; `check` recursively detects changed or missing declared files and returns `BLOCKED`. It does not discover unlisted dependencies, version changes, incorrect assumptions or scientific approvals. Include relevant code, configuration, database metadata and upstream state as inputs where applicable; record only files you are entitled to use and do not publish private paths. Database label files cannot prove the contents of an ecoinvent database. State stores absolute local paths, so relocation requires new records.

Example, from the repository root, with user-selected non-existing state path:

```sh
python3 piezocatalysis-lca-modeling/scripts/workflow_state.py record \
  --stage foreground --input /path/to/foreground.json --output /path/to/inventory.csv \
  --output /path/to/inventory.csv.manifest.json --state /path/to/new-foreground-state.json
python3 piezocatalysis-lca-modeling/scripts/workflow_state.py check /path/to/new-foreground-state.json
```

Use `--require-input /path/to/file` for each critical input and also provide it with `--input`; missing declarations fail, while unlisted dependencies cannot be discovered automatically. For a downstream stage add `--depends-on /path/to/new-foreground-state.json` and list its own input and output files. A failed downstream check preserves previous files. Restore the original upstream inputs or rerun affected stages to **new** output and state paths; do not edit a prior state to conceal a change. Independently inspect the state record before relying on a claimed dependency list.
