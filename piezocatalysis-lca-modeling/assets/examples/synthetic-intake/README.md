# Synthetic intake / 合成实验记录接入

Run from the repository root. Choose a new output directory each time.

```bash
python3 piezocatalysis-lca-modeling/scripts/real_case_intake.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-intake/exact-intake.json \
  --output-dir /tmp/piezolca-intake-exact
python3 piezocatalysis-lca-modeling/scripts/evidence_chain.py \
  /tmp/piezolca-intake-exact/evidence.json \
  --foreground /tmp/piezolca-intake-exact/foreground.json \
  --inventory /tmp/piezolca-intake-exact/inventory.csv \
  --manifest /tmp/piezolca-intake-exact/inventory.csv.manifest.json
```

`foreground-template.json` describes the campaign structure and target units. The observation sheet fills each quantity with the single record marked `selected=yes`. Keep repeats in the sheet as `selected=no` and give a reason for the chosen record. A JSON pointer in `target` identifies the quantity. Water volume and concentration share the campaign, cycle and sampling event ID for their respective influent or effluent role. The volume represents the experimental stream, so enter the batch volume instead of the instrument aliquot volume.

For a tabular export made from a separate raw file, register the original in `raw_records` and set `original_id` and `original_locator` on the exported row. `meter-log.csv` illustrates this route. Both source hashes are recorded. Check the cited instrument cell against the export during review. Leave both fields blank to refer to the observation CSV itself. The generated `evidence.json` keeps paths to these original files. Keep access to them when rerunning the audit.

For a meter energy total, enter `metered_energy` and use an energy quantity. For power and time, declare `metered_input_power`, `instrument_reading`, or `rated_power`, and `elapsed_runtime` or `specified_runtime`, as appropriate. Estimated direct energy uses `estimated_energy`. Use a single energy accounting route per activity and retain instrument identifiers in the observation file.

The exact case yields 32.5 mg of apparent removal over the two cycles. At a 65 mg functional unit, 0.12 kW × 0.5 h becomes 0.12 kWh/FU, and 90 Wh becomes 0.18 kWh/FU for the two respective ultrasound activities. The first effluent concentration is explicitly zero. Run `gaps-intake.json` for separate below-LOD, below-LOQ and missing runtime records. The limits become 0.5 and 1.5 mg/L and bound apparent removal at 35.9–38 mg. Exact scaling remains unavailable in that case. All observations and instrument names are fictional.
