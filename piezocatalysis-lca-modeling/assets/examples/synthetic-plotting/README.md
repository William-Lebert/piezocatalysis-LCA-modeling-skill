# 可信绘图与合成示例

`plot_data.py` 把现有报告转换为版本化 `piezolca.plot-data/1`；`plot_report.py` 使用 Matplotlib 输出可编辑 SVG、PNG、CSV 数据表、绘图 JSON 和哈希清单。无需 GUI，不会启动或写入 openLCA。独立绘图环境示例（不要在项目里提交虚拟环境）：

```sh
python3 -m venv /tmp/piezolca-plot-env
/tmp/piezolca-plot-env/bin/pip install -r piezocatalysis-lca-modeling/assets/examples/synthetic-plotting/requirements.txt
python3 piezocatalysis-lca-modeling/scripts/plot_data.py --kind cycles \
  --report piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/constant.json \
  --output /tmp/piezolca-plot-data.json --license-note 'Synthetic input only.'
/tmp/piezolca-plot-env/bin/python3 piezocatalysis-lca-modeling/scripts/plot_report.py \
  /tmp/piezolca-plot-data.json --output-dir /tmp/piezolca-figure --locale zh
```

两个输出路径必须是新的。中文需要系统中文字体，找不到时可传 `--font-path`；英文用 `--locale en`。SVG 保留文本，跨电脑编辑时应安装相同字体；PNG 的 DPI 可设置。CSV 和 JSON 是可编辑数据副本，修改后应重新生成图与清单；文件哈希用于追踪变更，并非数据真实性证明。

四种数据类型可运行 `python3 .../scripts/plot_data.py --help`：

- `cycles`：输入逐循环前景原始 JSON，分别显示每轮水相表观质量差和处理能耗。能耗按每轮／批次，不是每功能单位；检测限画区间，缺失明确标示。
- `stages`：输入 `result_coverage.py` 的单类别报告、对应每功能单位模型计划和人工审核的 `--binding` JSON。binding 为 `{system_uuid, root_uuid, stages: [过程UUID], activities: [...]}`；每活动需 `activity_id`、`process_uuid`、`provider_uuid`（未连接为 null）、`flow_uuid`、`unit`、`amount`、`is_input`。这些 UUID 和数量应来自实际建模及 IPC 回读，不可按名称猜测。程序验证每条前景交换、供应方、方向、根过程与每阶段一单位服务、参考流和所列背景过程贡献；该实现按各阶段引用量比例分配固定背景 `LCI_RESULT` 的贡献，遇到无法分配的非零贡献或未核对交换会停止。它不是 UPR 供应链分解，代理和未连接项继续显示。
- `scenarios`：输入 `cycle_scenario_compare.py` 结果及该报告引用的原始基准／情景 JSON（核对内容哈希），指定一个影响类别 UUID。不同功能单位或声明不一致时停止；部分模型可以展示结果但标明不能据此排名。请先独立核对情景模型交换与链接。
- `sensitivity`：输入 `sensitivity_report.py` 报告，选择一个路线及一个类别，显示每个声明的单因素情景对基准的正负变化，按绝对变化排序。每条只是一个指定设置，不能推断双侧上下限或概率分布。

图表的类别、单位、功能单位、数据库／方法声明、来源文件摘要、警告和许可证备注保留在绘图数据与清单；图注保留必要条件。用户声明不等于科学核实。商业数据库及其衍生结果的分享须按相关许可审查，`--license-note` 是提醒而非许可认证。
