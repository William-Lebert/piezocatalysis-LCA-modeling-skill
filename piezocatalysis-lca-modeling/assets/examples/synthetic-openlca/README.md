# Synthetic openLCA IPC example

`tests/test_openlca_readonly.py` starts an isolated loopback JSON-RPC **mock** and supplies invented product-system/method IDs and result values. The mock returns a synthetic impact of 3.2 kg CO2-eq with two contributions, 1.2 and 2.0; the test independently checks that they sum to 3.2. No real database, licensed data, or openLCA engine is involved. From the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_openlca_readonly.py' -v
```

It checks descriptor reads, successful output and result disposal, missing IDs, errors, timeouts, missing contributions and disallowed database-write methods. Test IDs in the file are mock-only and will not exist in a real database.

For an already-running local server, omit `--port` to probe `127.0.0.1` ports 8080 and 18808, or use `--candidate-ports 8080,9000` before the subcommand. An ambiguous match is rejected, and a protocol response does not authenticate the software or identify its database. On verified macOS openLCA 2.7.0, `--start-local --workspace PATH --database NAME` instead starts a guarded temporary server on a clone; see `references/openlca-workflow.md` for the requirements and limits.

已有本机服务运行时，可省略 `--port` 自动探测 8080、18808，或在子命令前使用 `--candidate-ports 8080,9000`。多个匹配将被拒绝；协议响应不能认证软件或确认数据库身份。已验证的 macOS openLCA 2.7.0 还可使用 `--start-local --workspace 路径 --database 库名` 在副本上自动启动受限服务；条件和限制见 `references/openlca-workflow.md`。

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
