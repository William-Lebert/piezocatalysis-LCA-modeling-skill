# Piezocatalysis LCA Modeling Skill / 压电催化 LCA 建模技能包

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23813629.svg)](https://doi.org/10.5281/zenodo.23813629)

Version 1.1.1, 2026-11-13.

版本：1.1.1，2026-11-13。

This release contains a Codex Skill for research-grade life-cycle assessment of piezocatalysis, photocatalysis, and piezo-photocatalysis systems. It supports software-neutral model design plus implementation routes for openLCA and SimaPro.

本发布包面向压电催化、光催化和压电光催化体系的科研级生命周期评价，包含软件中立的建模规范，以及 openLCA 与 SimaPro 两条实施路径。

The optional openLCA adapter can discover an existing local service. On the verified macOS openLCA 2.7.0 distribution it can also start a guarded temporary local server using a clone of an existing database; see the [openLCA workflow](piezocatalysis-lca-modeling/references/openlca-workflow.md) for setup and limitations.

可选的 openLCA 适配器支持发现已有本机服务；在已验证的 macOS openLCA 2.7.0 发行版上，也可基于已有数据库的临时副本启动受限本机服务。具体条件和限制见 [openLCA 工作流](piezocatalysis-lca-modeling/references/openlca-workflow.md)。

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

- [Brightway2](https://github.com/brightway-lca/brightway2), [bw2calc](https://github.com/brightway-lca/brightway2-calc), and [bw2io](https://github.com/brightway-lca/brightway2-io): LCA calculation and data import.
- [openLCA IPC Python client](https://github.com/GreenDelta/olca-ipc.py) and [openLCA Python examples](https://github.com/GreenDelta/openlca-python-examples): openLCA integration.
- [lca_algebraic](https://github.com/oie-mines-paristech/lca_algebraic): parametric modeling and sensitivity analysis.
- [premise](https://github.com/polca/premise): prospective background scenarios.
