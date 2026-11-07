# Reporting and Figures

## Contents

1. Methods structure
2. Required tables
3. Figure set
4. Language and typography
5. Interpretation discipline

## 1. Methods structure

Write the LCA methods in this order:

1. goal and decision context;
2. functional unit;
3. system boundary and exclusions;
4. foreground data and evidence classes;
5. background database and mapping/proxy strategy;
6. allocation and catalyst-lifetime treatment;
7. LCIA methods and versions;
8. EE/O method and power definition;
9. sensitivity and uncertainty analysis;
10. software and reproducibility information.

## 2. Required tables

Provide:

- route-specific foreground inventory;
- parameter/evidence/uncertainty register;
- background dataset mapping and proxy table;
- absolute LCIA results;
- contribution or hotspot results;
- sensitivity scenarios;
- EE/O parameters and results when relevant.

The optional sensitivity report exports absolute values, baseline differences, percentages, per-category ranking groups and whether the ranking changes. Keep the included component-level inputs and scenario provenance with the results. `--csv` creates a new file only; text cells beginning with spreadsheet formula characters are prefixed with an apostrophe. A null percentage is not a zero change. Ranking uses exact numerical ties and lower numerical impact, so it does not by itself establish statistical significance or an overall environmental preference across categories.

## 3. Figure set

Recommended figures for a piezocatalysis paper:

- system-boundary schematic;
- absolute GWP/CED or selected midpoint comparison;
- independently normalized midpoint heatmap/bar chart;
- contribution analysis by preparation and treatment stage;
- EE/O comparison with explicit power boundary;
- sensitivity or uncertainty plot.

Avoid radar charts when axis scaling obscures magnitude. Avoid pie charts for many small contributions. Use a full black frame, readable tick marks, and a colorblind-safe palette when matching an Origin-style scientific presentation.

## 4. Language and typography

For bilingual deliverables, keep scientific symbols and units identical across versions. A practical default is Times New Roman for English text and numbers and SimSun for Chinese text, unless the journal template specifies otherwise.

Do not place panel letters on standalone figures when the user will assemble multi-panel layouts later. Keep editable data tables with every figure.

## 5. Interpretation discipline

- distinguish model result, sensitivity result, and mechanistic hypothesis;
- do not call a screening proxy model an absolute product footprint;
- state whether results apply to laboratory, pilot, or prospective industrial scale;
- discuss trade-offs rather than only the lowest GWP route;
- identify conditions under which the ranking could reverse;
- keep literature context separate from present-study measurements.
