# SimaPro Workflow

## Contents

1. Capability audit
2. Recommended execution paths
3. Direct Import
4. Excel external links
5. COM automation
6. Validation and recovery

## 1. Capability audit

Record the installed SimaPro version, database, project, edition, licensed modules, user permissions, and available import/export functions.

Treat these as separate capabilities:

- SimaPro application can open;
- Developer edition is installed;
- COM class is registered;
- the license includes COM access;
- the current user can write the target project/database;
- LCIA calculations and exports are authorized.

An error such as `No license for COM` means the connector reached the COM layer but the active license does not grant COM use. Do not attempt database-file workarounds.

## 2. Recommended execution paths

1. **Human-confirmed import:** AI prepares and validates files; the user imports, calculates, and exports. Use this as the stable default.
2. **Excel external links:** AI updates a controlled workbook; SimaPro reads linked parameter cells. Use for recurring parameter updates.
3. **COM automation:** use only after an explicit entitlement check and a read-only test with official API/type-library documentation.

## 3. Direct Import

Prepare software-neutral LCI first, then map it to the installed SimaPro import template. Typical fields include process name, category, unit, time period, geography, input/output name, amount, unit, and direction. Exact columns depend on the installed version and template.

After import:

- inspect at least one process from each route;
- confirm reference product and amount;
- confirm `kWh` did not become `J` or another unit;
- verify input/output direction and waste signs;
- verify provider mappings and unmatched flows;
- calculate a small test result before bulk import.

## 4. Excel external links

Use a minimal compatibility workbook before building a full parameter file.

Practical compatibility rules observed in SimaPro 9 workflows:

- test legacy `.xls` if `.xlsx` produces `List index out of bounds (0)`;
- keep a visible first worksheet with a simple ASCII name such as `Sheet1`;
- place numeric values in plain cells without merged ranges, tables, macros, or dynamic arrays;
- avoid blank leading sheets and hidden-only workbooks;
- link one probe cell first, verify a dependent parameter, then expand;
- keep the workbook path stable and avoid cloud-sync placeholders.

Treat these as compatibility heuristics, not universal software guarantees.

## 5. COM automation

Before writes:

1. confirm COM entitlement in the license;
2. inspect the installed type library or official developer documentation;
3. instantiate the class with a read-only probe;
4. read the active project and a harmless descriptor;
5. back up the project/database;
6. run one test write in an isolated project;
7. verify the result in the UI.

Do not copy unverified method names from generic examples. COM APIs vary by version and entitlement. Never write directly to SimaPro database files.

## 6. Validation and recovery

- keep an import log and an exported process list;
- version every workbook and input package;
- use reversible test projects;
- stop after repeated authorization or schema errors;
- export absolute LCIA results and compare them with an independent scaling calculation;
- if COM is unavailable, continue through Direct Import or external links rather than blocking the LCA study.
