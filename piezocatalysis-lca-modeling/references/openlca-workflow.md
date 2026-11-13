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

`scripts/openlca_readonly.py` uses only the Python standard library and connects to `127.0.0.1`. When no port is specified, it probes only 8080 and 18808 with a read-only descriptor request; use `--candidate-ports 8080,9000` to specify up to 16 candidate ports. If more than one responds, it refuses to choose; use `--port` explicitly. Discovery tests protocol behavior, not service identity or database identity, and returns the selected port in its JSON output. It supports listing descriptors and calculating an **existing** product system. Its method allowlist has no database create, update, import or delete operation. Calculating schedules a temporary server result and `result/dispose` frees that temporary result; this is not a persistent database write. Existing servers are not reconfigured by the adapter.

### Inventory mapping candidates / 清单映射候选

Start with `assets/examples/synthetic-mapping/README.md`. For a closed local database on the verified macOS installation, replace the placeholders below with your inventory, mapping table, workspace and database information:

```sh
python scripts/dataset_candidates.py --inventory /path/to/inventory.csv \
  --mapping /path/to/mapping.csv --start-local --workspace /path/to/openLCA-data-1.4 \
  --database YOUR_DATABASE --database-version YOUR_VERSION --system-model YOUR_MODEL \
  --format csv > /path/to/new-local-candidates.csv
```

Alternatively provide `--port PORT` for a running local service or `--descriptors FILE` for the JSON output of `openlca_readonly.py list --type Process`. With `--start-local`, `--database` is the actual directory name of the cloned source database. With a running service or saved descriptors the database identity is user asserted, not verified. Database name, version and system model must match a mapping row exactly; a mismatch blocks candidates for that row.

The lookup searches an explicit `process_uuid` first and never falls back to a name when it is missing. Otherwise it searches the dataset name case-insensitively and filters by exact location if one is provided. No automatic selection is made: `needs_review` means a single candidate, `ambiguous` means multiple candidates, and `not_found` means none. Invalid UUIDs, database or foreground mismatch, and unsupported or inconsistent unit conversions are reported separately. More than 20 matches are counted but only the first 20 are listed. Unmapped inventory flows use their foreground names for searching and remain unmapped.

Process descriptors do not supply the verified reference product, flow property, unit or all exchange details. Check those in openLCA, including waste treatment direction and technology, then manually enter the selected process UUID, reference flow UUID, flow property UUID, unit UUID, source and date in the mapping table. Review the conversion factor and mark `review_status` only after confirmation. Existing mapping files without the new optional columns remain supported. Candidates and CSV exports can contain licensed database information; store them locally and follow the applicable database license.

```sh
python scripts/openlca_readonly.py list --type ProductSystem
python scripts/openlca_readonly.py --port 8080 list --type ProductSystem
python scripts/openlca_readonly.py --port 8080 list --type ImpactMethod
python scripts/openlca_readonly.py --port 8080 list --type FlowProperty
python scripts/openlca_readonly.py --port 8080 parameters --system-id PRODUCT_SYSTEM_UUID
```

For actual one-parameter-at-a-time scenario recalculation, see `assets/examples/synthetic-parametric/README.md`. The read-only guard also permits `data/get/parameters`; the requested values are passed only in a temporary calculation setup, not written back to the database. Parameters are matched by name and context; confirm their units and the model's scientific assumptions.

#### Optional guarded automatic startup on macOS

For the specifically verified, signed macOS openLCA 2.7.0 distribution, close the database in openLCA first, then run, replacing both paths with your own:

```sh
python scripts/openlca_readonly.py --start-local \
  --workspace /path/to/openLCA-data-1.4 --database YOUR_EXISTING_DATABASE \
  list --type FlowProperty
```

This starts openLCA automatically for the command, then stops the process. It clones the existing Derby database and workspace libraries using APFS `clonefile`, never passing the source database to the server. If cloning, signature checks, pinned 2.7.0 component hashes, required Derby files, lock checks, local binding, or server restrictions cannot be verified, startup fails. Other openLCA releases and platforms are not supported by this launcher. The database may be large; cloning requires a compatible local filesystem and free space for changes. A forced crash can leave an owner-only temporary clone in the system temporary directory; review it before removing it. Do not copy databases without the necessary license rights.

On macOS, openLCA 2.7.0 GUI startup can create Eclipse caches and a Derby log inside the signed application bundle. If strict verification fails, the launcher copies the application into its private temporary directory while excluding only these known runtime artifacts, then verifies the entire copied bundle and the pinned components before starting it. It does not modify the installed app; other signature failures still stop startup. The default path remains `/Applications/openLCA.app`, and `--openlca-app` selects another installation. Close the GUI database before cloning it.

When creating foreground exchanges, check the unit on the **exchange itself**, not only the provider's quantitative reference or the flow descriptor. For example, an electricity flow can have MJ as its reference unit while the selected provider's exchange is in kWh. Explicitly set the intended unit and flow-property factor, then verify the saved exchange and provider link before calculating.

The guarded launcher applies the separately provided Java guard at process startup: it binds the IPC listener to `127.0.0.1`, limits registered RPC methods to descriptor reads, calculation and result management, and terminates the child when its parent pipe closes. It checks the resulting listener belongs to the launched process. This is a narrow tested safeguard, not authentication: other local processes may access the listening port while it runs. The upstream 2.7.0 `--readonly` flag alone was observed accepting `data/put`, so the launcher does not rely on it as its sole protection. A JVM process and an embedded database may write temporary state to the clone. The source database must be closed and remain unchanged during cloning; lock-file checks cannot prevent every concurrent-access race. Check openLCA and database licenses and keep outputs private as needed.

The independent guard source and reproducibility notes are in `scripts/openlca_guard/`. For a real software integration check with a temporary, fictional database, run `python3 tests/integration_openlca_guard.py` from the repository root. This optional test requires the verified macOS openLCA 2.7.0 app and APFS; ordinary unit tests do not require openLCA.

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
