# Piezocatalysis LCA research review checklist

Before using a result for a scientific comparison, retain source records and review:

1. **Service:** pollutant identity, treated volume and performance requirement; apparent water-phase removal versus mineralization; or H2O2 product basis, product quality and measurement; or dry catalyst output. Different functions are not automatically equivalent.
2. **Experiment:** reaction mode and reactor, boundary and duration; influent and effluent volumes/concentrations, sampling plan and sampling losses, detection or quantification limits, repetitions and calibration. Treat missing and censored values explicitly.
3. **Inventory:** fresh and recovered catalyst, unexplained loss, end-of-life handling, oxidant and pH inputs, water and wastewater, auxiliary mixing/heating/pumping, and equipment or infrastructure exclusions with reasons. Record whether energy is measured at the wall, at a device, or estimated from rated power; avoid double counting overlapping measurements.
4. **Background and method:** database, version, system model, geography, process reference flow and units, technology fit, proxies and their rationale, allocation or system expansion for co-products, selected LCIA method and relevant category coverage. Keep licenses and local-only materials in mind.
5. **Results:** functional-unit scaling and provenance, unlinked or omitted exchanges, signed contributions, scenario comparability and uncertainty coverage. A zero impact or absent characterization factor does not prove complete coverage.

The domain declaration tool checks presence and a few consistency rules; it cannot establish that a source, proxy, measurement or boundary is scientifically appropriate. Researcher review remains necessary.

For cycle-level numeric evidence and piezocatalytic ultrasound, oxidant and catalyst boundary declarations, use the agent-callable checks in `assets/examples/synthetic-evidence/README.md`. The CSV link verifies normalized records; original spreadsheet or publication locations remain user-declared until independently checked.
