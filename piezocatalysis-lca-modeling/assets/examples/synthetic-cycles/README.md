# 逐循环合成案例 / Synthetic cycle campaigns

三个文件均为虚构输入，与真实实验无关。`constant.json` 对应原有 `synthetic-foreground/case-a.json` 的两次恒定性能循环；`variable-exact.json` 和 `variable-censored.json` 描述同一组三次变化循环，只将最后一次精确出水 3 mg/L 改为低于定量限 3 mg/L。以仓库根目录运行：

```sh
python3 piezocatalysis-lca-modeling/scripts/cyclic_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/constant.json \
  --inventory-csv /tmp/cyclic-constant.csv
python3 piezocatalysis-lca-modeling/scripts/cyclic_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/variable-exact.json \
  --inventory-csv /tmp/cyclic-variable.csv
python3 piezocatalysis-lca-modeling/scripts/cyclic_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/variable-censored.json
```

导出路径和同名 `.manifest.json` 必须不存在。CSV 每行标注**每个处理功能单位**基准，配套元数据记录功能单位、缩放方式和哈希；新旧文件的映射交接方式见 `assets/examples/synthetic-handoff/README.md`。本开发版的批次／单次缩放入口会拒绝带有该标记的清单；v1.3.0 及以前的已安装缩放器不具备此检查。检测限、缺失值或净去除不为正时，不生成精确缩放；CSV 如包含空金额不会通过现有清单校验。

恒定案例每轮表观去除 10 mg，两轮共 20 mg，初装 1 g、不补加、干产率每批 5 g。目标 100 mg 需 5 组、总计 1 批制备、2 kWh 制备电和 1 kWh 超声电，与旧模型在相同边界及均匀复用条件下相同。这里整组结束时回收的催化剂均送处置，明确分配完整初装量；不是每次处理后都处置。

变化案例三轮去除为 10、8、9 mg，共 27 mg；补加 0、0.1、0.2 g，加初装 1 g 共 1.3 g；终回收 0.5 g，未解释的回收差合计 0.8 g。目标 54 mg 对应两组、0.52 制备批，处置最终回收物 1 g，再生试剂 0.1 g、再生电力 0.1 kWh。第二轮入水 1 L、20 mg/L、出水 2 L、6 mg/L，按进出水质量差 20−12=8 mg 计算；不能默认体积相同。低于定量限版本第三轮为 9—12 mg，整组为 27—30 mg，没有精确缩放。

用 `catalyst_mass_basis` 声明全部初装、补加、装载和回收数据采用同一 `dry`、`wet` 或 `unknown` 基准；只有 `dry` 可直接与干产率计算制备批次。湿基或未知基准需要先获得依据并转换，程序不会把它们当成干质量。允许明确的水量变化但不能据此认定污染物矿化。未解释的催化剂损失只作为待查质量差，不自动生成废物流。最终回收去向为 `disposed` 时单独输出回收物处置清单；`retained` 不输出处置、也不自动给予回收抵扣；`unknown` 给出待核提示。整组分配初装及所有补加量，并允许按功能单位比例重复整组，是清晰的分摊假设。过程、清洗和处置活动来源及代理映射需另行审核。

`activity_id` 跨制备和各循环必须唯一；同一个 `overlap_group` 只能有一个纳入项。初装、补加和最终回收物必须使用专门字段，已标为 `is_catalyst` 的普通活动会被拒绝；同一循环的重复流名会警告，但程序无法识别所有不同名称或未标注的重复测量。填报者应避免同时录入总表电量和分项、催化剂补加及其重复清单。每项测量记录单位、来源和证据类别；未知值填写 `null`，不能填零替代。模板在 `assets/templates/cyclic_foreground.template.json`。

The inventory `evidence_class` describes the underlying activity input, not an assertion that the per-functional-unit amount was measured directly. The exported amount is calculated using the functional-unit allocation and can depend on other recorded inputs. / 清单中的 `evidence_class` 描述原活动输入的证据类别，并不表示每功能单位数量为直接实测；导出数量经过功能单位分配计算，还依赖其他记录的输入。

### Recording the final catalyst destination

Set `final_recovered_destination` to `disposed`, `retained` or `unknown`. For a known route, add a `final_recovered_fate` object with `route`, `source` and `evidence_class`, for example:

```json
{
  "final_recovered_destination": "disposed",
  "final_recovered_fate": {
    "route": "Fictional incineration of collected dry catalyst residue",
    "source": "Synthetic terminal fate worksheet, row 1",
    "evidence_class": "scenario"
  }
}
```

Use a dry catalyst mass to map disposal and regenerate the paired inventory and manifest. In the `constant` case, 1 g is recovered per campaign and five campaigns provide the functional unit. The disposal line is 5 g per functional unit, equivalent to 0.005 kg in a kg-based dataset. Assign `final-recovered-catalyst` to a reviewed waste treatment mapping through the existing assignments CSV. Check the actual openLCA reference waste, input direction, mass unit, geography and route. Record every proxy's rationale and potential bias. A wet or unknown mass basis leaves this dry-basis amount unavailable. Retention makes no disposal demand or credit, and unaccounted cycle losses remain separate from the recovered mass.
