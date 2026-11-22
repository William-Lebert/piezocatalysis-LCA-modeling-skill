# Piezocatalysis LCA Modeling Skill / 压电催化 LCA 建模技能包

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23813629.svg)](https://doi.org/10.5281/zenodo.23813629)

Version 1.7.3.

版本 1.7.3。

本版更新与回滚方法见 [v1.7.3 维护版说明](docs/RELEASE_v1.7.3_zh.md)。

This repository provides a research Skill for agents performing life-cycle assessment of piezocatalysis, photocatalysis, and piezo-photocatalysis systems. Its scripts, templates, and references support software-neutral modeling and openLCA or SimaPro workflows.

本项目是供科研 Agent 使用的 Skill 包，面向压电催化、光催化和压电光催化体系的生命周期评价。Agent 可按任务调用建模脚本、模板和参考文档，并结合 openLCA 或 SimaPro 工作。

The optional openLCA adapter can discover an existing local service. On the verified macOS openLCA 2.7.0 distribution it can also start a guarded temporary local server using a clone of an existing database; see the [openLCA workflow](piezocatalysis-lca-modeling/references/openlca-workflow.md) for setup and limitations.

可选的 openLCA 适配器支持发现已有本机服务；在已验证的 macOS openLCA 2.7.0 发行版上，也可基于已有数据库的临时副本启动受限本机服务。具体条件和限制见 [openLCA 工作流](piezocatalysis-lca-modeling/references/openlca-workflow.md)。

The release adds read-only process candidate discovery for inventory mapping; try the [synthetic example](piezocatalysis-lca-modeling/assets/examples/synthetic-mapping/README.md).

本版新增清单到 openLCA 过程的只读候选查询，使用方式见[合成映射案例](piezocatalysis-lca-modeling/assets/examples/synthetic-mapping/README.md)。候选需人工确认后填入映射表。

An isolated synthetic foreground has also been checked with a locally licensed ecoinvent background by comparing openLCA GUI and IPC results. The foreground data are illustrative; the database and test copy are not included in this repository.

另已在隔离副本中用合成前景和本机 ecoinvent 背景对照验证 openLCA 界面与 IPC 结果；案例输入为虚构数据，数据库及测试副本不包含在仓库中。

The release also converts documented experimental records into a foreground inventory and scales separate catalyst-production and pollutant-removal functional units. See the [two synthetic foreground cases](piezocatalysis-lca-modeling/assets/examples/synthetic-foreground/README.md).

本版还支持从有来源的实验记录生成前景清单，分别按催化剂产量和污染物去除量缩放；使用方法见[两组合成前景案例](piezocatalysis-lca-modeling/assets/examples/synthetic-foreground/README.md)。

One-at-a-time parameter scenarios can now be recalculated in openLCA with a reproducibility record; see the [synthetic parameter example](piezocatalysis-lca-modeling/assets/examples/synthetic-parametric/README.md).

现可在 openLCA 中逐一重算参数情景并生成复现记录，见[合成参数案例](piezocatalysis-lca-modeling/assets/examples/synthetic-parametric/README.md)。

Review uncertainty evidence and run the [synthetic joint-distribution example](piezocatalysis-lca-modeling/assets/examples/synthetic-uncertainty/README.md).

不确定性数据盘点及合成联合分布验证见[不确定性示例](piezocatalysis-lca-modeling/assets/examples/synthetic-uncertainty/README.md)。

Check declared scenario boundaries and functional units with the [scenario comparability examples](piezocatalysis-lca-modeling/assets/examples/synthetic-comparability/README.md).

比较情景前可使用[情景可比性检查](piezocatalysis-lca-modeling/assets/examples/synthetic-comparability/README.md)核对功能单位和研究边界。

Cycle inventories can be labeled and reviewed for dataset mapping; see the [synthetic handoff](piezocatalysis-lca-modeling/assets/examples/synthetic-handoff/README.md).

逐循环清单基准标记、映射和审核交接见[合成案例](piezocatalysis-lca-modeling/assets/examples/synthetic-handoff/README.md)。

For cycle-by-cycle catalyst reuse, see the [synthetic cycle examples](piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/README.md).

逐循环催化剂回收、补加及处理清单请参见[逐循环合成案例](piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/README.md)。

Selected ecoinvent process references, product-system links and selected LCIA flow factors can be reviewed using `mapping_coverage.py`; see the [openLCA workflow](piezocatalysis-lca-modeling/references/openlca-workflow.md#selected-mapping-and-lcia-coverage-review).

可使用 `mapping_coverage.py` 核对选定数据集的参考交换、产品系统连接及指定基本流的 LCIA 表征因子；具体方法见 [openLCA 工作流](piezocatalysis-lca-modeling/references/openlca-workflow.md#selected-mapping-and-lcia-coverage-review)。

Version 1.7.0 connects cyclic experiment intake and catalyst disposal tracking to openLCA mapping checks, fixed-exchange scenario recalculation, and replayable research deliveries. See the [release notes](docs/RELEASE_v1.7.0_zh.md) and [migration notes](docs/migration-notes.md).

v1.7.0 把逐循环实验接入、催化剂末端去向、openLCA 映射核对和情景重算接到科研交付。升级时请阅读[迁移说明](docs/migration-notes.md)。

## Windows and macOS development / 双平台开发

The two platforms share the same Skill and tests. Follow the [Windows guide](platforms/windows/README.md) or [macOS guide](platforms/macos/README.md) for setup, testing, and local openLCA behavior.

Windows 与 macOS 共用科研核心和发布版本。平台接入、提交流程及目录说明见[双平台开发布局](platforms/README.md)。

## Agent usage / Agent 使用

Install or load the `piezocatalysis-lca-modeling/` Skill in the agent environment, then request the relevant LCA task. The agent starts from [`SKILL.md`](piezocatalysis-lca-modeling/SKILL.md) and selects the appropriate scripts and references; for example: “审查两组压电催化实验的功能单位和数据缺口，再用合成数据演示清单与图表。” Outputs and software access depend on the data, environment and task.

将 `piezocatalysis-lca-modeling/` 安装或加载到 Agent 环境后，直接提出科研任务。Agent 从 [`SKILL.md`](piezocatalysis-lca-modeling/SKILL.md) 选择对应流程、脚本和参考资料；实际输出及软件连接取决于任务、可用数据和环境。

## Contents / 内容

- `piezocatalysis-lca-modeling/`: installable Skill folder / 可安装 Skill 文件夹
- `USER_MANUAL_BILINGUAL.md`: Chinese-English user manual / 中英双语使用手册
- `LICENSE`: MIT license for original package content / 原创内容 MIT 许可证
- `NOTICE.md`: third-party, database, and confidentiality notice / 第三方、数据库与保密声明

The source DOCX and licensed LCA databases are intentionally not included.

原始 DOCX、许可证信息及商业数据库未包含在公开包中。

## Citation / 引用

If you use this software in research, please cite the specific version used.

如果您在科研工作中使用本软件，请引用实际使用的具体版本。

### Version v1.7.3

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.7.3)* [Computer software]. GitHub. [Source commit](https://github.com/William-Lebert/piezocatalysis-LCA-modeling-skill/commit/7c6ee0cc26dfeaba2a620b8baa0ad2b5f3d655de).

### Version v1.7.2

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.7.2)* [Computer software]. GitHub. [Source commit](https://github.com/William-Lebert/piezocatalysis-LCA-modeling-skill/commit/945ac8db587a3466496702c503eb522fe2e51a5d).

### Version v1.7.1

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.7.1)* [Computer software]. GitHub. [Source commit](https://github.com/William-Lebert/piezocatalysis-LCA-modeling-skill/commit/baf98205cf876fed8c4c3765d687570f61cd0588).

### Version v1.7.0

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.7.0)* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24395295

### Version v1.6.0

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.6.0)* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24333330

### Version v1.5.0

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.5.0)* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24269146

### Version v1.4.0

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.4.0)* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24252591

### Version v1.3.0

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.3.0)* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24225943

### Version v1.2.0

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.2.0)* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24203326

### Version v1.1.1

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.1.1)* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24186960

### Version v1.1.0

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.1.0)* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24040497

### Version v1.0.0

Pu, X. (2026). *Piezocatalysis LCA Modeling Skill (Version v1.0.0)* [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.23813630

### All versions / 所有版本

Project DOI: https://doi.org/10.5281/zenodo.23813629

For machine-readable citation metadata, see [`CITATION.cff`](CITATION.cff).

机器可读引用信息见 [`CITATION.cff`](CITATION.cff)。

## Optional advanced-engine feasibility / 可选高级引擎评估

A synthetic Brightway example and the limits on parameterization, uncertainty analysis, and prospective scenarios are documented in [the feasibility record](piezocatalysis-lca-modeling/assets/examples/synthetic-brightway/README.md). These engines are not core dependencies.

合成 Brightway 案例及参数化、不确定性分析和前瞻情景的限制见[可行性记录](piezocatalysis-lca-modeling/assets/examples/synthetic-brightway/README.md)；高级引擎不属于核心依赖。

### 逐循环清单与 openLCA 交接

开发中的逐循环清单交接支持标注每功能单位基准、记录密度换算依据，并通过只读预检核对映射与数据库参考交换。预检不会创建产品系统；映射代理和缺项仍需研究者判断。操作示例见 [逐循环交接说明](piezocatalysis-lca-modeling/assets/examples/synthetic-handoff/README.md)。

Agent 可用 `scripts/mapping_review.py` 只读记录多个候选的地域、参考产品、单位、参考方向、代理理由和选用／拒绝记录；导出映射保持待审核。详见[合成映射审查说明](piezocatalysis-lca-modeling/assets/examples/synthetic-mapping-review/README.md)。

逐循环结果可用 `scripts/result_coverage.py` 检查技术流连接、所选影响类别、基本流因子及正负贡献；完整报告可能包含受许可约束的数据。详见 [openLCA 工作流](piezocatalysis-lca-modeling/references/openlca-workflow.md#result-interpretation-and-selected-coverage)。

逐循环情景比较可由 `scripts/cycle_scenario_compare.py` 根据两份循环记录重建每功能单位清单，检查声明的功能单位与边界等条件，并将独立 openLCA 结果与贡献量近似并列。背景数据、场景与模型交换仍需核对，自动检查不授权排名，须独立核对服务和模型。详见 [逐循环情景工作流](piezocatalysis-lca-modeling/references/openlca-workflow.md#cycle-scenario-comparison)。

实验数据质量可先用 `scripts/experimental_quality.py` 核对逐批、逐循环记录、检测限和功率／时间配对，再结合 `uncertainty_readiness.py` 评估分布与关联依据。示例见[合成数据质量检查](piezocatalysis-lca-modeling/assets/examples/synthetic-quality/README.md)。

压电催化应用还支持以过氧化氢为产品的功能单位：见 [合成 H2O2 前景示例](piezocatalysis-lca-modeling/assets/examples/synthetic-h2o2/README.md)和[领域文献与建模启示](piezocatalysis-lca-modeling/references/domain-literature.md)。过氧化氢净积累量、回收产品和污染物去除是不同的功能，需分别说明边界。开发中的扩展支持 H2O2 产品前景的证据链接与科研交付，产品定义和实验依据仍需人工审核。

实验数据证据链可用 `scripts/evidence_chain.py` 将前景输入与 CSV 记录、单位、数据基准及每功能单位清单逐项核对；`scripts/piezocatalysis_checks.py` 可检查超声及光照能耗、氧化剂、pH 调节和催化剂去向。原始 Excel／文献页码目前仍须人工核对。参见[合成证据链示例](piezocatalysis-lca-modeling/assets/examples/synthetic-evidence/README.md)。

压电催化服务、实验边界与证据可使用 `scripts/domain_review.py` 汇总检查：处理水量、表观污染物去除、H₂O₂ 产品和干催化剂制备分别声明；缺失值和检测限不会自动补零。参见[合成领域检查示例](piezocatalysis-lca-modeling/assets/examples/synthetic-domain-review/README.md)及[研究检查表](piezocatalysis-lca-modeling/references/domain-quality-checklist.md)。

绘图接口可将逐循环、单类别阶段贡献、可比情景和单因素敏感性报告导出为 CSV、可编辑 SVG 和 PNG；详见[合成绘图示例与依赖](piezocatalysis-lca-modeling/assets/examples/synthetic-plotting/README.md)。阶段分配有明确的固定背景条件，部分模型及数据许可提示会随图保留。

### Agent 科研交付

Agent 可用 `scripts/research_delivery.py` 整理已有清单、证据、映射、计算、图表和方法草稿，并核对来源哈希与缺口。见[合成交付示例](piezocatalysis-lca-modeling/assets/examples/synthetic-delivery/README.md)；该整理流程不代替软件重算或科研审查。

### 压电催化情景与工程放大（开发中）

可按相同服务比较逐循环清单、记录测量范围和工程假设，并关联独立核验的 openLCA 比较；见 [合成情景说明](piezocatalysis-lca-modeling/assets/examples/synthetic-engineering/README.md)。

## Related projects / 参考项目

The following projects informed the evaluation of LCA engines and integration approaches; each is independently maintained and has its own license.

以下项目为生命周期评价引擎与对接方式的评估提供了参考；各项目独立维护，分别适用其自身许可证。

- [LCA-Skills](https://github.com/SDAI-institute/LCA-Skills) and [Activity Browser](https://github.com/LCA-ActivityBrowser/activity-browser): research workflow and result interpretation.
- [Brightway2](https://github.com/brightway-lca/brightway2), [bw2calc](https://github.com/brightway-lca/brightway2-calc), and [bw2io](https://github.com/brightway-lca/brightway2-io): LCA calculation and data import.
- [openLCA IPC Python client](https://github.com/GreenDelta/olca-ipc.py) and [openLCA Python examples](https://github.com/GreenDelta/openlca-python-examples): openLCA integration.
- [lca_algebraic](https://github.com/oie-mines-paristech/lca_algebraic): parametric modeling and sensitivity analysis.
- [premise](https://github.com/polca/premise): prospective background scenarios.

## Task routes / 任务入口

For a quick check of supplied data, choose **Quick Audit**; for building or calculating a study, choose **Guided LCA**; to organize existing results, choose **Research Delivery**. Single-purpose tasks can call the appropriate existing tool directly. See [task routing and optional stage records](piezocatalysis-lca-modeling/references/task-routing.md). A file-integrity `PASS` is not a scientific approval.

检查现有数据可选择**快速审查**；建立或计算模型选择**引导建模**；整理已有结果选择**科研交付**。单项任务可直接调用相应工具。阶段输入、人工复核点与可选状态记录见[任务路由](piezocatalysis-lca-modeling/references/task-routing.md)；文件完整性通过不代表科研审核通过。

逐循环研究可使用[样品关联与服务检查合成案例](piezocatalysis-lca-modeling/assets/examples/synthetic-cycle-service/README.md)记录批次、样品、阈值和寿命声明；功能单位换算与科研可比性仍需单独确认。

开发中的[逐循环情景绑定](piezocatalysis-lca-modeling/assets/examples/synthetic-bound-scenarios/README.md)可逐情景核对清单、软件模型交换、背景过程和参数；部分模型仍需人工复核。

开发中的科研交付可核对绑定情景及加和敏感性图，区分已有 openLCA 重算与用户提供的近似；真实实验资料可按[数据准备清单](docs/real-case-intake_zh.md)整理。
