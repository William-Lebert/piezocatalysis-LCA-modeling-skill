# 逐循环清单与映射交接 / Synthetic inventory handoff

本例数据、映射名称和 UUID 全部虚构，只验证结构、单位和审核流程；不代表真实 ecoinvent 数据集。以仓库根目录运行（输出路径应不存在）：

```sh
python3 piezocatalysis-lca-modeling/scripts/cyclic_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/constant.json \
  --inventory-csv /tmp/piezolca-constant-inventory.csv > /tmp/piezolca-constant-cycle.json
python3 piezocatalysis-lca-modeling/scripts/inventory_handoff.py \
  --inventory /tmp/piezolca-constant-inventory.csv \
  --mapping piezocatalysis-lca-modeling/assets/examples/synthetic-handoff/mapping.csv \
  --assignments piezocatalysis-lca-modeling/assets/examples/synthetic-handoff/assignments-constant.csv \
  > /tmp/piezolca-constant-handoff.json
```

逐循环导出会创建 CSV 和同目录的 `CSV文件名.manifest.json`，CSV 每行标注 `piezolca.inventory/2` 和 `per_functional_unit`。元数据记录功能单位、边界、缩放规则、输入及程序文件 SHA-256、清单 SHA-256、循环损失和警告。两文件需一起保存；交接工具先核对清单哈希，再生成分类和待办。哈希用于检查内容是否一致，并非签名或数据真实性证明。

`assignments-constant.csv` 按 `activity_id` 连接现有映射表；对应三循环案例使用 `assignments-variable.csv`。这样可以更新审核表而不修改原始清单。未分配的输入标为 `unmapped`，未分配的输出标为 `awaiting_disposal_mapping`；排除项为 `excluded`，保留原因。分配到映射表后分别显示 `exact`、`proxy`、`constructed`；待审核、未知 UUID、参考方向、单位换算等问题独立列出。映射表可填 `reference_is_input`（供应方参考交换为输入时 `true`，输出时 `false`）；与前景交换方向不对应会提示。识别出来的换算量是**待审核候选**，不是经工具认证的连接。

`review_status=reviewed`、数据库名称、参考交换和地理等是填报者声明；脚本不访问数据库，也不证明科学适用性。真实连接仍需结合 `mapping_coverage.py` 和 openLCA 审核，参考流的单位／属性、废物与替代过程尤其如此。同量纲单位使用内置换算。体积到质量仅在映射表明确填写 `conversion_type=density`、`density_kg_per_l`、`density_source` 和 `density_evidence_class` 时按所声明密度计算；工具不推断密度或证明其适用。低于定量限或缺失导致不能精确缩放时，清单金额与候选数据集金额保留空值，报告提示待办。

新清单的基准标记会使本开发版 `audit_and_scale_inventory.py` 拒绝将其再次按每批／每次缩放；v1.3.0 及以前的已安装版本不认识该标记。v1.3.0 或更早创建、未标记的 CSV 无法可靠地自动判断基准；旧文件仍按旧接口读取，需从原始循环记录重新生成带标记清单，或由研究者自行核对，不能假定所有无标记文件都是未缩放数据。删除或改写标记无法被无清单哈希的旧缩放器识别，故应保留原始配对文件并走交接工具。

## 连接 openLCA 的只读预检

完成清单交接后，可用 `scripts/cycle_model_plan.py` 核对声明的数据集过程 UUID、地理、参考流、流属性、单位和参考方向，生成每个活动的待审核模型计划：

```sh
python3 piezocatalysis-lca-modeling/scripts/cycle_model_plan.py \
  --inventory /tmp/piezolca-constant-inventory.csv \
  --mapping /path/to/reviewed-mapping.csv --assignments /path/to/assignments.csv \
  --start-local --workspace "$HOME/openLCA-data-1.4" --database YOUR_DATABASE \
  > /tmp/piezolca-cycle-model-plan.json
```

此命令只读，不会创建产品系统。`--database` 是填报的数据库名称，预检核对其与映射表一致；数据库版本和代理的适用性仍须人工判断。`partial` 表示存在缺口或模型警告，未映射项不能解释为零影响。输出数值基于已缩放清单，建模时直接使用 `dataset_amount_per_functional_unit`，不要再次按循环数或功能单位缩放。若服务已由用户启动，也可用 `--port` 代替 `--start-local --workspace`。本目录虚构 UUID 仅用于离线交接，不能用于匹配真实 ecoinvent。
