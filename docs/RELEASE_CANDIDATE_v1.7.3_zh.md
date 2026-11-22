# v1.7.3 维护候选说明

openLCA 2.7.0 读取产品系统时，JSON 序列化会扫描整个交换表，以找出系统引用的交换编号。同一个情景在计算前后各读一次快照，因此会重复扫描。隔离的 BiOCl 基准库有 42,952,270 条交换记录，而该产品系统只引用了 7 个交换 ID。Derby 执行计划确认旧查询走全表扫描，优化查询走索引。[openLCA 2.7.0 源码](https://github.com/GreenDelta/olca-modules/blob/v2.7.0/olca-core/src/main/java/org/openlca/jsonld/output/ProductSystemWriter.java#L105-L127)

本版在验证过的 macOS 2.7.0 临时 IPC 进程里，改用参数化的交换 ID 分批查询。原有 JSON 序列化和计算前后的两次读取照常执行。超过 4,096 个引用交换 ID 的系统、核心组件摘要不匹配的兼容构建，以及外部 `--port` 服务均沿用其原查询。优化运行在 APFS 临时数据库副本上。

| 同一批情景 | v1.7.2 端到端均值 | v1.7.3 候选均值 | 耗时缩短 |
| --- | ---: | ---: | ---: |
| 4 个合成逐循环情景 | 94.4 秒 | 40.8 秒 | 56.7% |
| 4 个 BiOCl 情景 | 90.1 秒 | 33.2 秒 | 63.1% |

Apple M5 Max 上以同一 openLCA 和数据库副本串行执行。每个版本各跑两轮，第二轮反转版本及案例顺序。计时包括克隆并启动 IPC、计算与核对、关闭服务和写出结果。每轮 8 个情景的 200 项 LCIA 结果按情景、类别 UUID 和单位逐项比较，数值完全一致。全部计算快照摘要也一致。

## 回退

在独立目录安装 v1.7.2，再将 Agent 指回旧版 Skill。保留已有研究输入和复算输出。[v1.7.2 仓库提交](https://github.com/William-Lebert/piezocatalysis-LCA-modeling-skill/commit/6d18d45e38bb9f08f5c6bceb6350130fee1b0faa)
