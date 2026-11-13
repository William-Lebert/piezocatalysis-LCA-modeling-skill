# Synthetic process mapping / 合成数据集映射

All flows, processes, IDs and locations in this folder are invented. From the skill directory:

```sh
python scripts/dataset_candidates.py \
  --inventory assets/examples/synthetic-mapping/inventory.csv \
  --mapping assets/examples/synthetic-mapping/mapping.csv \
  --descriptors assets/examples/synthetic-mapping/processes.json \
  --database 'Synthetic DB' --database-version 1.0 --system-model synthetic \
  --format csv
```

Electricity has two candidates (`ambiguous`); water has one (`needs_review`); the reagent has an unavailable explicit process UUID (`not_found`) even though a name match exists; wastewater has no match (`not_found`). No candidate is automatically selected. These are examples of candidate discovery, not LCIA results.

电力有两个候选，水有一个待审核候选；试剂指定的过程 UUID 不存在，废水没有候选。不会自动选定数据集，也不会把缺失项视为零。
