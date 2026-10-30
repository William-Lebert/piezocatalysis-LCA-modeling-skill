# User Manual / 使用手册

## 1. Purpose / 用途

Use this Skill to design, build, audit, troubleshoot, and report LCAs for piezocatalytic materials and pollutant-treatment systems. It is intentionally limited to PZC, PC, and PPC research rather than general industrial LCA.

本 Skill 用于设计、构建、审查、排错和报告压电催化材料及污染物处理体系的 LCA。它有意限定在 PZC、PC 和 PPC 研究，不作为通用工业 LCA 百科。

## 2. Installation / 安装

Copy the folder `piezocatalysis-lca-modeling` into the local Codex skills directory, typically:

将 `piezocatalysis-lca-modeling` 文件夹复制到 Codex 本地技能目录，通常为：

```text
%USERPROFILE%\.codex\skills\piezocatalysis-lca-modeling
```

Restart or refresh Codex, then invoke it explicitly with `$piezocatalysis-lca-modeling`.

重启或刷新 Codex，然后使用 `$piezocatalysis-lca-modeling` 显式调用。

## 3. Recommended input package / 推荐输入资料

Prepare the following before modeling:

建模前建议准备：

- synthesis recipes, actual dry yields, washing and separation details;
- equipment active power and duration;
- catalyst dose, pollutant concentration, volume, and treatment time;
- PZC/PC/PPC kinetic constants and reuse data;
- intended deployment energy source and illumination scenario;
- licensed background database and LCIA methods;
- literature tables used for any external comparison.

- 合成配方、实际干燥产量、洗涤和分离细节；
- 设备实际功率与运行时间；
- 催化剂投加量、污染物浓度、体积和处理时间；
- PZC/PC/PPC 动力学常数与循环数据；
- 预期应用的能源来源与光照情景；
- 合法授权的背景数据库与 LCIA 方法；
- 用于外部比较的文献表格。

## 4. First prompt / 首次调用示例

```text
Use $piezocatalysis-lca-modeling to audit my PPC catalyst experiment, select a defensible functional unit, create the foreground LCI and proxy register, and prepare implementation plans for both openLCA and SimaPro. Do not calculate until the functional unit and illumination boundary are explicit.
```

```text
使用 $piezocatalysis-lca-modeling 审查我的 PPC 催化实验，选择可辩护的功能单位，建立前景清单和代理数据登记表，并分别制定 openLCA 与 SimaPro 实施方案。在功能单位和光照边界明确前不要计算。
```

## 5. Core workflow / 核心流程

### Step 1: Scope / 步骤 1：范围

Choose whether the question is catalyst preparation, pollutant-treatment service, treated-water quality, or EE/O. Do not mix these functional units.

明确研究问题属于催化剂制备、污染物去除服务、达标出水，还是 EE/O。不得混用不同功能单位。

### Step 2: Evidence / 步骤 2：证据

Classify each value as measured, reported, calculated, proxy, or scenario. Put missing and uncertain values in the assumptions log.

将每个数值标记为实测、文献报告、计算、代理或情景值。缺失和不确定参数写入假设登记表。

### Step 3: Foreground inventory / 步骤 3：前景清单

Build separate synthesis-batch and treatment-run inventories. Include route-specific yield, washing, centrifugation, drying, recovery, and waste management.

分别建立合成批次清单与处理运行清单，纳入路线特异的产率、洗涤、离心、干燥、回收与废弃处理。

### Step 4: Background mapping / 步骤 4：背景映射

Map exact datasets first. When a proxy is necessary, record its rationale, expected bias, and an alternative sensitivity dataset.

优先匹配精确数据集。必须使用代理时，记录代理理由、预期偏差和敏感性替代数据集。

### Step 5: Software implementation / 步骤 5：软件实施

- openLCA: open the correct database, start IPC if automation is needed, back up entities, calculate, and export absolute results.
- SimaPro: default to validated Direct Import or Excel external links; use COM only after entitlement and API verification.

- openLCA：打开正确数据库；自动化时启动 IPC；备份实体；计算并导出绝对结果。
- SimaPro：默认采用经过校验的 Direct Import 或 Excel 外部链接；仅在授权和 API 验证后使用 COM。

### Step 6: QA and reporting / 步骤 6：质控与报告

Reconcile totals, verify one hand calculation, retain absolute LCIA, run sensitivity cases, and write limitations before preparing normalized figures.

核对总量，验证至少一个手算锚点，保留绝对 LCIA，完成敏感性分析并写明局限性后，再绘制归一化图。

## 6. openLCA quick start / openLCA 快速开始

1. Open the licensed database and verify the LCIA methods.
2. Start the IPC server only when scripted work is required.
3. Use a software-neutral model specification and stable UUID manifest.
4. Export process backups before changes.
5. Calculate absolute impacts and contribution results.
6. Re-read modified processes and archive the manifest.

1. 打开授权数据库并确认 LCIA 方法。
2. 仅在需要脚本自动化时启动 IPC。
3. 使用软件中立模型规格与稳定 UUID 清单。
4. 修改前导出过程备份。
5. 计算绝对影响与贡献结果。
6. 回读修改后的过程并归档 manifest。

## 7. SimaPro quick start / SimaPro 快速开始

1. Confirm version, project, database, and user permissions.
2. Treat COM authorization as separate from installation edition.
3. Prefer a small Direct Import or one-cell Excel-link test.
4. If `.xlsx` raises a sheet-index error, test a simple `.xls` compatibility workbook.
5. Inspect units and directions after import.
6. Export absolute results and compare one anchor with an independent calculation.

1. 确认版本、项目、数据库与用户权限。
2. 将 COM 授权与安装版本分开判断。
3. 优先进行小规模 Direct Import 或单元格外链测试。
4. 若 `.xlsx` 出现工作表索引错误，测试结构简单的 `.xls` 兼容工作簿。
5. 导入后检查单位与输入输出方向。
6. 导出绝对结果，并与独立计算的锚点核对。

## 8. Included tools / 内置工具

```powershell
python scripts/validate_model_spec.py assets/templates/model_spec.template.json
python scripts/validate_inventory.py assets/templates/inventory.template.csv
python scripts/piezocatalysis_calculations.py eeo --power-kw 0.1 --volume-l 0.1 --kobs-min-1 0.01
```

The templates contain illustrative placeholders. Replace them before scientific use.

模板包含示例占位值，科研使用前必须替换。

## 9. Definition of done / 完成标准

A model is complete only when the functional unit, boundary, evidence classes, providers, software versions, absolute results, sensitivity cases, exclusions, and reproducibility files are all present.

只有在功能单位、系统边界、证据等级、背景提供者、软件版本、绝对结果、敏感性情景、排除项和复现文件全部齐全时，模型才算完成。

## 10. Public release / 公开发布

Do not publish commercial databases, private experimental records, license keys, connector binaries, or copyrighted papers. Publish templates, original scripts, methodological instructions, and synthetic examples only.

不得发布商业数据库、私人实验记录、许可证密钥、连接器二进制文件或受版权保护的论文。仅发布模板、原创脚本、方法说明和合成示例。
