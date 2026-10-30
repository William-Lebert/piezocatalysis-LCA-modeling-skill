# Calculations and Quality Assurance

## Contents

1. Core equations
2. Inventory scaling
3. Normalization
4. QA checks
5. Stop conditions

## 1. Core equations

Pseudo-first-order removal:

`r = 1 - exp(-kobs * t)`

Pollutant removed:

`m_removed = C0 * V * r`

Equipment electricity:

`E = P * t`

Batch share for a catalyst dose:

`share = catalyst_dose / dry_batch_yield`

Preparation electricity assigned to one run:

`E_prep_run = E_prep_batch * share`

Treatment-service scaling:

`scale_FU = target_removed_mass / m_removed_run`

`inventory_FU = inventory_run * scale_FU`

First-order EE/O:

`EEO = 1000 * ln(10) * P / (60 * V * kobs)`

with `P` in kW, `V` in L, and `kobs` in min-1.

## 2. Inventory scaling

Maintain separate tables for:

- synthesis batch inventory;
- catalyst output/yield;
- treatment run inventory;
- catalyst lifetime/reuse allocation;
- functional-unit inventory.

Never scale a precursor input by catalyst dose without first dividing by the actual dry batch output. For theoretical yields, label the output as calculated or scenario and do not replace an available measured yield.

For solutions, distinguish solution volume, solution density, solute mass fraction, and resulting solute mass. Preserve the solvent/water balance when material.

## 3. Normalization

For visualization across routes, normalize each impact category independently:

`normalized_ij = absolute_ij / max_j(absolute_ij)`

or use a stated external reference. Never normalize an already normalized table. Do not compare the height of different impact categories as if they shared physical units. Publish the absolute table in the SI.

## 4. QA checks

### Scope

- functional unit appears in every result table;
- preparation-only and treatment-service results are not mixed;
- PZC/PC/PPC energy boundaries are explicit;
- illumination decision is documented;
- database system model and LCIA version are recorded.

### Inventory

- all amounts are numeric and non-negative unless a documented credit is intended;
- input/output directions are correct;
- units convert to the provider reference unit;
- dry catalyst output equals the yield basis;
- washing cycles, solvent density, and recovery are explicit;
- electricity equals power times time for each equipment item.

### Software

- reference process and target unit are correct;
- product systems are connected;
- provider IDs match the manifest;
- calculation errors are not replaced by zeros;
- result categories match the selected method.

### Results

- contribution totals reconcile with total impacts within numerical tolerance;
- route ordering is plausible from the inventory and not solely a plotting artifact;
- normalized figures reproduce from absolute results;
- at least one hand calculation matches the model scaling;
- sensitivity cases reveal whether rankings are robust.

## 5. Stop conditions

Stop and resolve before publication when:

- a dominant input lacks a provider or proxy rationale;
- routes use different functional units or system models;
- the reference product is wrong;
- a COM/IPC write cannot be verified in the UI or by re-read;
- a normalized figure is available but the absolute table is missing;
- the preferred route changes under a reasonable unresolved assumption and this is not reported.
