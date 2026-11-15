# Agent 科研交付整理

`research_delivery.py` 从**已有**逐循环科研记录整理本地交付：校验前景、每功能单位清单与 manifest，按提供情况核对证据、领域边界、映射审查、计算、图表和来源；生成方法说明、绝对 LCIA 表、输入快照、图表和逐文件 SHA-256 清单。它不启动 openLCA、不重新计算，也不创建数据或推断科学结论。Agent 应先按任务运行对应前景、证据、映射、计算和绘图工具，再按实际已有材料填写配置。缺少的材料列为缺口，不用零代替。

从仓库根目录运行以下**部分交付**示例，所有数据虚构，输出路径应不存在：

```sh
python3 piezocatalysis-lca-modeling/scripts/cyclic_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/foreground.json \
  --inventory-csv /tmp/piezo-delivery-inventory.csv > /tmp/piezo-delivery-cycle.json
python3 piezocatalysis-lca-modeling/scripts/research_delivery.py assemble \
  piezocatalysis-lca-modeling/assets/examples/synthetic-delivery/spec.json \
  --output-dir /tmp/piezo-research-delivery
python3 piezocatalysis-lca-modeling/scripts/research_delivery.py verify /tmp/piezo-research-delivery
python3 piezocatalysis-lca-modeling/scripts/research_delivery.py assemble \
  /tmp/piezo-research-delivery/replay-spec.json --output-dir /tmp/piezo-research-delivery-replayed
```

该例只提供前景和清单，因此会明确报告缺少证据审查、映射、计算及图表。`replay-spec.json` 用已复制的文件**重新整理交付**，不会重新运行 openLCA；使用相同版本脚本可复查整理过程。`verify` 检查清单列出的文件是否存在且哈希一致，不是签名、真实性或科学有效性的证明。

## 完整交付配置

配置 `schema_version`、`title`、`license_note` 与 `artifacts`。最少提供 `foreground`、`inventory`、`inventory_manifest`；路径相对配置文件解析。增加已有文件时：

- `evidence_spec`、`evidence_report` 必须成对；`evidence_sources` 将来源 ID 显式映射到要复制的本地标准化 CSV。全部标准化 CSV 已提供且没有额外原件时会重跑证据核对；遗漏的来源标为缺口。Excel/PDF 原件及数据库不会自动复制。
- `domain_protocol`、`domain_input`、`domain_report` 与证据报告一起提供，检查输入哈希并重跑所指定循环的领域边界检查。
- `mapping` 和 `assignments` 成对；`model_plan` 中的清单和映射摘要必须一致。`candidate_review`、`candidate_decisions`、`candidate_record` 必须同时提供，重放候选审查并检查所选过程与模型计划一致。候选选择本身仍待独立审核。
- `calculation` 和 `coverage` 成对；coverage 必须包含同一计算，计算量为一个声明的功能单位。没有完整绑定时，报告不会声称计算系统交换已与清单独立核对。
- 要纳入阶段图，提供 `binding`、`plot_data`、`plot_dir`、`model_plan`、`calculation` 和 `coverage`。阶段数据由现有分配函数重新计算，校验来源哈希、绑定及图表清单，再复制 CSV、SVG、PNG。逐循环图可额外提供 `cycle_plot_data` 和 `cycle_plot_dir`，会从前景重算数据并校验来源及文件。情景图和敏感性图目前需由 Agent 单独交付并说明来源。

输出 `methods.md` 是从提供的结构化记录生成的**待审方法草稿**；`lcia-results.csv` 保留每个类别的绝对量和单位；`delivery-manifest.json` 保存文件、来源、代码摘要和未解决问题。用户声明的数据库、功能单位、地理及计量条件仍需研究者审核；不从匹配的文本或哈希推断矿化、概率分布或方案排名。

完整输出可能包含实验记录、绝对结果和 ecoinvent 等数据库衍生信息。默认仅保存在用户指定的本机目录，不上传或自动分享；外发前逐项检查隐私及许可证。`source-spec.json` 可能包含原本机路径，应注意清理或审查。程序不会自动复制或发布商业数据库。
