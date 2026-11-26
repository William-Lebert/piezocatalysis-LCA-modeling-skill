# openLCA 复算基准与回归检查

基准入口用两份 Skill 中的 `scenario_suite.py rerun` 读取同一份归档，顺序执行各轮。计时包含命令启动、临时数据库副本、复算、保存前校验、服务退出及 JSON 写出。第二轮反转版本和案例顺序，以减小运行顺序的影响。需要可用的本地 openLCA 工作区与 [macOS 守护启动环境](../piezocatalysis-lca-modeling/references/openlca-workflow.md#optional-guarded-automatic-startup-on-macos)。

## 同批案例对照

从仓库根目录运行。将 `/path/to/` 下的路径换成本机已有 Skill、归档及工作区路径。每次运行指定一个新的输出目录，父目录须已存在。基线 Skill 可以用 `git archive <commit> piezocatalysis-lca-modeling` 提取。

```sh
python3 tests/benchmark_scenario_suite.py \
  --baseline-skill /path/to/baseline/piezocatalysis-lca-modeling \
  --suite synthetic /path/to/synthetic/suite.json \
  --suite biocl /path/to/biocl/suite.json \
  --workspace /path/to/openLCA-data-1.4 \
  --rounds 2 --output /path/to/new-benchmark-run
```

候选默认使用当前仓库的 Skill，可用 `--candidate-skill` 指向另一份。非默认应用路径用 `--openlca-app` 指定。每组案例可增加轮次，单次超时默认 180 秒，可用 `--timeout` 调整。

- `manifest.json` 记录输入归档、脚本和守护 JAR 的哈希与运行设置。
- 每次复算保留原始 JSON 及命令日志。命令失败或发现差异时，入口返回非零状态，便于按案例、版本和轮次定位。
- `summary.json` 在全部复算和比对通过后生成。报告各轮耗时、均值、变化率及 LCIA、贡献、清单流和快照核对数量。逐项比对忽略每轮生成的时间戳、临时结果 ID，以及包含这些字段的两个摘要。

含商业背景库数据的复算结果留在本机，按数据库许可处理。

## 描述符回退检查

```sh
python3 tests/integration_openlca_descriptor_fallback.py
```

入口复用守护集成测试的虚构数据库脚本，生成 33 个独立供应过程。用两个隔离副本分别执行原查询和优化路径，从 Derby 语句记录验证优化路径在 32 次按 ID 查找后执行一次全量描述符查询。对照 LCIA、贡献和总清单流，同时核对计算前后及两个副本间的产品系统、过程、方法、类别和参数快照。测试结束后校验源数据库文件哈希。
