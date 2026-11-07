# Synthetic openLCA IPC example

`tests/test_openlca_readonly.py` starts an isolated loopback JSON-RPC **mock** and supplies invented product-system/method IDs and result values. The mock returns a synthetic impact of 3.2 kg CO2-eq with two contributions, 1.2 and 2.0; the test independently checks that they sum to 3.2. No real database, licensed data, or openLCA engine is involved. From the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_openlca_readonly.py' -v
```

It checks descriptor reads, successful output and result disposal, missing IDs, errors, timeouts, missing contributions and disallowed database-write methods. Test IDs in the file are mock-only and will not exist in a real database.

For a real calculation, first open the intended database and start its IPC server in openLCA, inspect system/method descriptors, and independently confirm the functional-unit, unit and flow-property UUIDs and metadata. Replace every `YOUR_...` value below. The adapter does not create a test database or model. Save output to a new local file.

```sh
python3 scripts/openlca_readonly.py --port 8080 calculate \
  --system-id YOUR_PRODUCT_SYSTEM_UUID --method-id YOUR_IMPACT_METHOD_UUID \
  --amount 1 --unit-id YOUR_UNIT_UUID --flow-property-id YOUR_FLOW_PROPERTY_UUID \
  --unit-label 'YOUR_UNIT_NAME' --functional-unit 'YOUR_FUNCTIONAL_UNIT' \
  --database-label 'YOUR_DATABASE' --database-version 'YOUR_DATABASE_VERSION' \
  --system-model 'YOUR_SYSTEM_MODEL' --software-version 'YOUR_OPENLCA_VERSION' \
  > new-local-result.json
```

The database name, version, system model, software version, unit label and functional unit are user assertions; the program cannot verify them. A normal exit does not certify model correctness or license status. The output records warnings and absolute impacts, without normalizing the data.
