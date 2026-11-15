# 候选数据集审查与清单交接

本例的活动 ID 来自 `synthetic-cycles/constant.json`，查询词仅演示格式，不是对任何真实数据集的推荐。Agent 使用本机合法取得的 openLCA 数据库时，先按实验事实准备查询，再让研究者审查技术、地域及代理适用性；不要把候选名称或地理接近视为选定依据。现有脚本只读数据库，不创建或编辑产品系统。

从仓库根目录运行，`YOUR_DATABASE` 应替换为用户确认的本机数据库，且创建新的输出路径：

```sh
python3 piezocatalysis-lca-modeling/scripts/cyclic_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/constant.json \
  --inventory-csv /tmp/piezo-mapping-inventory.csv > /tmp/piezo-mapping-cycle.json
python3 piezocatalysis-lca-modeling/scripts/mapping_review.py collect \
  --inventory /tmp/piezo-mapping-inventory.csv \
  --manifest /tmp/piezo-mapping-inventory.csv.manifest.json \
  --queries piezocatalysis-lca-modeling/assets/examples/synthetic-mapping-review/queries.json \
  --database YOUR_DATABASE --database-version 'YOUR_VERSION' --system-model 'YOUR_SYSTEM_MODEL' \
  --start-local --workspace "$HOME/openLCA-data-1.4" --output-dir /tmp/piezo-mapping-review
```

可使用 `--port PORT` 连接已启动的本地 IPC（不用 `--workspace`）。受控自动启动仅适用于现有守卫文档支持的环境和数据库副本。数据库名、版本和系统模型是用户声明，IPC 查询本身不能证明数据库身份。

每项 `queries` 使用一个 `activity_id`，提供 `name_contains` 和可选 `geography`，或明确给出最多 20 个 `process_uuids`；当同时给出 UUID 和名称／地域时，系统会核对声明。名称查询最多展开 20 个候选，并记录匹配总数和 `truncated`；没有结果、指定 UUID 不存在以及未查询的活动均保留。可缩小查询或按 UUID 分批再审查；不会根据名称或地域自动选定。

`review.json` 包含前景清单/manifest 哈希及每个候选的过程 UUID、版本、地域代码与名称、参考产品及流/流属性、单位、参考方向和查到的问题。openLCA 过程列表可能用地域代码（例如 CN），而位置实体使用名称（例如 China）；有位置实体代码时核对代码，缺少时记录未核实。候选不代表科学适用，也不代表产品系统已经连接。

在 `decisions.csv` 中逐行保留候选快照；按需填写 `decision=pending|selected|rejected`。选择或拒绝须填写真实审查者、ISO 日期和理由；选择还须填写 `match_type=exact|proxy|constructed`、偏差、地域和技术适用理由。对确需以质量代理体积的情况，选择 `conversion_type=density`，记录 `density_kg_per_l`、来源及证据类别；没有密度依据不能推断换算。其他情况使用 `conversion_type=unit`。候选快照中的名称、地域、参考产品和单位等不应手改，重新查询才能更新。

```sh
python3 piezocatalysis-lca-modeling/scripts/mapping_review.py finalize \
  --inventory /tmp/piezo-mapping-inventory.csv \
  --manifest /tmp/piezo-mapping-inventory.csv.manifest.json \
  --review /tmp/piezo-mapping-review/review.json \
  --decisions /tmp/piezo-mapping-review/decisions.csv \
  --output-dir /tmp/piezo-mapping-handoff
```

`review-record.json` 保存选用、拒绝及理由、来源哈希和生成脚本摘要；若采集与交接脚本版本不同会明确标示，`mapping.csv` 与 `assignments.csv` 可交给 `inventory_handoff.py`。每个活动最多选一个；无候选或未选择的活动保持未映射。若原清单已填写映射编号，导出时保留该编号；如果多个活动共用编号，或新编号与其他活动已有编号冲突，程序会停止并提示先人工整理，避免把新候选悄悄套用到其他活动。**即使选择了候选，导出映射的 `review_status` 仍是 `pending`**；审查者确认内容、参考方向、换算、工艺与地域适用性后再按既有映射流程显式审核，重新运行 `cycle_model_plan.py` 和产品系统链接检查。清单哈希可检测更改，不是审查签名或数据真实性证明。

完整候选名称、UUID、产品及结果可能受 ecoinvent 等数据库许可约束。报告默认保留本机，对外分享前检查许可证和输出内容。
