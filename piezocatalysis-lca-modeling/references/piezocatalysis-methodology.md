# Piezocatalysis LCA Methodology

## Contents

1. Technology modes
2. Functional units
3. System boundaries
4. Kinetics and treatment scaling
5. Energy accounting
6. Catalyst lifetime and reuse
7. Scale-up and comparative claims

## 1. Technology modes

- **PZC (piezocatalysis):** mechanical excitation is the intended driving input. Include ultrasound, vibration, fluid shear, milling, or other mechanical energy that is causally required.
- **PC (photocatalysis):** photon input is the intended driving input. Include artificial illumination electricity when it is required by the modeled system.
- **PPC (piezo-photocatalysis):** mechanical and photon inputs jointly provide the service. Report their electricity terms separately before summing.

Do not infer that PPC is environmentally preferable from a higher kinetic constant alone. A higher rate may reduce residence time, but total impact also depends on power, catalyst demand, synthesis burden, lifetime, solvent use, and background electricity.

## 2. Functional units

Choose the functional unit from the decision being answered.

| Research question | Recommended functional unit | Minimum conditions to report |
| --- | --- | --- |
| Which synthesis route has lower production impact? | 1 g dry catalyst at gate | purity, yield, moisture basis, lab/industrial scale |
| Which catalyst treats pollution with lower burden? | removal of a specified pollutant mass | C0, volume, time, outlet/removal definition, catalyst dose |
| Which reactor provides cleaner water? | 1 m3 water meeting a specified outlet criterion | influent and effluent quality, flow, residence time |
| How electricity-efficient is degradation? | one order of concentration reduction | power boundary, reactor volume, kobs or C0/Ct |

Never combine a catalyst-production result per gram with a treatment-service result per pollutant removed in the same ranking without an explicit conversion model.

## 3. System boundaries

### Preparation-only, cradle-to-gate

Include precursor production, reaction solvent, washing media, hydrothermal/solvothermal treatment, calcination or drying, centrifugation/filtration, yield losses, and direct waste treatment. Exclude treatment operation and catalyst performance.

### Cradle-to-treatment

Add catalyst demand per service, catalyst recovery/reuse, reactor electricity, ultrasound, illumination when causal, mixing, pumping, temperature control, separation after use, and spent-catalyst treatment.

### End of life

Model recycling credit only when a defensible recovery route, recovery rate, displaced product, and allocation/system-expansion rule are available. Otherwise show disposal and recycling as separate scenarios.

## 4. Kinetics and treatment scaling

For pseudo-first-order kinetics:

`C_t/C_0 = exp(-k_obs t)`

`removal_fraction = 1 - exp(-k_obs t)`

`removed_mass_mg = C0_mg_L * V_L * removal_fraction`

For a functional unit of pollutant mass removed, calculate the number of equivalent treatment runs as:

`runs_per_FU = target_removed_mass / removed_mass_per_run`

Scale catalyst demand and treatment electricity by `runs_per_FU`. Do not replace measured kinetics with reuse-cycle removal rates unless the research question explicitly concerns lifetime behavior.

## 5. Energy accounting

Calculate equipment electricity from measured or documented active power and run time:

`E_kWh = P_kW * t_h`

Classify energy by stage:

- preparation: hydrothermal reactor, oven, furnace, centrifuge, filtration, drying;
- treatment: ultrasound, illumination, mixing, pumping, heating/cooling;
- ancillary: analytical equipment and laboratory overhead, normally excluded unless material to the goal.

### Illumination decision

If an artificial lamp is an engineering requirement, include it. If the lamp only simulates freely available natural sunlight and the modeled deployment uses sunlight, a sunlight baseline may exclude lamp electricity. State this as a prospective scenario, retain a laboratory-electricity sensitivity case, and avoid describing the exclusion as a measured reduction.

### EE/O

For first-order degradation with power in kW, volume in L, and `kobs` in min-1:

`EE/O = 1000 * ln(10) * P / (60 * V * kobs)`

Numerically, `EE/O ≈ 38.4 * P / (V * kobs)` in kWh m-3 order-1.

Use only the power terms that drive the modeled degradation mode. Catalyst preparation energy is not part of EE/O, although it remains part of LCA.

## 6. Catalyst lifetime and reuse

Allocate preparation burden over total lifetime pollutant removal:

`lifetime_removed_mass = sum(C0_i * V_i * removal_fraction_i)`

`prep_burden_per_FU = batch_prep_burden * catalyst_share / lifetime_removed_mass * target_FU`

If cycle conditions differ, calculate each cycle separately. Do not use a simple arithmetic mean of removal percentages when concentration, volume, or catalyst recovery changes.

The optional `scripts/audit_and_scale_inventory.py` handles only a simplified equal-performance service: `runs_per_FU = target_removed_mg / removed_per_run_mg` and `preparation_batches_per_FU = runs_per_FU × catalyst_dose_g / dry_batch_yield_g / effective_uses`. Each preparation inventory row is per synthesis batch; each treatment row is per treatment run. `effective_uses` is an explicitly sourced assumption, not a measured recovery fraction. It may represent an average effective lifetime only when the equal-dose, equal-removal and allocation assumptions are appropriate. For changing performance, replacement, regeneration or cycle-specific losses, use an explicit cycle-by-cycle model instead; this tool does not model those processes automatically.

For experimental inputs, `scripts/experimental_foreground.py` calculates apparent concentration decrease from the declared liquid volume and influent/outlet concentrations, reports catalyst loading, and creates a per-batch/per-run inventory. It also reports dry-catalyst production and treatment functional units separately; see `assets/examples/synthetic-foreground/README.md`. A below-quantification-limit outlet yields a range, not an exact removal or an exact treatment scale. This calculation assumes the same relevant liquid volume for both concentrations and does not distinguish degradation, adsorption, sampling losses or other causes of concentration decrease. The simple mass-input check is not a closed mass balance.

Report catalyst loss, regeneration inputs, washing between cycles, and the rule used after the last observed cycle. Treat extrapolated lifetime as a scenario.

## 7. Scale-up and comparative claims

Do not linearly scale laboratory nameplate electricity without discussing utilization and thermal efficiency. Build separate laboratory, optimized laboratory, pilot, and industrial scenarios when possible.

For comparisons with literature catalysts, harmonize at least:

- functional unit and pollutant service;
- PZC/PC/PPC mode and power boundary;
- background database and system model;
- LCIA method and version;
- catalyst lifetime and recovery;
- geographic electricity mix;
- included preparation and waste stages.

If harmonization is incomplete, label the comparison contextual rather than a definitive ranking.
