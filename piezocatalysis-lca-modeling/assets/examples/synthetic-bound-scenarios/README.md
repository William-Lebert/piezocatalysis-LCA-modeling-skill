# Captured cyclic scenarios / 逐循环情景绑定

`scenario_binding.py` captures each scenario's already generated cyclic foreground, per-functional-unit inventory/manifest, reviewed mapping and model binding, then uses a read-only openLCA session to preflight the providers, snapshot the product system, linked processes, method, selected category and parameters before and after a fresh calculation, and check each foreground exchange, unit and provider against the plan. It fails if the observed entities change during that calculation, if the model or units differ, or if a supplied parameter override is missing, ambiguous or protected. An unknown or unconnected exchange remains unresolved; it is never treated as zero.

The file `capture.template.json` describes required inputs. Use distinct paths for each scenario, prepared mappings/assignments, product system binding and a new output. For a verified macOS 2.7.0 installation, set `start_local` to the existing database's workspace and database name. The guarded launcher opens a temporary clone and closes it; it does not create or edit product systems. Replace all identifiers, context and placeholder paths with a model that has already been created and reviewed. Never supply licensed database files as output or publish private database-derived results without permission.

```sh
python3 piezocatalysis-lca-modeling/scripts/scenario_binding.py capture /path/to/case-capture.json --output /path/to/new-bound-case.json
python3 piezocatalysis-lca-modeling/scripts/scenario_binding.py compare \
  --baseline /path/to/base-bound.json --scenario /path/to/case-bound.json \
  --baseline-input /path/to/base-foreground.json --scenario-input /path/to/case-foreground.json \
  --contexts /path/to/two-ordered-contexts.json --output /path/to/new-comparison.json
```

The ordered context declarations use the existing `scenario_comparability.py` format: baseline first, scenario second. Comparison rechecks source-to-plan and bound exchanges; it rejects inconsistent system/binding, method, boundary, background-provider snapshots or mappings. It preserves actual impacts and disables the linear approximation when foreground exchanges are unresolved, model parameters or overrides are present, contributions offset, a nonzero contribution is unaccounted for, or the baseline is zero. No automatic ranking is authorized. A direct `port` may instead be used only for an already running local IPC server; that connection is not authenticated. Product-system parameters and database/functional-unit labels are still user-asserted, even when snapshots match. Coverage checks concern the selected category and requested flow IDs; they are not a full LCIA-factor or UPR supply-chain audit.

本功能逐情景核对输入清单、实际产品系统交换、provider 和参数快照，计算前后检查受检对象是否变化；已绑定不等于科研结论已获批准。自建或外部 IPC 服务身份、数据库名称、功能单位标签、产品功能和代理适用性仍需独立核实。存在未连接项、参数或抵消贡献等情况时，保留实际重算值，但不提供线性估计；不对真实方案自动排名。

When a process contains otherwise identical exchanges, provide `exchange_internal_id` in the corresponding `binding.activities` entries. Use openLCA’s exchange `internalId` from the process data or product-system links. The database exchange primary key and the flow UUID are different identifiers.
