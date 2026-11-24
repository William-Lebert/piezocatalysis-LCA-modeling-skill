# v1.7.5 维护版说明

本次仓库更新包含 v1.7.4 的冷读和多情景复算改动。首次读取产品系统时，少量描述符按 ID 查询。多情景复算在同一只读临时副本里复用过程、地域、影响方法和影响类别，产品系统与参数仍在每次计算前后读取。[v1.7.4 候选验证](RELEASE_CANDIDATE_v1.7.4_zh.md)

以 v1.7.4 本地候选为计时基线，本次进一步优化已验证 macOS openLCA 2.7.0 临时 IPC 的贡献读取。openLCA 原先在每次返回影响类别贡献时重新创建描述符解析器。现在同一 IPC 工作线程在同一私有数据库副本上，每个解析器最多使用 32 次。解析器仅保留数据集引用和描述信息，计算值及响应由原接口逐次生成。[openLCA 结果编码源码](https://github.com/GreenDelta/olca-modules/blob/v2.7.0/olca-core/src/main/java/org/openlca/core/services/JsonResultService.java)

| 同批案例 | LCIA 贡献读取总耗时 | 端到端耗时 | 端到端缩短 |
| --- | ---: | ---: | ---: |
| 合成逐循环 4 个情景 | 2.21 → 0.36 秒 | 25.70 → 24.16 秒 | 6.0% |
| BiOCl 4 个情景 | 1.32 → 0.22 秒 | 25.02 → 22.77 秒 | 9.0% |

在同机执行两轮，第二轮反转版本和案例顺序。端到端计时包含临时服务启动、复算、校验、关闭和写出。200 项 LCIA、1,416 条贡献明细、17,456 条清单流和快照摘要全部一致。比较计算记录时忽略每次运行生成的时间戳与结果 ID。

## 回退

在单独目录取回 v1.7.3 仓库提交，再把 Agent 指回旧版 Skill。保留原始输入和复算记录。[v1.7.3 仓库提交](https://github.com/William-Lebert/piezocatalysis-LCA-modeling-skill/commit/70315468b1b63403a3abaf1caa2bccf9f5eeb679)
