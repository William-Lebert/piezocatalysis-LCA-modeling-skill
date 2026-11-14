# Piezocatalysis LCA Modeling Skill / 压电催化 LCA 建模技能包

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23813629.svg)](https://doi.org/10.5281/zenodo.23813629)

Version 1.3.0, 2026-11-15.

版本：1.3.0，2026-11-15。

This release contains a Codex Skill for research-grade life-cycle assessment of piezocatalysis, photocatalysis, and piezo-photocatalysis systems. It supports software-neutral model design plus implementation routes for openLCA and SimaPro.

本发布包面向压电催化、光催化和压电光催化体系的科研级生命周期评价，包含软件中立的建模规范，以及 openLCA 与 SimaPro 两条实施路径。

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

For cycle-by-cycle catalyst reuse, see the [synthetic cycle examples](piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/README.md).

逐循环催化剂回收、补加及处理清单请参见[逐循环合成案例](piezocatalysis-lca-modeling/assets/examples/synthetic-cycles/README.md)。

Selected ecoinvent process references, product-system links and selected LCIA flow factors can be reviewed using `mapping_coverage.py`; see the [openLCA workflow](piezocatalysis-lca-modeling/references/openlca-workflow.md#selected-mapping-and-lcia-coverage-review).

可使用 `mapping_coverage.py` 核对选定数据集的参考交换、产品系统连接及指定基本流的 LCIA 表征因子；具体方法见 [openLCA 工作流](piezocatalysis-lca-modeling/references/openlca-workflow.md#selected-mapping-and-lcia-coverage-review)。

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

### Version v1.3.0

The version-specific Zenodo DOI will be added after the archive is verified.

版本专属 Zenodo DOI 在归档核验后补充。

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

## Related projects / 参考项目

The following projects informed the evaluation of LCA engines and integration approaches; each is independently maintained and has its own license.

以下项目为生命周期评价引擎与对接方式的评估提供了参考；各项目独立维护，分别适用其自身许可证。

- [LCA-Skills](https://github.com/SDAI-institute/LCA-Skills) and [Activity Browser](https://github.com/LCA-ActivityBrowser/activity-browser): research workflow and result interpretation.
- [Brightway2](https://github.com/brightway-lca/brightway2), [bw2calc](https://github.com/brightway-lca/brightway2-calc), and [bw2io](https://github.com/brightway-lca/brightway2-io): LCA calculation and data import.
- [openLCA IPC Python client](https://github.com/GreenDelta/olca-ipc.py) and [openLCA Python examples](https://github.com/GreenDelta/openlca-python-examples): openLCA integration.
- [lca_algebraic](https://github.com/oie-mines-paristech/lca_algebraic): parametric modeling and sensitivity analysis.
- [premise](https://github.com/polca/premise): prospective background scenarios.
