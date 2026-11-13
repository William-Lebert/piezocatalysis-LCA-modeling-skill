# openLCA Workflow

## Contents

1. Capability audit
2. Manual workflow
3. IPC workflow
4. Safe updates
5. Calculation and export
6. Troubleshooting

## 1. Capability audit

Before modeling, record:

- openLCA version;
- active user-data directory and workspace;
- database name, version, system model, and license status;
- imported LCIA method package and version;
- active database in the UI;
- IPC port and whether the server is running.

The workspace contains application metadata and database connections; the installation directory contains program files. Keep project data outside the installation root when possible.

## 2. Manual workflow

1. Import or open the licensed background database.
2. Import compatible LCIA methods.
3. Create foreground flows with correct flow type and unit group.
4. Create one preparation process per catalyst route.
5. Create one treatment process per operating mode and catalyst route.
6. Link background providers and inspect each reference product.
7. Create product systems using the intended reference process.
8. calculate absolute LCIA and contribution results.
9. export results and record database/method identifiers.

## 3. IPC workflow

Use IPC when reproducibility or batch calculation is required.

### Local read-only adapter (openLCA 2.x JSON-RPC)

`scripts/openlca_readonly.py` uses only the Python standard library and connects to `127.0.0.1` at the explicitly supplied IPC port. It supports listing descriptors and calculating an **existing** product system. Its method allowlist has no database create, update, import or delete operation. Calculating schedules a temporary server result and `result/dispose` frees that temporary result; this is not a persistent database write. It does not start or configure the server.

```sh
python scripts/openlca_readonly.py --port 8080 list --type ProductSystem
python scripts/openlca_readonly.py --port 8080 list --type ImpactMethod
python scripts/openlca_readonly.py --port 8080 list --type FlowProperty
```

Review the active database in openLCA and select exact UUIDs. A sample calculation command is in `assets/examples/synthetic-openlca/README.md`. The adapter requires product-system, impact-method, unit and flow-property UUIDs, amount, functional-unit description, and user-supplied version/database/system-model labels. It verifies system and method IDs against descriptors, but **cannot independently identify the active database or verify the unit/property relationship**. The user must confirm those in openLCA; the exported metadata explicitly marks labels as user asserted. Descriptor lists and reports may contain private dataset information; keep them local and respect database licenses.

It polls result state with a timeout, returns absolute impacts and category-specific process contributions, checks their numerical sum where available, and attempts result disposal even after errors. Empty impact results, server errors, non-finite numbers and disposal failures stop the command rather than returning fabricated zeroes. Empty contributions and unreconciled sums are warnings. Result output is JSON on standard output; save it to a new file and do not overwrite an input. The API doesn't expose every assumption or guarantee that results are scientifically valid: check the product-system reference flow, unit, LCIA method, model context and any warnings independently.

Contribution reconciliation uses relative tolerance `1e-6` and zero fixed absolute tolerance, and reports the chosen tolerance. A zero total requires an exactly zero contribution sum; rounding or cancellation may therefore trigger a warning that needs investigation.

The synthetic test uses a local mock server, not an openLCA database. Actual compatibility depends on the running openLCA and server version. This implementation follows the official [descriptor](https://greendelta.github.io/openLCA-ApiDoc/data/get_descriptors.html), [calculation](https://greendelta.github.io/openLCA-ApiDoc/results/calculate.html), and [result lifecycle](https://greendelta.github.io/openLCA-ApiDoc/results/results.html) documentation.

### General IPC procedure

1. Ask the user to open the target database and start the IPC server.
2. Connect to the confirmed port.
3. Read descriptors before writing; verify the database contains the target process, flow, provider, and method.
4. Use stable UUIDs in a model manifest rather than repeated name searches.
5. Create or update the smallest explicit set of entities.
6. calculate through a `CalculationSetup` using the product-system target, target unit, flow property, and impact method.
7. poll result state, stop on errors, export totals and contributions, then dispose the result.

Do not assume schema fields across openLCA versions. Inspect the installed IPC/schema package when upgrading.

## 4. Safe updates

- Export the target process JSON before mutation.
- Make scripts idempotent by identifying prior generated exchanges.
- Preserve existing provider links unless intentionally remapped.
- Never replace missing data with zero.
- Write a manifest containing process IDs, product-system IDs, method IDs, database name, and model tag.
- Re-read the modified process and representative results after writing.

## 5. Calculation and export

For every route, export:

- total impacts by category;
- process or flow contributions;
- reference amount and unit;
- calculation setup metadata;
- warnings and exclusions;
- absolute results before normalization.

Use one calculation setup per LCIA method if the API or database package requires it. Keep CED separate from midpoint categories when it is delivered as a distinct method.

## 6. Troubleshooting

- **Connection refused:** IPC server is not running, the port differs, or a firewall blocks localhost.
- **Missing entity:** wrong active database, stale UUID, or entity not imported.
- **Empty impacts:** no LCIA method, elementary-flow mismatch, or disconnected product system.
- **Implausibly identical routes:** shared foreground process, wrong reference process, identical provider links, or normalization performed on already normalized values.
- **Startup failure after workspace changes:** preserve database folders, reset only Eclipse/UI metadata after reading the log, and avoid placing the workspace inside the program installation.
