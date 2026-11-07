# Synthetic treatment-service example

All numbers, substances, datasets and assumptions in this folder are invented and do not represent measurements or an actual database. From the skill folder, run:

```sh
python scripts/audit_and_scale_inventory.py \
  --inventory assets/examples/synthetic-treatment/inventory.csv \
  --mapping assets/examples/synthetic-treatment/dataset_mapping.csv \
  --parameters assets/examples/synthetic-treatment/parameters.json \
  --system Synthetic-A --reference-flow 'dry catalyst'
```

The standard output is a JSON report; save it to a **new** file when needed. It must not replace any input file. The example defines 1 L at 20 mg/L influent and 10 mg/L outlet, so one run removes 10 mg. A 100 mg removal functional unit requires 10 runs. Each run uses 1 g catalyst; 5 g is made per batch and the effective lifetime is 2 uses. With constant performance and evenly allocated preparation, 10 × 1 / 5 / 2 = 1 synthesis batch is allocated per functional unit. Therefore the precursor is 10 g (0.01 kg in the illustrative mapped unit), preparation electricity is 2 kWh, treatment electricity is 1 kWh, and wastewater is 10 L.

`expected-report.json` contains the reproducible output for this example. Parameter values must be JSON numbers; sources and evidence classes are required for the service definition and each numeric parameter.

The wastewater is intentionally unmapped and appears with a null dataset amount and warning; a null is unknown, not zero. Mapping review is pending and the proxy is hypothetical. This is an inventory-scaling check, not an LCIA result or a validated scientific model. It does not model changing cycle performance, extra regeneration, or recovery separately.
