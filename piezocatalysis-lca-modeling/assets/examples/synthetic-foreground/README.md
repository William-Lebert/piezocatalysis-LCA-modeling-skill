# 合成实验前景案例 / Synthetic experimental foregrounds

`case-a.json` 与 `case-b.json` 的所有数据和来源均为虚构情景，不是实验测量或 LCIA 结果。以 Skill 目录为当前目录运行：

```sh
python scripts/experimental_foreground.py assets/examples/synthetic-foreground/case-a.json \
  --inventory-csv /tmp/synthetic-a-inventory.csv > /tmp/synthetic-a-report.json
python scripts/experimental_foreground.py assets/examples/synthetic-foreground/case-b.json \
  --inventory-csv /tmp/synthetic-b-inventory.csv > /tmp/synthetic-b-report.json
python scripts/validate_inventory.py /tmp/synthetic-a-inventory.csv
python scripts/validate_inventory.py /tmp/synthetic-b-inventory.csv
```

导出文件须使用不存在的路径。CSV 是每个制备批次及每次处理的原始基准清单；JSON 同时提供两种功能单位的缩放结果。CSV 可交给现有 `audit_and_scale_inventory.py`，其映射表和处理参数需要按实际案例提供。

| 项目 | 案例 A | 案例 B |
| --- | ---: | ---: |
| 干催化剂产量／批 | 5 g | 10 g |
| 制备 1 kg 所需批数 | 200 | 100 |
| 每次处理表观去除量 | 10 mg | 15 mg |
| 处理功能单位 | 去除 100 mg | 去除 150 mg |
| 处理次数／功能单位 | 10 | 10 |
| 分摊制备批数／处理功能单位 | 1 | 0.1 |
| 超声电力／处理功能单位 | 1 kWh | 1 kWh |
| 废水／处理功能单位 | 10 L | 5 L |

两种案例还包含前驱体、制备电力、清洗水及清洗废水、废催化剂和边界外运输。A 的制备电力为每批 2 kWh；B 为每批 7.2 MJ，换算后同为 2 kWh。案例 B 用 500 mL、0.04 g/L 和 10,000 µg/L 验证体积及浓度换算。废物流只表示清单输出，后续仍需选择并连接适当的废物处理数据集。

模板在 `assets/templates/experimental_foreground.template.json`。填写每个数据的数值、单位、来源和证据类别；清洗水、设备电力等各自用不同 `activity_id`。同一总表计与其分项不能同时计入，可给互斥计量项指定相同 `overlap_group`，脚本会拒绝同时纳入；相同阶段和方向的重复名称会提示复核，但无法识别所有可能的重复。

未测值用 `null`，不可用零代替；含缺失值的 CSV 会保留空数值，须补全后才能通过现有清单校验。出水低于定量限时设置 `qualifier` 为 `below_loq`，低于检测限用 `below_lod`；`value` 设为 `null`，`limit` 为相应限值（单位同出水浓度）。报告给出表观去除量区间，不生成精确处理缩放结果。`missing` 表示未获得出水结果。浓度差按相同进出水体积计算，仅表示水相浓度下降，不证明矿化或污染物完全降解。

生产功能单位只含制备阶段；处理功能单位分配制备和处理投入，假设每次处理条件相同、催化剂负荷相同、有效使用次数已被合理估计。应分别记录试剂来源、设备电力边界、清洗及废物处理；复用性能变化、回收损失和再生投入需单独建模。
