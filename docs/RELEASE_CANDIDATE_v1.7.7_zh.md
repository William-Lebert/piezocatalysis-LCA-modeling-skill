# v1.7.7 维护候选

多情景复算会为每个产品系统构建技术流索引。openLCA 2.7.0 原来先加载过程、产品系统、结果和流的全部描述符，再按产品系统链接取用。BiOCl 复算的 JVM 采样在这四类全量读取上观察到 147 个计算栈样本。[openLCA 技术流索引源码](https://github.com/GreenDelta/olca-modules/blob/v2.7.0/olca-core/src/main/java/org/openlca/core/matrix/index/TechIndex.java#L122-L151)

候选在通过组件哈希校验的 macOS 临时守护进程中复用已有的按 ID 查找。每类描述符超过 32 次不同 ID 查找时走原全量读取。每个情景仍重新构建索引、计算 LCIA，并在计算前后核对模型和参数快照。采样中另一处主要开销是影响因子表扫描，其行处理和查询均沿用上游实现。[openLCA 影响因子构建源码](https://github.com/GreenDelta/olca-modules/blob/v2.7.0/olca-core/src/main/java/org/openlca/core/matrix/ImpactBuilder.java)

## 端到端复算

在同一台 Mac 上，对同一份合成归档和 BiOCl 归档分别用 v1.7.6 与候选执行 `scenario_suite.py rerun --workspace`。每个版本各两轮，第二轮反转版本和案例顺序。耗时包括启动、复算、保存前的校验、临时服务退出及 JSON 写出。

| 案例 | v1.7.6 均值 | v1.7.7 候选均值 | 耗时减少 |
| --- | ---: | ---: | ---: |
| 合成逐循环 4 个情景 | 23.07 秒 | 17.10 秒 | 25.9% |
| BiOCl 4 个情景 | 22.01 秒 | 16.42 秒 | 25.4% |

对照两轮输出，200 项 LCIA 数值及其类别、单位，1,416 条贡献，17,456 条总清单流，以及产品系统、供应方、方法、类别、参数快照全部逐项相等。各次运行生成的时间戳、结果 ID 和包含这些字段的两个摘要在独立结构对照中略去，各文件仍通过命令自身的摘要校验。

## 维护性

两处技术描述符读取共用一个有界查找实现。情景捕获把已计算的前景和快照摘要用于验证及输出。复算入口把原归档和新结果的整套校验从各两遍减为各一遍，原归档先验后算，结果校验通过才写出。

如需回退，可在独立目录取回 v1.7.6，保留已有输入和复算记录。[v1.7.6 仓库提交](https://github.com/William-Lebert/piezocatalysis-LCA-modeling-skill/commit/6fe7deeedf040a91089dfe60adcb37d596b53770)
