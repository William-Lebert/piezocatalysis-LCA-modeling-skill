# Synthetic cycle service and sample links / 合成逐循环服务与样品

All numbers, campaign and sample identifiers are fictional. `observations.csv` is derived from the fictional foreground rather than an independent laboratory record. Its optional `campaign_id,sample_id,cycle_id,sample_role` columns are explicitly repeated in each applicable link in `evidence.json`. The checker verifies declarations against the row, cycle and influent/effluent role; it cannot establish the actual identity or handling of a sample. An omitted sample link remains unverified in the service review. IDs must be unique across cycles and roles within a campaign; volume and concentration should identify the same sample for the relevant role.

`service.json` declares a fictional 10 mg/L threshold, not a regulatory standard. Exact measurements are compared with the threshold; a below-limit observation is only numerically consistent with the threshold when the detection/quantification limit is no greater than it. Missing observations and intervals that cross a criterion stay unresolved. Volume changes, unknown energy or catalyst losses are flagged. The report records observed cycles separately from a declared observed, assumed or extrapolated lifetime. Numerical outcome is provisional; it is not proof of compliance, representative sampling or comparable service.

From the repository root, use fresh output paths:

```sh
D=$(mktemp -d)
python3 piezocatalysis-lca-modeling/scripts/cyclic_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/foreground.json \
  --inventory-csv "$D/inventory.csv" > "$D/foreground.json"
python3 piezocatalysis-lca-modeling/scripts/evidence_chain.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-cycle-service/evidence.json \
  --foreground piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/foreground.json \
  --inventory "$D/inventory.csv" --manifest "$D/inventory.csv.manifest.json" > "$D/evidence.json"
python3 piezocatalysis-lca-modeling/scripts/cycle_service_review.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-cycle-service/service.json \
  --foreground piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/foreground.json \
  --evidence "$D/evidence.json" > "$D/service.json"
```

A cyclic research delivery can include `cycle_service_spec` and `cycle_service_report` together with the paired evidence spec/report. The delivery rebuilds and checks the service report and preserves its review issues. The existing LCI is still scaled by apparent pollutant removal; the tool does not convert or recalculate it as treated-water volume. Researcher review is required before any comparison, even if a declared threshold is met.

本例的样品编号和 10 mg/L 阈值均为虚构声明。可选的批次、样品、循环和进出水角色须与来源行一致；不提供时仍可处理旧文件，但在服务检查中标为待核对。删失上限、缺失值、体积变化、能耗和催化剂损失均按实际状态保留。已有清单仍以表观去除量为功能单位，不自动换算为达标水量；数值满足自设阈值不代表法规达标或两个方案可比。
