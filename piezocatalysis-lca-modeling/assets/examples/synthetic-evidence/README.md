# 合成实验数据证据链与压电催化边界

这些文件完全虚构，原始 CSV 是为软件联调构造的，不代表独立实验记录。Agent 可逐项建立 `evidence.json`：给前景 JSON 和每份本地 CSV 记录 SHA-256；`links` 将目标 JSON Pointer 关联到来源 ID、**从 1 开始的数据记录序号**和声明的样品／循环基准。源 CSV 使用 `value,unit,qualifier,limit,evidence_class,basis` 列；首行为表头，记录序号不是实际文件行号。`evidence_class` 必须与目标一致（`measured`、`reported`、`calculated`、`proxy`、`scenario`），程序不会把情景改为实测。每条报告保留源文件哈希、记录号、列名、原始单元格文本、单位换算、目标指针和缺失状态。

支持质量、体积、浓度、功率、时间和能量的同量纲换算。`below_lod`/`below_loq` 要求 `value` 为空、`limit` 为正；`missing` 的数值及限值均为空。缺失与删失不会补零。所有前景数值都列出链接覆盖率；未链接或重复使用同一来源记录会提示审查。程序重建逐循环前景，并在提供 inventory/manifest 时同时核对前景、服务、边界、每功能单位清单活动、单位、方向和数值；报告为每项清单列出直接输入及功能单位分配所依赖的指针。功率和时间引出的电量、催化剂准备分配等按现有前景模型计算，不能再次缩放。

可选 `originals` 数组记录原始 Excel、PDF 或其他文件的 `id`、`path`、`sha256`；CSV 可选列 `original_id,original_locator` 填写引用文件和如 `Sheet1!B2` 或 `p.3, Table 2` 的位置。程序只校验原始文件哈希并保留**用户声明的位置**，不会读取该页或单元格进行核对；会标记 `original_locator_requires_review`。需要 Agent 或研究者对原件逐项检查，不能把手工转换 CSV 当成已自动验证的原始单元格。直接 CSV 来源可不填这两列。

从仓库根目录运行，使用新的本地输出路径：

```sh
python3 piezocatalysis-lca-modeling/scripts/cyclic_foreground.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/foreground.json \
  --inventory-csv /tmp/piezo-evidence-inventory.csv > /tmp/piezo-cycles.json
python3 piezocatalysis-lca-modeling/scripts/evidence_chain.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/evidence.json \
  --foreground piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/foreground.json \
  --inventory /tmp/piezo-evidence-inventory.csv \
  --manifest /tmp/piezo-evidence-inventory.csv.manifest.json > /tmp/piezo-evidence.json
python3 piezocatalysis-lca-modeling/scripts/piezocatalysis_checks.py \
  piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/protocol.json \
  --foreground piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/foreground.json \
  --evidence /tmp/piezo-evidence.json \
  --domain piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/domain.json > /tmp/piezo-boundary.json
```

`protocol.json` 将超声功率时间估算或设备／墙插实测、辅助设备计量、氧化剂及 pH 调节投入、光照、催化剂去向、副产物与矿化声明与前景活动关联；检查每个循环是否声明超声活动，提示可能重复计量及无清单投入。以 `domain_sample_cycle_id` 指定一个循环，检查该循环进出水体积、浓度、删失和来源记录的样品基准是否与领域声明一致，同时核对服务类型、功能单位、污染物、性能声明及前景边界。文本一致只表示声明一致，不自动证明科学等价。当前只比对指定循环的四个字段，不推断所有循环、试剂或装置是否齐全。示例的辅助能耗、氧化剂与最终催化剂处置仍有缺口。

引用报告是某一时点快照；修改任何源文件后应重跑整个证据链和领域检查。文件哈希和数值相符不证明测量真实性、采样设计、污染物身份、矿化、数据库映射或研究可比性；人工审查仍必需。现阶段不读取任意 Excel/PDF 表格，不执行 OCR，不自动核验用户声明的原文件位置。完整结果和数据按用户隐私及背景数据库许可保管。
