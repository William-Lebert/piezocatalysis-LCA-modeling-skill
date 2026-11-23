# v1.7.4 维护候选说明

openLCA 2.7.0 首次导出产品系统时，会为解析过程引用加载整类描述符。BiOCl 冷启动采样显示，一个约 7.65 KB 的响应在发送响应头前耗时 5.84 秒。JVM 栈多次落在构造全量过程描述符映射的 SQL 查询上。[openLCA 描述符解析源码](https://github.com/GreenDelta/olca-modules/blob/v2.7.0/olca-core/src/main/java/org/openlca/jsonld/output/JsonRefs.java)

在已验证的 macOS openLCA 2.7.0 临时 IPC 中，少量描述符使用原 DAO 按 ID 查询。同一次导出中某一类型超过 32 个不同 ID 时，改用原全量映射。用 `scenario_suite.py --workspace` 启动的套件在该次私有只读副本中复用过程、地域、影响方法及所选影响类别。产品系统与参数每个情景仍在计算前后各取一次。外部 `--port` 继续逐次读取全部快照输入。

| 同一批案例 | 首次产品系统读取 v1.7.3 → v1.7.4 | 端到端 v1.7.3 → v1.7.4 | 端到端缩短 |
| --- | ---: | ---: | ---: |
| 合成逐循环 4 个情景 | 5.75 → 1.09 秒 | 37.80 → 26.84 秒 | 29.0% |
| BiOCl 4 个情景 | 5.80 → 1.07 秒 | 33.72 → 23.48 秒 | 30.4% |

同一台机器串行测两轮，第二轮反转版本和案例顺序。端到端包括启动临时服务、复算、校验、关闭和结果写出。合成套件完整过程读取从 66 次降到 21 次，BiOCl 从 40 次降到 15 次。两个套件的完整影响方法读取均从 8 次降到 1 次。200 项 LCIA 按情景、类别 UUID 和单位逐项比对，数值完全相等。快照、供应方、方法、影响类别和参数摘要全部一致。

## 回退

在单独目录安装 v1.7.3，再把 Agent 指回旧版 Skill。保留原研究输入和新复算记录。[v1.7.3 仓库提交](https://github.com/William-Lebert/piezocatalysis-LCA-modeling-skill/commit/70315468b1b63403a3abaf1caa2bccf9f5eeb679)
