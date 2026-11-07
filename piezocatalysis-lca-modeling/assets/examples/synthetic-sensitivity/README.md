# Synthetic sensitivity example / 合成敏感性示例

All inputs and impact results are invented. This example tests arithmetic and reporting; it is not a measurement, a database result, or a real LCA. Run from the skill directory:

以下输入和影响结果均为虚构，仅用于测试计算和报告，不是实验值、数据库结果或真实 LCA。在技能目录中运行：

```sh
python scripts/sensitivity_report.py assets/examples/synthetic-sensitivity/scenarios.json --csv /tmp/piezo-sensitivity-results.csv > /tmp/piezo-sensitivity-report.json
```

Use a new CSV path: the program refuses to overwrite an existing file. `expected-report.json` and `expected-report.csv` are reproducible example outputs. The shell redirect can overwrite a file, so choose a new JSON output path as well.

请使用新的 CSV 路径，程序不会覆盖已有 CSV。`expected-report.json` 和 `expected-report.csv` 是示例输出；命令行重定向可能覆盖文件，因此 JSON 输出也应使用新路径。

Hand check: baseline climate values are A = 1 + 2 = 3 and B = 2 + 2 = 4. Doubling A's treatment power, assuming fixed runtime and unchanged treatment performance, gives A = 1 + 2 × 2 = 5, so the order changes from A/B to B/A. Doubling A's yield while holding its preparation inputs fixed gives 1 / 2 + 2 = 2.5. All values and units are synthetic.

手算核对：基准气候指标 A = 1 + 2 = 3，B = 2 + 2 = 4。若 A 的处理功率翻倍，同时假设运行时间和处理性能不变，则 A = 1 + 2 × 2 = 5，排序由 A/B 变为 B/A。若 A 的产率翻倍且制备批次投入不变，则 A = 1 / 2 + 2 = 2.5。所有数值和单位均为合成示例。

The examples also include runtime, effective reuse, solvent recovery, alternative electricity and proxy dataset scenarios. Linear and inverse operators are approximations that the analyst must justify; for recovery, electricity mix and proxies, the example supplies separately calculated replacement contributions. The script does not calculate those impacts. Baseline and alternative contributions must be complete, non-overlapping and reconcile with absolute totals. The exact matching of declared comparison metadata does not prove scientific comparability. For negative baselines, percentage change uses `abs(baseline)`; a zero baseline yields null percentage, not zero. Ranking treats exact equal values as ties.

示例还包含运行时间、有效复用次数、溶剂回收、电力来源和代理数据情景。线性／反比缩放的适用性必须由研究者论证；回收、电力来源和代理案例提供的是另行计算的替代贡献值，脚本本身不计算它们。基准和替代组成项须完整、不重叠，且与绝对总量核对一致。声明的元数据相同并不证明科研上可比。负基准的变化比例以 `abs(基准)` 为分母；基准为零时比例为 null，不填零。数值完全相等按并列处理。

Each `replace` adjustment must supply both `replacement_source` and `replacement_evidence_class` (`measured`, `reported`, `calculated`, `proxy`, or `scenario`) independently of the scenario's evidence class. For adjusted components, output preserves `baseline_source`, `baseline_evidence_class`, and `scenario_evidence_class`. Scaled contributions are classified as calculated under the declared scenario; this does not validate its assumptions. Existing replace inputs require the new field.

每个 `replace` 调整项必须分别提供 `replacement_source` 和 `replacement_evidence_class`（`measured`、`reported`、`calculated`、`proxy` 或 `scenario`），不能直接套用情景的证据类别。调整后的组成项保留基准来源、基准证据类别和情景证据类别；缩放结果标记为计算值，但不代表情景假设已被证实。旧版 replace 输入需要补充该字段。
