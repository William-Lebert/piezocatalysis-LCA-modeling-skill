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
