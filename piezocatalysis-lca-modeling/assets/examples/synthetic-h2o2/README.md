# Synthetic piezocatalytic H2O2 inventory

All values in `case.json` are fictional and are not copied from a publication. The case expresses a functional unit of 1 kg **net accumulated** H2O2. Each campaign is assumed to yield 0.1 g net product and use 0.01 g freshly allocated dry catalyst; a preparation batch yields 5 g dry catalyst. Thus the functional unit needs 10,000 equivalent campaigns and 20 preparation batches. A 40 W, 6 min ultrasound step uses 0.004 kWh per campaign, or 40 kWh per functional unit. These are mathematical test values, not a scale-up prediction.

```sh
python3 piezocatalysis-lca-modeling/scripts/h2o2_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-h2o2/case.json \
  --inventory-csv /tmp/piezolca-h2o2-example.csv
python3 piezocatalysis-lca-modeling/scripts/inventory_handoff.py \
  --inventory /tmp/piezolca-h2o2-example.csv
```

The CSV and its `.manifest.json` must be kept together; the CSV is already per functional unit and the project scaler rejects applying campaign scaling again. Actual background mapping requires review. The module takes the declared net product mass; record its method, sampling and any externally added H2O2 adjustments in `product_definition`. It does not infer gross generation from net accumulation, claim recovery, subtract oxidant consumption, or allocate co-products. `net_accumulated` and `recovered_product` are distinct functional-unit bases. Fresh dry catalyst per campaign must include all newly allocated material and makeup; there is no automatic credit for recovered catalyst. Disposal requires a specifically identified catalyst waste activity, not just a generic wastewater output.

Unknown or zero product yields leave scaled amounts unavailable. The catalyst and wastewater routes, electricity boundary, co-reagents and product measurement need real evidence. A product-based result cannot be treated as a wastewater-treatment result without a separate function and consistent system boundary.

## Evidence and research delivery / 证据与科研交付

`observations.csv` and `evidence.json` are fictional fixtures created from the fictional model; they are not independent measurements. The evidence checker supports the H₂O₂ product foreground and verifies value/unit/class links, the paired inventory, product basis and per-functional-unit allocation dependencies. The product definition, analytical method, corrections for externally added H₂O₂ and catalyst destination remain researcher declarations and require independent verification. Net accumulation does not prove recovery, total generation or in-situ consumption.

Run with a new directory from the repository root:

```sh
D=$(mktemp -d)
python3 piezocatalysis-lca-modeling/scripts/h2o2_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-h2o2/case.json \
  --inventory-csv "$D/inventory.csv" > "$D/foreground-report.json"
python3 piezocatalysis-lca-modeling/scripts/evidence_chain.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-h2o2/evidence.json \
  --foreground piezocatalysis-lca-modeling/assets/examples/synthetic-h2o2/case.json \
  --inventory "$D/inventory.csv" --manifest "$D/inventory.csv.manifest.json" > "$D/evidence-report.json"
```

Use the existing `research_delivery.template.json` to point `foreground`, `inventory`, `inventory_manifest`, `evidence_spec`, `evidence_report` and `evidence_sources.synthetic-h2o2` at these files, then call `research_delivery.py assemble` and `verify`. Product-basis and definition mismatches are rejected. A missing or zero product quantity cannot be used to attach an impact calculation. A delivery can contain previously calculated results and coverage, but it does not calculate or authenticate them; exchange binding and applicability still need independent review. The cyclic-specific domain review and cyclic plot do not support an H₂O₂ product foreground. Missing data, proxies and unknown catalyst fate remain visible.

10 项证据记录均为合成案例数据。产品定义、检测方法、外加 H₂O₂ 修正与催化剂去向是用户声明，必须对照原始记录复核；哈希匹配不证明测量真实。产品缺失或为零时不生成可使用的每功能单位计算量，也不能将已有影响结果附会为该模型结果。已有计算材料可纳入本地交付，但交付不会重跑 openLCA；逐循环专用的领域审查和逐循环图不适用于产品前景。

For a published inventory with an explicitly reported H₂O₂ production reference, `product_basis` can be `reported_production`. Use `reported_product_per_campaign` for the mass corresponding to that reference and keep the paper's definition in `product_definition`. Document any molar to mass conversion and its source. Trace this field in the evidence specification. Use the reported basis to reconstruct the published inventory and review its product definition before comparing with net accumulation or recovered product.
