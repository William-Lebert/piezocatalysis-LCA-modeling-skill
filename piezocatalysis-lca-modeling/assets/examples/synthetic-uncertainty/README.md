# 不确定性准备检查与合成联合抽样

```sh
python3 piezocatalysis-lca-modeling/scripts/uncertainty_readiness.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-uncertainty/readiness-demo.json
python3 piezocatalysis-lca-modeling/scripts/synthetic_joint_uncertainty.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-uncertainty/joint-demo.json
```

第一个命令整理参数单位、证据、来源、地域、时间、重复数、检测限、分布及变量关系声明；缺项返回退出码 2。模板在 `assets/templates/uncertainty_readiness.template.json`。`background_uncertainty_reviewed` 表示已检查，`background_uncertainty_represented` 表示所定义的分析范围内背景不确定性已被模型表示，不能互相代替。边界或方法未检查应保留为 false。固定参数要有依据，报告会标识其未参与不确定性传播。检查通过只代表声明字段齐全供方法复核，程序不评判分布参数是否有效、不自动识别所有相关变量，也不证明数据充分。

第二个命令仅接受 `purpose: synthetic_validation_only`，以明确列出的有限联合状态做演示，整组抽取参数及其预先给定响应。示例的两个虚构状态是 `(power, duration) = (1, 2)` 与 `(2, 1)`，各占 0.5；响应 `power * duration + power` 分别为 3 和 4，因此总体解析均值 3.5、总体标准差 0.5。种子 37、10,000 次抽样，结果记录样本均值、样本标准差、状态次数、分位数、前半段均值、输入哈希和 Python 版本。前半段与全部结果相近只是诊断，不是收敛证明。分位数是所假定模型输出分布的分位数，不是实验置信区间。

这不是 openLCA 原生蒙特卡洛功能，也不是给真实实验推断概率的通用抽样器。参数、概率和响应都是合成演示；应先以实测重复、校准、文献和相关性证据为依据，分别处理情景、测量误差、背景、模型结构及方法不确定性。若变量有共同来源或质量平衡约束，应显式定义联合分布，不能为了简便默认独立。当前本项目只读 guard 未开放 `result/simulate` 和 `result/simulate/next`；[openLCA 官方 IPC 说明](https://greendelta.github.io/openLCA-ApiDoc/results/simulate.html)介绍原生模拟的调用机制，但本示例没有调用该接口或证明原生模拟的随机种子可控性。
